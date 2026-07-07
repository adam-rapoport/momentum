"""Trigger-collision matrix — keeps skill activation sane as the roster grows.

Three layers, all driven by the live registry so new skills are covered
automatically:

1. Keyword policy: every trigger phrase has >=2 essential tokens after
   filler stripping (single tokens only via the acronym allowlist).
2. Self-trigger + uniqueness: every keyword, spoken as an utterance,
   routes to its own skill, and fires exactly ONE skill's matcher unless
   the overlap is explicitly allowed with a declared winner.
3. Routing corpus (tests/trigger_corpus.yaml): realistic PM utterances
   with expected routing — grown with every wave of new skills.
   (Lives flat in tests/ — a tests/data/ subdir would hit the repo's
   unanchored `data/` gitignore pattern.)
"""
from __future__ import annotations

from pathlib import Path

import yaml

from app.core.skills import _FILLER_WORDS, _keyword_matches, detect_skill, load_skills

CORPUS_PATH = Path(__file__).parent / "trigger_corpus.yaml"

# Single-token trigger phrases allowed (unambiguous PM acronyms). Grows
# deliberately — e.g. "prfaq", "premortem" — never with bare common nouns.
ACRONYM_ALLOWLIST = {"adr", "qbr"}

# keyword -> skill that must win when that keyword, spoken as an utterance,
# legitimately fires more than one skill's matcher. Every entry needs a
# comment justifying the overlap.
ALLOWED_OVERLAPS = {
    # "prep for sprint review" (meeting-prep) contains sprint-review's
    # "sprint review"; prepping for the meeting is the more specific intent.
    "prep for sprint review": "meeting-prep",
    # Same shape for the planning ceremony: "prep for sprint planning"
    # (meeting-prep) contains sprint-planning's "sprint planning".
    "prep for sprint planning": "meeting-prep",
}


def _essential(keyword: str) -> list[str]:
    return [t for t in keyword.split() if t not in _FILLER_WORDS] or keyword.split()


def _firing_skills(utterance: str) -> set[str]:
    lowered = utterance.lower()
    return {
        skill.name
        for skill in load_skills(force=True).values()
        for kw in skill.trigger_keywords
        if _keyword_matches(kw, lowered)
    }


def test_keyword_policy_two_essential_tokens_or_allowlisted_acronym():
    for skill in load_skills(force=True).values():
        for kw in skill.trigger_keywords:
            assert len(_essential(kw)) >= 2 or kw in ACRONYM_ALLOWLIST, (
                f"{skill.name}: trigger '{kw}' is a single essential token and "
                "not an allowlisted acronym — bare words fire on ordinary chat"
            )


def test_every_keyword_self_triggers_its_own_skill():
    for skill in load_skills(force=True).values():
        for kw in skill.trigger_keywords:
            got = detect_skill(f"help me {kw}", {})
            want = ALLOWED_OVERLAPS.get(kw, skill.name)
            assert got == want, (
                f"'{kw}' should route to {want}, got {got}"
            )


def test_keyword_uniqueness_matrix():
    """Each keyword utterance fires exactly one skill's matcher — or the
    overlap is declared in ALLOWED_OVERLAPS with the winning skill."""
    for skill in load_skills(force=True).values():
        for kw in skill.trigger_keywords:
            fired = _firing_skills(f"help me {kw}")
            if len(fired) <= 1:
                continue
            assert kw in ALLOWED_OVERLAPS, (
                f"trigger '{kw}' ({skill.name}) fires {sorted(fired)} — "
                "either redesign the keyword or declare the overlap + winner "
                "in ALLOWED_OVERLAPS"
            )
            winner = ALLOWED_OVERLAPS[kw]
            assert detect_skill(f"help me {kw}", {}) == winner


def test_routing_corpus():
    raw = yaml.safe_load(CORPUS_PATH.read_text(encoding="utf-8"))
    rows = raw["utterances"]
    assert len(rows) >= 30, "corpus should keep growing with every wave"
    failures = []
    for row in rows:
        got = detect_skill(row["text"], {})
        if got != row["expect"]:
            failures.append(f"  {row['text']!r}: expected {row['expect']}, got {got}")
    assert not failures, "corpus routing mismatches:\n" + "\n".join(failures)
