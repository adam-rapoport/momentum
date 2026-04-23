"""Smoke test: verify per-turn model routing rules.

Runs select_model against a handful of inputs and checks the result.
Does NOT hit Groq.

Usage:
  .venv/bin/python -m scripts.try_routing
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings
from app.core.model_router import HEAVY_SLASH_COMMANDS, select_model


def main() -> None:
    default = settings.groq_model
    heavy = settings.groq_heavy_model
    assert default != heavy, (
        f"default and heavy models are the same ({default}); routing would be a no-op"
    )

    cases: list[tuple[str, str, dict | None, str]] = [
        (
            "casual chat -> default",
            "what's the project status look like?",
            None,
            default,
        ),
        (
            "empty metadata + /write-prd -> heavy",
            "/write-prd SSO via Okta for web",
            {},
            heavy,
        ),
        (
            "/stakeholder-update -> heavy",
            "/stakeholder-update weekly exec note",
            {},
            heavy,
        ),
        (
            "/meeting-prep -> heavy",
            "/meeting-prep Thursday planning",
            None,
            heavy,
        ),
        (
            "unknown slash command -> default",
            "/something-else please help",
            {},
            default,
        ),
        (
            "active skill in metadata -> heavy (even without slash command)",
            "ok go ahead and draft it",
            {"active_skill": "write-prd", "active_skill_phase": "drafting"},
            heavy,
        ),
        (
            "intake-phase user reply during active skill -> heavy",
            "target users are internal admins",
            {"active_skill": "write-prd", "active_skill_phase": "intake"},
            heavy,
        ),
        (
            "no active skill and no slash -> default",
            "thanks, that's all for now",
            {},
            default,
        ),
    ]

    failures = 0
    for label, user_text, meta, expected in cases:
        got = select_model(user_text, meta)
        ok = got == expected
        icon = "OK " if ok else "FAIL"
        print(f"  [{icon}] {label}")
        print(f"        user={user_text!r} meta={meta}")
        print(f"        expected={expected} got={got}")
        if not ok:
            failures += 1

    print()
    print(f"heavy slash commands configured: {sorted(HEAVY_SLASH_COMMANDS)}")
    print(f"default model: {default}")
    print(f"heavy model:   {heavy}")
    print()
    if failures:
        print(f"{failures} case(s) failed")
        sys.exit(1)
    print("all routing cases passed")


if __name__ == "__main__":
    main()
