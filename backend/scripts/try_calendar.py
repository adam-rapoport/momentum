"""Smoke test: exercise the Calendar tools end-to-end against the
user's real Google account.

Usage:
  .venv/bin/python -m scripts.try_calendar              # full happy-path
  .venv/bin/python -m scripts.try_calendar list-only    # just ListCalendarEvents
  .venv/bin/python -m scripts.try_calendar avail-only   # List + FindAvailability
"""
from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

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


def _now_local() -> datetime:
    # Use local-wall-clock in the machine's current tz for readable output.
    try:
        return datetime.now(ZoneInfo("America/Los_Angeles"))
    except Exception:  # noqa: BLE001 — fallback to utc if zoneinfo unavailable
        return datetime.now(timezone.utc)


async def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "full"
    now = _now_local()
    week_ahead = now + timedelta(days=7)

    async with SessionLocal() as db:
        user = (await db.scalars(select(User).limit(1))).first()
        project = (await db.scalars(select(Project).limit(1))).first()
        if user is None or project is None:
            print("[try_calendar] seed the DB first: python -m scripts.seed")
            return

        token = set_context(
            ToolContext(
                db=db,
                session_id=user.id,
                project_id=project.id,
                user_id=user.id,
            )
        )
        try:
            print(f"== ListCalendarEvents ({now.isoformat()} → {week_ahead.isoformat()}) ==")
            print(
                await execute_tool(
                    "ListCalendarEvents",
                    {
                        "time_min": now.isoformat(),
                        "time_max": week_ahead.isoformat(),
                        "max_results": 10,
                    },
                )
            )

            if mode == "list-only":
                return

            print("\n== FindAvailability (30-min slots in next 3 days) ==")
            three_day = now + timedelta(days=3)
            print(
                await execute_tool(
                    "FindAvailability",
                    {
                        "time_min": now.isoformat(),
                        "time_max": three_day.isoformat(),
                        "duration_minutes": 30,
                    },
                )
            )

            if mode == "avail-only":
                return

            # Create a solo focus block 1 hour from now. No attendees → no
            # send-invites concern, safe to actually create.
            start = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
            end = start + timedelta(minutes=30)
            print(f"\n== CreateCalendarEvent (solo block at {start.isoformat()}) ==")
            print(
                await execute_tool(
                    "CreateCalendarEvent",
                    {
                        "summary": "pMomentum Chunk C smoke test (delete me)",
                        "start_iso": start.isoformat(),
                        "end_iso": end.isoformat(),
                        "description": "Auto-created by try_calendar. Safe to delete.",
                    },
                )
            )

            # And one with attendees — should suppress invites and tell the
            # user to send manually.
            start2 = start + timedelta(hours=2)
            end2 = start2 + timedelta(minutes=30)
            print(f"\n== CreateCalendarEvent (with attendee, invites suppressed) ==")
            print(
                await execute_tool(
                    "CreateCalendarEvent",
                    {
                        "summary": "pMomentum Chunk C smoke test w/ attendee (delete me)",
                        "start_iso": start2.isoformat(),
                        "end_iso": end2.isoformat(),
                        "attendees": [user.email or "rapoport.apps@gmail.com"],
                    },
                )
            )
        finally:
            reset_context(token)


if __name__ == "__main__":
    asyncio.run(main())
