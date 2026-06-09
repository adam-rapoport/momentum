"""Pending-action staging for the pause-and-review flow (Sprint 5 Chunk E).

A "pending action" is a tool's externally-visible side effect (send an
email, send calendar invites) that has been staged but not executed.
It lives in `session.session_metadata['pending_action']` until the user
approves (executes), revises (clears, model re-stages), or restarts
(clears, drops the work). This is the non-skill, non-document equivalent
of `pending_deliverable` from Sprint 3.

Action shape:
    {
      "kind": "send_email" | "create_event",
      "tool_name": "SendEmail" | "CreateCalendarEvent",
      "params": {...},   # raw inputs to re-execute on approve
      "preview": {...},  # frontend-friendly fields for the ApprovalBar
      "staged_at": ISO-8601 string,
    }
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Session

logger = logging.getLogger(__name__)


VALID_KINDS = {"send_email", "create_event"}


async def stage_action(
    db: AsyncSession,
    session_id: UUID,
    *,
    kind: str,
    tool_name: str,
    params: dict[str, Any],
    preview: dict[str, Any],
) -> None:
    """Save a pending action onto the session's metadata. Caller is
    responsible for the surrounding commit — session_engine commits at
    the end of each tool batch."""
    if kind not in VALID_KINDS:
        raise ValueError(f"invalid pending_action kind: {kind!r}")

    session = await db.scalar(select(Session).where(Session.id == session_id))
    if session is None:
        raise ValueError(f"session {session_id} not found")

    meta = dict(session.session_metadata or {})
    meta["pending_action"] = {
        "kind": kind,
        "tool_name": tool_name,
        "params": params,
        "preview": preview,
        "staged_at": datetime.now(timezone.utc).isoformat(),
    }
    session.session_metadata = meta


async def execute_pending_action(
    db: AsyncSession, user_id: UUID, action: dict[str, Any]
) -> str:
    """Execute the staged action. Returns a one-line success summary
    suitable for the resume system note. Raises on failure — caller
    converts to an error system note for the model."""
    kind = action.get("kind")
    params = action.get("params") or {}
    if kind == "send_email":
        return await _execute_send_email(db, user_id, params)
    if kind == "create_event":
        return await _execute_create_event(db, user_id, params)
    raise ValueError(f"unknown pending_action kind: {kind!r}")


async def _execute_send_email(
    db: AsyncSession, user_id: UUID, params: dict[str, Any]
) -> str:
    # Imports localized to avoid pulling Google libraries at module-load
    # time when other code paths (tests) don't need them.
    from app.core.integrations.gmail import create_draft, send_draft

    draft = await create_draft(
        db,
        user_id,
        to=params["to"],
        cc=params.get("cc") or None,
        subject=params["subject"],
        body_markdown=params["body_markdown"],
        reply_to_message_id=params.get("reply_to_message_id"),
    )
    sent = await send_draft(db, user_id, draft["draft_id"])
    recipients = ", ".join(params["to"])
    return (
        f"Email sent to {recipients}: '{params['subject']}'. "
        f"Message id: {sent['message_id']}."
    )


async def _execute_create_event(
    db: AsyncSession, user_id: UUID, params: dict[str, Any]
) -> str:
    from app.core.integrations.google_calendar import create_event

    result = await create_event(
        db,
        user_id,
        summary=params["summary"],
        start_iso=params["start_iso"],
        end_iso=params["end_iso"],
        description=params.get("description") or "",
        location=params.get("location") or "",
        attendees=params.get("attendees") or None,
        calendar_id=params.get("calendar_id") or "primary",
        # Approved → invites go out.
        send_updates="all",
    )
    attendees = params.get("attendees") or []
    return (
        f"Event '{result['summary']}' created and invites sent to "
        f"{', '.join(attendees) if attendees else '(no attendees)'}. "
        f"Calendar URL: {result['html_link']}"
    )


def mark_action_executing(session: Session) -> None:
    """Stamp the staged action as 'executing'. The session engine commits this
    BEFORE calling execute_pending_action so that a crash between the send and
    the result being recorded cannot lead to a blind re-send: a later approve
    of an 'executing' action is refused (see _resolve_pending_action)."""
    meta = dict(session.session_metadata or {})
    action = dict(meta.get("pending_action") or {})
    action["status"] = "executing"
    meta["pending_action"] = action
    session.session_metadata = meta


def clear_pending_action(session: Session) -> dict[str, Any] | None:
    """Remove any pending_action from session_metadata; return the cleared
    action so callers can log/use it."""
    meta = dict(session.session_metadata or {})
    cleared = meta.pop("pending_action", None)
    session.session_metadata = meta
    return cleared


def get_pending_action(session: Session) -> dict[str, Any] | None:
    return (session.session_metadata or {}).get("pending_action")
