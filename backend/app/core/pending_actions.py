"""Pending-action staging for the pause-and-review flow (Sprint 5 Chunk E).

A "pending action" is a tool's externally-visible side effect (send an
email, send calendar invites) that has been staged but not executed.
Staged actions live as a FIFO queue in
`session.session_metadata['pending_actions']` (Phase 1, finding A4: the
old singular `pending_action` slot silently dropped the second of two
actions staged in one tool batch — e.g. parallel SendEmail calls). Each
is resolved one at a time: the user approves (executes), revises
(clears, model re-stages), or restarts (clears, drops the work), and the
engine re-pauses on the next queued action until the queue is empty.
The legacy singular key is still read so pre-Phase-1 sessions resolve
cleanly. This is the non-skill, non-document equivalent of
`pending_deliverable` from Sprint 3.

Action shape:
    {
      "kind": "send_email" | "create_event",
      "tool_name": "SendEmail" | "CreateCalendarEvent",
      "call_id": "...",  # tool_call id that staged it (None on legacy rows);
                         # used to rewrite the matching staged tool_result
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
    call_id: str | None = None,
) -> None:
    """Append a pending action to the session's staging queue. Caller is
    responsible for the surrounding commit — session_engine commits at
    the end of each tool batch. `call_id` is the staging tool_call's id
    (from ToolContext.current_call_id) so resolution can rewrite exactly
    the tool_result that belongs to this action."""
    if kind not in VALID_KINDS:
        raise ValueError(f"invalid pending_action kind: {kind!r}")

    session = await db.scalar(select(Session).where(Session.id == session_id))
    if session is None:
        raise ValueError(f"session {session_id} not found")

    meta = dict(session.session_metadata or {})
    queue = list(meta.get("pending_actions") or [])
    queue.append(
        {
            "kind": kind,
            "tool_name": tool_name,
            "call_id": call_id,
            "params": params,
            "preview": preview,
            "staged_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    meta["pending_actions"] = queue
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
    """Stamp the HEAD staged action as 'executing'. The session engine commits
    this BEFORE calling execute_pending_action so that a crash between the
    send and the result being recorded cannot lead to a blind re-send: a later
    approve of an 'executing' action is refused (see _resolve_pending_action)."""
    meta = dict(session.session_metadata or {})
    if meta.get("pending_action") is not None:
        # Legacy singular slot (pre-Phase-1 session).
        action = dict(meta["pending_action"])
        action["status"] = "executing"
        meta["pending_action"] = action
    else:
        queue = list(meta.get("pending_actions") or [])
        if queue:
            action = dict(queue[0])
            action["status"] = "executing"
            queue[0] = action
            meta["pending_actions"] = queue
    session.session_metadata = meta


def clear_pending_action(session: Session) -> dict[str, Any] | None:
    """Pop the HEAD pending action (legacy singular slot first, then the
    queue) from session_metadata; return it so callers can log/use it.
    Returns None when nothing is staged."""
    meta = dict(session.session_metadata or {})
    cleared = meta.pop("pending_action", None)
    if cleared is None:
        queue = list(meta.get("pending_actions") or [])
        if queue:
            cleared = queue.pop(0)
            if queue:
                meta["pending_actions"] = queue
            else:
                meta.pop("pending_actions", None)
    session.session_metadata = meta
    return cleared


def get_pending_actions(session: Session) -> list[dict[str, Any]]:
    """All staged actions, oldest first. A legacy singular `pending_action`
    (written before the Phase 1 list migration) is treated as the queue head
    so old paused sessions resolve exactly like new ones."""
    meta = session.session_metadata or {}
    queue = list(meta.get("pending_actions") or [])
    legacy = meta.get("pending_action")
    if legacy is not None:
        queue.insert(0, legacy)
    return queue


def get_pending_action(session: Session) -> dict[str, Any] | None:
    """The action currently up for review — head of the staging queue."""
    queue = get_pending_actions(session)
    return queue[0] if queue else None
