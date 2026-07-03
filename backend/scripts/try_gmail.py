"""Smoke test: exercise the Gmail tools end-to-end against the user's
real Google account, bypassing the LLM.

Usage:
  .venv/bin/python -m scripts.try_gmail              # full happy-path
  .venv/bin/python -m scripts.try_gmail list-only    # just ListEmails
  .venv/bin/python -m scripts.try_gmail draft-only   # ListEmails + DraftEmail

Requires: Google integration connected with Gmail scopes (Settings ->
Reconnect after Sprint 5 Chunk A).
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

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


async def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "full"

    async with SessionLocal() as db:
        user = (await db.scalars(select(User).limit(1))).first()
        project = (await db.scalars(select(Project).limit(1))).first()
        if user is None or project is None:
            print("[try_gmail] seed the DB first: python -m scripts.seed")
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
            print("== ListEmails (3 most recent) ==")
            list_output = await execute_tool(
                "ListEmails", {"max_results": 3}
            )
            print(list_output)

            if mode == "list-only":
                return

            # Try to extract the first message_id from the output for ReadEmail
            first_id = _first_id(list_output)
            if first_id:
                print(f"\n== ReadEmail({first_id}) ==")
                read_output = await execute_tool(
                    "ReadEmail", {"message_id": first_id}
                )
                # Truncate body in stdout so the terminal isn't flooded
                print(read_output[:1500])
                if len(read_output) > 1500:
                    print(f"... [{len(read_output) - 1500} more chars]")
            else:
                print("\n== ReadEmail skipped — no message_id in list output ==")

            if mode == "draft-only" or mode == "full":
                print("\n== DraftEmail (to self) ==")
                draft_output = await execute_tool(
                    "DraftEmail",
                    {
                        "to": [user.email or "rapoport.apps@gmail.com"],
                        "subject": "Momentum Sprint 5 Chunk B smoke test",
                        "body_markdown": (
                            "Hi from Momentum.\n\n"
                            "This is a test draft created by `try_gmail`. "
                            "Open Gmail to see it, then delete or send.\n"
                        ),
                    },
                )
                print(draft_output)

            if mode == "full":
                print("\n== SendEmail (Chunk B placeholder — creates a draft) ==")
                send_output = await execute_tool(
                    "SendEmail",
                    {
                        "to": [user.email or "rapoport.apps@gmail.com"],
                        "subject": "Momentum SendEmail (placeholder) test",
                        "body_markdown": "Should land as a draft, not a sent message.",
                    },
                )
                print(send_output)
        finally:
            reset_context(token)


def _first_id(list_output: str) -> str | None:
    """Lazy parser for the bullet list — finds the first 'id: `XXX`'."""
    import re

    m = re.search(r"id:\s*`([^`]+)`", list_output)
    return m.group(1) if m else None


if __name__ == "__main__":
    asyncio.run(main())
