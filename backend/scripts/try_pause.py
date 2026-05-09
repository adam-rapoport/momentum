"""Smoke test: verify pause-and-review state-machine helpers.

Doesn't hit the LLM. Exercises:
  - _classify_review_response for approve / revise / restart / free text
  - _apply_review_resolution mutates session correctly for each intent
  - AwaitReview tool produces a non-error output (sentinel works)

Usage:
  .venv/bin/python -m scripts.try_pause
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.core.session_engine import (
    _apply_review_resolution,
    _apply_skill_detection,
    _classify_review_response,
)
from app.core.tools import (
    ToolContext,
    _load_builtin_tools,
    execute_tool,
    reset_context,
    set_context,
)
from app.dependencies import SessionLocal
from app.models import Project, Session, User

_load_builtin_tools()


async def main() -> None:
    print("== classify review responses ==")
    cases = [
        ("/approve", "approve"),
        ("Looks good", "approve"),
        ("LGTM", "approve"),
        ("/revise add a non-goals section", "revise"),
        ("/revise", "revise"),
        ("/restart", "restart"),
        ("start over", "restart"),
        ("cancel", "restart"),
        ("random free-form reply", None),
        ("", None),
    ]
    for text, expected in cases:
        result = _classify_review_response(text)
        marker = "ok" if result == expected else "FAIL"
        print(f"  [{marker}] {text!r:45s} -> {result!r} (expected {expected!r})")
        assert result == expected

    async with SessionLocal() as db:
        user = (await db.scalars(select(User).limit(1))).first()
        project = (await db.scalars(select(Project).limit(1))).first()
        assert user and project, "seed the DB first: python -m scripts.seed"

        session = (
            await db.scalars(
                select(Session).where(Session.user_id == user.id).limit(1)
            )
        ).first()
        if session is None:
            print("[try_pause] no sessions exist — create one in the UI first")
            return

        print("\n== apply resolution: approve ==")
        session.status = "awaiting_review"
        session.session_metadata = {
            "active_skill": "write-prd",
            "active_skill_phase": "review",
            "pending_deliverable": {"deliverable_kind": "prd", "document_id": "x"},
        }
        note = await _apply_review_resolution(db, session, "approve", "/approve")
        assert session.status == "active"
        assert "active_skill" not in session.session_metadata
        assert "pending_deliverable" not in session.session_metadata
        assert "approved" in note.lower()
        print(f"  status={session.status!r}, meta={session.session_metadata}")
        print(f"  note[:80]={note[:80]!r}")

        print("\n== apply resolution: revise (keeps skill active) ==")
        session.status = "awaiting_review"
        session.session_metadata = {
            "active_skill": "write-prd",
            "active_skill_phase": "review",
            "pending_deliverable": {"deliverable_kind": "prd"},
        }
        note = await _apply_review_resolution(
            db, session, "revise", "/revise add a non-goals section"
        )
        assert session.status == "active"
        assert session.session_metadata.get("active_skill") == "write-prd"
        assert "pending_deliverable" not in session.session_metadata
        assert "add a non-goals section" in note
        print(f"  status={session.status!r}, meta={session.session_metadata}")
        print(f"  note[:100]={note[:100]!r}")

        print("\n== apply resolution: restart ==")
        session.status = "awaiting_review"
        session.session_metadata = {
            "active_skill": "write-prd",
            "active_skill_phase": "review",
            "pending_deliverable": {"deliverable_kind": "prd"},
        }
        note = await _apply_review_resolution(db, session, "restart", "/restart")
        assert session.status == "active"
        assert "active_skill" not in session.session_metadata
        assert "pending_deliverable" not in session.session_metadata
        assert "restart" in note.lower() or "cancelled" in note.lower()
        print(f"  status={session.status!r}, meta={session.session_metadata}")

        print("\n== skill detection after /restart clears via exit sentinel ==")
        session.session_metadata = {"active_skill": "write-prd", "active_skill_phase": "intake"}
        _apply_skill_detection(session, "/restart")
        assert "active_skill" not in session.session_metadata
        print(f"  meta after /restart: {session.session_metadata}")

        print("\n== AwaitReview tool output (sentinel still works) ==")
        token = set_context(
            ToolContext(
                db=db,
                session_id=session.id,
                project_id=project.id,
                user_id=user.id,
            )
        )
        try:
            output = await execute_tool(
                "AwaitReview",
                {
                    "deliverable_kind": "prd",
                    "document_id": "first-prd",
                    "summary_for_user": "Drafted the smoke-test PRD.",
                },
            )
            print(f"  output[:100]={output[:100]!r}")
            assert not output.startswith("Error")

            print("\n== AwaitReview requires deliverable_kind + summary ==")
            err = await execute_tool("AwaitReview", {})
            assert err.startswith("Error")
            print(f"  err[:80]={err[:80]!r}")
        finally:
            reset_context(token)

    print("\nAll Chunk C smoke checks passed.")


if __name__ == "__main__":
    asyncio.run(main())
