"""Smoke test: exercise the document tools end-to-end against the seeded
default project, bypassing the LLM.

Usage:
  .venv/bin/python -m scripts.try_documents

Walks through: list (empty) -> write -> list -> read -> edit -> read ->
list. Also checks the skills loader picks up all three SKILL.md files
and that detect_skill routes slash commands correctly.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.core.skills import detect_skill, load_skills
from app.core.tools import (
    ToolContext,
    _load_builtin_tools,
    execute_tool,
    reset_context,
    set_context,
)
from app.dependencies import SessionLocal
from app.models import Project, User

_load_builtin_tools()


async def main() -> None:
    async with SessionLocal() as db:
        user = (await db.scalars(select(User).limit(1))).first()
        project = (await db.scalars(select(Project).limit(1))).first()
        if user is None or project is None:
            print("[try_documents] seed the DB first: python -m scripts.seed")
            return

        token = set_context(
            ToolContext(
                db=db,
                session_id=user.id,  # unused by document tools
                project_id=project.id,
                user_id=user.id,
            )
        )
        try:
            print("== ListDocuments (likely empty) ==")
            print(await execute_tool("ListDocuments", {}))

            print("\n== WriteDocument (first-prd) ==")
            body = (
                "# Test PRD\n\n"
                "## Problem\nUsers have no way to test the doc tools.\n\n"
                "## Scope\nOne round-trip smoke test.\n"
            )
            print(
                await execute_tool(
                    "WriteDocument",
                    {"title": "Test PRD", "content_markdown": body, "document_id": "first-prd"},
                )
            )

            print("\n== ListDocuments ==")
            print(await execute_tool("ListDocuments", {}))

            print("\n== ReadDocument(first-prd) ==")
            print(await execute_tool("ReadDocument", {"document_id": "first-prd"}))

            print("\n== EditDocument (add a section) ==")
            print(
                await execute_tool(
                    "EditDocument",
                    {
                        "document_id": "first-prd",
                        "old_string": "## Scope\nOne round-trip smoke test.",
                        "new_string": (
                            "## Scope\nOne round-trip smoke test.\n\n"
                            "## Open Questions\n- Did the edit land?"
                        ),
                    },
                )
            )

            print("\n== ReadDocument (verify edit) ==")
            print(await execute_tool("ReadDocument", {"document_id": "first-prd"}))

            print("\n== EditDocument (should fail — count mismatch) ==")
            print(
                await execute_tool(
                    "EditDocument",
                    {"document_id": "first-prd", "old_string": "nope", "new_string": "x"},
                )
            )

            print("\n== AwaitReview (sentinel echo) ==")
            print(
                await execute_tool(
                    "AwaitReview",
                    {
                        "deliverable_kind": "prd",
                        "document_id": "first-prd",
                        "summary_for_user": "Drafted the smoke-test PRD.",
                    },
                )
            )
        finally:
            reset_context(token)

    print("\n== Skills loader ==")
    skills = load_skills(force=True)
    for name, skill in skills.items():
        print(
            f"  {name:22s} slash=/{skill.slash_command:20s} phases={skill.phases} "
            f"trigger_keywords={skill.trigger_keywords[:3]}..."
        )

    print("\n== detect_skill probes ==")
    cases = [
        ("/write-prd I need a PRD for 2FA", None),
        ("/meeting-prep prep for tomorrow", None),
        ("let's write a PRD for the referral program", None),
        ("random casual chat", None),
        ("/cancel-skill", {"active_skill": "write-prd"}),
        ("/write-prd ...", {"active_skill": "meeting-prep"}),  # slash wins
        ("write a prd", {"active_skill": "meeting-prep"}),  # kw ignored (skill active)
    ]
    for text, meta in cases:
        print(f"  {text!r:55s} meta={meta}  ->  {detect_skill(text, meta)!r}")


if __name__ == "__main__":
    asyncio.run(main())
