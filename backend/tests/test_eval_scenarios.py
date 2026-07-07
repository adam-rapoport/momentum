"""Every skill ships with an eval scenario (scripts/eval/scenarios/).

Pure-file checks — no network, no backend. This is what makes "write the
eval scenario" an enforced checklist item for every new skill: a SKILL.md
without a matching scenario fails CI.
"""
from __future__ import annotations

from pathlib import Path

import yaml

from app.core.skills import load_skills

SCENARIOS_DIR = Path(__file__).resolve().parents[1] / "scripts" / "eval" / "scenarios"


def _scenarios() -> dict[str, dict]:
    out: dict[str, dict] = {}
    for path in sorted(SCENARIOS_DIR.glob("*.yaml")):
        out[path.stem] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return out


def test_every_skill_has_a_scenario():
    skills = set(load_skills(force=True))
    missing = skills - set(_scenarios())
    assert not missing, f"skills without an eval scenario: {sorted(missing)}"


def test_every_scenario_maps_to_a_real_skill():
    skills = load_skills(force=True)
    orphaned = set(_scenarios()) - set(skills)
    assert not orphaned, f"scenarios without a matching skill: {sorted(orphaned)}"


def test_scenario_contents_are_valid():
    skills = load_skills(force=True)
    for name, raw in _scenarios().items():
        assert (raw.get("skill") or name) == name, f"{name}: 'skill' mismatches filename"
        prompt = (raw.get("prompt") or "").strip()
        assert prompt, f"{name}: missing prompt"
        skill = skills.get(name)
        if skill is not None:
            assert prompt.startswith(f"/{skill.slash_command}"), (
                f"{name}: prompt must start with /{skill.slash_command} so the "
                "run activates the skill deterministically"
            )
        expect = raw.get("expect") or {}
        assert int(expect.get("min_documents", 1)) >= 0
        replies = raw.get("scripted_replies") or []
        assert isinstance(replies, list) and all(isinstance(r, str) for r in replies), (
            f"{name}: scripted_replies must be a list of strings"
        )
