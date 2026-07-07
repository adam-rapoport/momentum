"""Drive Momentum skills end-to-end against a live isolated backend.

This is the promoted, parameterized version of the one-off runner used for
the 2026-07-03 skills quality review. The runner is generic: everything
workspace-specific (the fixture documents, the seeded profile, the
per-skill prompts) lives outside this file — fixtures in an external
directory, prompts in `scenarios/<skill>.yaml` next to this script.

Usage (from backend/, venv active, backend already running isolated — see
serve_isolated.sh):

    python -m scripts.eval.run_live_skills check
    python -m scripts.eval.run_live_skills seed --fixtures DIR --data-dir DIR
    python -m scripts.eval.run_live_skills run --fixtures DIR --data-dir DIR [skill ...]

Outputs per skill under --out: <skill>.transcript.md, <skill>.meta.json and
a copy of every document the skill saved (<skill>.doc-N.md).

WS protocol notes (app/schemas/websocket.py):
  terminal events for an assistant turn are stream.done, stream.awaiting_review
  (AwaitReview pause — reply like a user approving), or error. stream.text is
  streamed text; stream.tool_start / stream.tool_result are tool activity.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import httpx
import websockets
import yaml

SCENARIOS_DIR = Path(__file__).resolve().parent / "scenarios"

TURN_TIMEOUT = 300    # max SILENCE between stream events (a hung turn),
                      # not whole-turn wall clock — degraded providers make
                      # legitimate turns slow (503 retries restart the whole
                      # streamed generation) and those keep emitting events
SKILL_TIMEOUT = 1200  # hard wall-clock cap per skill
MAX_USER_MESSAGES = 5  # initial ask + nudges/approval (raised per-scenario
                       # when scripted_replies need more room)

DEFAULT_APPROVAL = "Looks good — finalize it. No changes."
DEFAULT_NUDGES = [
    "Use whatever's in memory and the reference docs — your best judgment on the rest. "
    "Don't wait on me; work through your phases and save the document.",
    "No further input from me. Make reasonable assumptions, note them in the doc, and save it.",
]


@dataclass
class Scenario:
    skill: str
    prompt: str
    scripted_replies: list[str] = field(default_factory=list)
    approval: str = DEFAULT_APPROVAL
    nudges: list[str] = field(default_factory=lambda: list(DEFAULT_NUDGES))
    min_documents: int = 1
    grader_notes: str = ""


def log(msg: str) -> None:
    print(msg, flush=True)


def load_scenarios() -> dict[str, Scenario]:
    scenarios: dict[str, Scenario] = {}
    for path in sorted(SCENARIOS_DIR.glob("*.yaml")):
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        skill = (raw.get("skill") or path.stem).strip()
        prompt = (raw.get("prompt") or "").strip()
        if not prompt:
            raise SystemExit(f"scenario {path.name}: missing 'prompt'")
        expect = raw.get("expect") or {}
        scenarios[skill] = Scenario(
            skill=skill,
            prompt=prompt,
            scripted_replies=[str(r) for r in (raw.get("scripted_replies") or [])],
            approval=(raw.get("approval") or DEFAULT_APPROVAL),
            nudges=[str(n) for n in raw["nudges"]] if raw.get("nudges") else list(DEFAULT_NUDGES),
            min_documents=int(expect.get("min_documents", 1)),
            grader_notes=(raw.get("grader_notes") or "").strip(),
        )
    return scenarios


def check_scenarios() -> int:
    """Every registered skill has a scenario and vice versa. No network."""
    from app.core.skills import load_skills  # local import: needs backend cwd

    skills = set(load_skills(force=True))
    scenarios = set(load_scenarios())
    missing = sorted(skills - scenarios)
    orphaned = sorted(scenarios - skills)
    for name in missing:
        log(f"[check] MISSING scenario: scenarios/{name}.yaml")
    for name in orphaned:
        log(f"[check] ORPHANED scenario (no such skill): {name}")
    if not missing and not orphaned:
        log(f"[check] OK — {len(skills)} skills, {len(scenarios)} scenarios, 1:1")
        return 0
    return 1


class Runner:
    def __init__(self, args: argparse.Namespace) -> None:
        self.base = args.base_url.rstrip("/")
        self.api = f"{self.base}/api/v1"
        self.ws_url = self.base.replace("http", "ws", 1) + "/ws"
        self.fixtures = Path(args.fixtures).expanduser() if args.fixtures else None
        self.docs_dir = (
            Path(args.data_dir).expanduser() / "documents" if args.data_dir else None
        )  # local doc store is a sibling of memory/ under DATA_DIR
        self.out = Path(args.out).expanduser()

    # -- seeding ---------------------------------------------------------

    def _fixture_yaml(self, name: str) -> dict:
        assert self.fixtures is not None
        path = self.fixtures / name
        if not path.exists():
            raise SystemExit(
                f"{name} not found in --fixtures dir {self.fixtures} — "
                "it defines the seeded workspace (see scripts/eval/README.md)"
            )
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    async def seed(self) -> None:
        if self.fixtures is None:
            raise SystemExit("seed needs --fixtures (or MOMENTUM_EVAL_FIXTURES)")
        profile = self._fixture_yaml("profile.yaml")
        manifest = self._fixture_yaml("manifest.yaml")
        uploads = manifest.get("upload") or []
        async with httpx.AsyncClient(timeout=300) as c:
            (await c.post(f"{self.api}/onboarding/complete")).raise_for_status()
            r = await c.post(f"{self.api}/onboarding/profile", json=profile)
            r.raise_for_status()
            log(f"[seed] profile: {r.json()}")
            for name in uploads:
                path = self.fixtures / name
                t0 = time.time()
                r = await c.post(
                    f"{self.api}/memory/documents",
                    files={"file": (name, path.read_bytes())},
                )
                info = r.json() if r.status_code == 200 else r.text[:200]
                log(f"[seed] {name}: {r.status_code} in {time.time()-t0:.0f}s -> {info}")
            r = await c.get(f"{self.api}/memory")
            log(f"[seed] memory records now: {len(r.json())}")

    # -- running ---------------------------------------------------------

    def _docs_on_disk(self) -> set[Path]:
        if self.docs_dir is None or not self.docs_dir.exists():
            return set()
        return set(self.docs_dir.rglob("*.md"))

    async def _one_turn(self, ws, transcript: list[str], skill_t0: float) -> dict:
        """Collect one assistant turn. Returns {'end': 'done'|'awaiting_review'|'error'|'timeout', ...}."""
        text_chars = 0
        event_counts: dict[str, int] = {}
        last_event = time.time()
        while True:
            idle_left = TURN_TIMEOUT - (time.time() - last_event)
            hard_left = SKILL_TIMEOUT - (time.time() - skill_t0)
            remaining = min(idle_left, hard_left)
            if remaining <= 0:
                return {"end": "timeout", "event_counts": event_counts}
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=remaining)
            except (asyncio.TimeoutError, TimeoutError):
                return {"end": "timeout", "event_counts": event_counts}
            last_event = time.time()
            ev = json.loads(raw)
            et = ev.get("type", "?")
            event_counts[et] = event_counts.get(et, 0) + 1
            if et == "stream.text":
                transcript.append(ev.get("text") or "")
                text_chars += len(ev.get("text") or "")
            elif et == "stream.tool_start":
                transcript.append(f"\n`[tool_start {ev.get('name')}]` ")
            elif et == "stream.tool_result":
                out = str(ev.get("output"))[:200].replace("\n", " ")
                flag = " ERROR" if ev.get("is_error") else ""
                transcript.append(f"`[tool_result{flag} {ev.get('name')}: {out}]`\n")
            elif et == "stream.awaiting_review":
                transcript.append(
                    f"\n`[awaiting_review kind={ev.get('kind')} doc={ev.get('document_id')}]`\n"
                    f"> {ev.get('summary_for_user') or ''}\n"
                )
                return {"end": "awaiting_review", "event_counts": event_counts, "text_chars": text_chars}
            elif et == "stream.done":
                return {
                    "end": "done", "event_counts": event_counts, "text_chars": text_chars,
                    "usage": ev.get("usage"), "metadata": ev.get("metadata"),
                }
            elif et == "error":
                transcript.append(f"\n`[error {ev.get('code')}: {ev.get('message')}]`\n")
                return {"end": "error", "event_counts": event_counts, "error": ev}
            # session.renamed etc.: ignore

    async def run_skill(self, sc: Scenario, suffix: str = "") -> None:
        if self.docs_dir is None:
            raise SystemExit("run needs --data-dir (the isolated backend's DATA_DIR)")
        self.out.mkdir(parents=True, exist_ok=True)
        transcript: list[str] = []
        meta: dict = {"skill": sc.skill, "turns": []}
        docs_before = self._docs_on_disk()
        skill_t0 = time.time()
        # Room for the initial ask + every scripted reply + approval + one nudge.
        max_msgs = max(MAX_USER_MESSAGES, len(sc.scripted_replies) + 3)

        async with httpx.AsyncClient(timeout=60) as c:
            r = await c.post(f"{self.api}/sessions", json={"title": f"live-run {sc.skill}{suffix}"})
            r.raise_for_status()
            session_id = r.json()["id"]
        meta["session_id"] = session_id

        approved = False
        replies = list(sc.scripted_replies)
        async with websockets.connect(self.ws_url, max_size=16 * 1024 * 1024) as ws:
            next_msg: str | None = sc.prompt
            nudge_i = 0
            sent = 0
            while next_msg is not None and sent < max_msgs:
                if time.time() - skill_t0 > SKILL_TIMEOUT:
                    meta["turns"].append({"error": "skill wall-clock cap hit"})
                    break
                transcript.append(f"\n\n## USER\n\n{next_msg}\n\n## ASSISTANT\n\n")
                await ws.send(json.dumps({
                    "type": "session.message", "session_id": session_id, "content": next_msg,
                }))
                sent += 1
                t0 = time.time()
                turn = await self._one_turn(ws, transcript, skill_t0)
                turn["seconds"] = round(time.time() - t0, 1)
                turn["user"] = next_msg[:100]
                meta["turns"].append(turn)
                log(f"[run] {sc.skill}{suffix} turn {sent}: {turn['end']} in {turn['seconds']}s {turn.get('event_counts')}")

                end = turn["end"]
                new_docs = self._docs_on_disk() - docs_before
                if end in ("error", "timeout"):
                    next_msg = None
                elif end == "awaiting_review":
                    if approved:  # second pause after an approval — bail, don't loop
                        next_msg = None
                    else:
                        approved = True
                        next_msg = sc.approval
                elif new_docs and approved:
                    next_msg = None  # doc saved + approval round-trip done
                elif new_docs and not "".join(transcript[-3:]).rstrip().endswith("?"):
                    next_msg = None  # doc saved, no pending question
                elif replies:
                    next_msg = replies.pop(0)  # scripted intake answers first
                elif nudge_i < len(sc.nudges):
                    next_msg = sc.nudges[nudge_i]
                    nudge_i += 1
                else:
                    next_msg = None

        new_docs = sorted(self._docs_on_disk() - docs_before)
        meta["documents_saved"] = len(new_docs)
        meta["meets_min_documents"] = len(new_docs) >= sc.min_documents
        meta["total_seconds"] = round(time.time() - skill_t0, 1)
        if sc.grader_notes:
            meta["grader_notes"] = sc.grader_notes
        for n, p in enumerate(new_docs, 1):
            shutil.copy(p, self.out / f"{sc.skill}{suffix}.doc-{n}.md")
        (self.out / f"{sc.skill}{suffix}.transcript.md").write_text("".join(transcript), encoding="utf-8")
        (self.out / f"{sc.skill}{suffix}.meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
        status = f"{len(new_docs)} doc(s)" if new_docs else "NO DOC SAVED"
        log(f"[run] {sc.skill}{suffix}: DONE — {status} in {meta['total_seconds']}s")


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    p.add_argument("mode", choices=["seed", "run", "check"])
    p.add_argument("skills", nargs="*", help="skill subset for run (default: all)")
    p.add_argument("--fixtures", default=os.environ.get("MOMENTUM_EVAL_FIXTURES"),
                   help="external fixtures dir with manifest.yaml + profile.yaml + docs")
    p.add_argument("--data-dir", default=None,
                   help="the isolated backend's DATA_DIR (to watch saved documents)")
    p.add_argument("--out", default=None, help="output dir for transcripts/docs/meta")
    p.add_argument("--base-url", default="http://127.0.0.1:8000")
    p.add_argument("--runs", type=int, default=1,
                   help="times to run each skill (>1 suffixes outputs .run2 etc; "
                        "prefer a fresh workspace per grade-bearing run — see README)")
    p.add_argument("--label", default="run", help="label used in the default --out dir name")
    args = p.parse_args(argv)
    if args.out is None:
        stamp = datetime.now().strftime("%Y%m%d-%H%M")
        args.out = f"eval-runs/{stamp}-{args.label}"
    return args


async def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if args.mode == "check":
        return check_scenarios()
    runner = Runner(args)
    if args.mode == "seed":
        await runner.seed()
        return 0
    scenarios = load_scenarios()
    wanted = args.skills or sorted(scenarios)
    unknown = [s for s in wanted if s not in scenarios]
    if unknown:
        raise SystemExit(f"no scenario for: {', '.join(unknown)} (run `check`)")
    for i in range(1, args.runs + 1):
        suffix = "" if i == 1 else f".run{i}"
        for skill in wanted:
            try:
                await runner.run_skill(scenarios[skill], suffix)
            except Exception as e:  # keep going; one broken run shouldn't sink the batch
                log(f"[run] {skill}{suffix}: FAILED {type(e).__name__}: {e}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
