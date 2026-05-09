"""End-to-end smoke test for Chunk E (pause-and-review for actions).

Bypasses the LLM. Drives the full pipeline manually:
  1. Set up a ToolContext on the seeded user/session.
  2. Call SendEmail → verify session_metadata.pending_action is set.
  3. Call _resolve_pending_action with intent='approve' → real Gmail send.
  4. Inspect resulting session state.

Plus a parallel pass for /revise (clears the action without sending) and
the calendar-event flow.

Usage:
  .venv/bin/python -m scripts.try_pause_action            # full happy-path (sends email!)
  .venv/bin/python -m scripts.try_pause_action revise     # only stage + revise (no send)
  .venv/bin/python -m scripts.try_pause_action stage-only # only stage, no resolution
"""
from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.core.pending_actions import get_pending_action
from app.core.session_engine import _resolve_pending_action
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
    mode = sys.argv[1] if len(sys.argv) > 1 else "full"

    async with SessionLocal() as db:
        user = (await db.scalars(select(User).limit(1))).first()
        project = (await db.scalars(select(Project).limit(1))).first()
        assert user and project, "seed first: python -m scripts.seed"

        session = (
            await db.scalars(
                select(Session).where(Session.user_id == user.id).limit(1)
            )
        ).first()
        if session is None:
            print("[try_pause_action] no sessions exist — create one in the UI first")
            return

        # Reset session state so this test is deterministic.
        session.status = "active"
        session.session_metadata = {}
        await db.commit()

        token = set_context(
            ToolContext(
                db=db,
                session_id=session.id,
                project_id=project.id,
                user_id=user.id,
            )
        )
        try:
            await _exercise_send_email(db, session, mode)
            if mode == "full":
                await _exercise_create_event(db, session, user)
        finally:
            reset_context(token)

    print("\n[try_pause_action] all checks passed.")


async def _exercise_send_email(db, session, mode: str) -> None:
    print("== SendEmail tool: stage ==")
    output = await execute_tool(
        "SendEmail",
        {
            "to": ["rapoport.apps@gmail.com"],
            "subject": "pMomentum Chunk E — staged email",
            "body_markdown": (
                "Hello from the Chunk E smoke test.\n\n"
                "If you're reading this in your inbox, the pause-and-review flow "
                "approved and sent it. If you only see it in drafts, the test "
                "ran with `revise` or `stage-only` mode."
            ),
        },
    )
    print(output[:300])
    assert "Pending approval" in output, "tool didn't return staging marker"

    # session_engine commits after each tool batch in real flow; do the same.
    await db.commit()
    pending = get_pending_action(session)
    assert pending is not None, "session_metadata.pending_action was not set"
    assert pending["kind"] == "send_email"
    assert pending["preview"]["to"] == ["rapoport.apps@gmail.com"]
    print(f"  staged kind={pending['kind']} subject={pending['preview']['subject']!r}")

    if mode == "stage-only":
        print("\n[stage-only] stopping here. session.session_metadata.pending_action is set.")
        return

    if mode == "revise":
        print("\n== resolve: revise (clears action, no send) ==")
        note = await _resolve_pending_action(
            db=db, session=session, intent="revise",
            user_text="/revise change the tone",
            action=pending,
        )
        assert "change the tone" in note
        await db.commit()
        assert get_pending_action(session) is None, "revise should clear pending_action"
        assert session.status == "active"
        print(f"  status={session.status} meta_keys={list(session.session_metadata or {})}")
        return

    print("\n== resolve: approve (REAL Gmail send happens here) ==")
    note = await _resolve_pending_action(
        db=db, session=session, intent="approve",
        user_text="/approve",
        action=pending,
    )
    print(f"  note[:150]={note[:150]!r}")
    assert "Email sent" in note or "Sent" in note or "email" in note.lower()
    await db.commit()
    assert get_pending_action(session) is None
    assert session.status == "active"
    print("  → check rapoport.apps@gmail.com inbox for the test message.")


async def _exercise_create_event(db, session, user) -> None:
    print("\n== CreateCalendarEvent tool: stage (with attendee) ==")
    now = datetime.now(ZoneInfo("America/Los_Angeles"))
    start = (now + timedelta(hours=4)).replace(minute=0, second=0, microsecond=0)
    end = start + timedelta(minutes=30)
    output = await execute_tool(
        "CreateCalendarEvent",
        {
            "summary": "pMomentum Chunk E — staged event (delete me)",
            "start_iso": start.isoformat(),
            "end_iso": end.isoformat(),
            "attendees": [user.email or "rapoport.apps@gmail.com"],
            "description": "Auto-created by try_pause_action.",
        },
    )
    print(output[:300])
    assert "Pending approval" in output, "calendar tool didn't stage"

    await db.commit()
    pending = get_pending_action(session)
    assert pending is not None and pending["kind"] == "create_event"
    print(f"  staged kind={pending['kind']} summary={pending['preview']['summary']!r}")

    print("\n== resolve: revise (clears, no event created) ==")
    note = await _resolve_pending_action(
        db=db, session=session, intent="revise",
        user_text="/revise move it later",
        action=pending,
    )
    assert "move it later" in note
    await db.commit()
    assert get_pending_action(session) is None
    print(f"  status={session.status} meta_keys={list(session.session_metadata or {})}")


if __name__ == "__main__":
    asyncio.run(main())
