"""Tests for the Sprint 5 Chunk E pause-and-review-for-actions flow.

Covers:
- `_classify_review_response` recognizes /approve, /revise, /restart for both
  the existing deliverable flow and the new action flow.
- `_resolve_pending_action` for approve / revise / restart, including the
  case where the staged action's execution fails (must not crash, must
  produce a system note that nudges the model to apologize).

`execute_pending_action` is patched so we never hit Google.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.core.pending_actions import (
    clear_pending_action,
    get_pending_action,
    get_pending_actions,
    mark_action_executing,
)
from app.core.session_engine import (
    _classify_review_response,
    _resolve_pending_action,
    _summarize_pending_action,
)


def _fake_session(meta: dict) -> SimpleNamespace:
    """Stand-in for the SQLAlchemy `Session` model — the resolver only
    reads/writes `.session_metadata`, `.status`, and `.user_id`."""
    return SimpleNamespace(
        id=uuid4(),
        user_id=uuid4(),
        status="awaiting_review",
        session_metadata=dict(meta),
    )


def _fake_send_email_action() -> dict:
    return {
        "kind": "send_email",
        "tool_name": "SendEmail",
        "params": {
            "to": ["alice@example.com"],
            "cc": [],
            "subject": "Hi",
            "body_markdown": "Hello",
            "reply_to_message_id": None,
        },
        "preview": {
            "to": ["alice@example.com"],
            "cc": [],
            "subject": "Hi",
            "body_snippet": "Hello",
        },
        "staged_at": "2026-04-24T00:00:00+00:00",
    }


# ---------- _classify_review_response ----------


def test_classify_approve_words():
    for text in ["/approve", "approve", "approved", "looks good", "lgtm"]:
        assert _classify_review_response(text) == "approve", text


def test_classify_restart_words():
    for text in ["/restart", "cancel", "start over"]:
        assert _classify_review_response(text) == "restart", text


def test_classify_revise_requires_slash():
    assert _classify_review_response("/revise change tone") == "revise"
    # Bare "revise" (no slash) is not a valid revise — leave the pause in place.
    assert _classify_review_response("change the tone") is None


def test_classify_empty_returns_none():
    assert _classify_review_response("") is None
    assert _classify_review_response("   ") is None


def test_classify_lenient_approve_phrases():
    """Phase 1 item 8: natural approvals — trailing punctuation stripped,
    commas/apostrophes folded. The word list stays deliberately small."""
    for text in ["Yes", "yes, send it.", "Send it!", "go ahead", "LGTM!", "Approved."]:
        assert _classify_review_response(text) == "approve", text


def test_classify_lenient_restart_phrases():
    for text in ["No", "don't", "stop", "Don't send it.", "never mind", "do not send"]:
        assert _classify_review_response(text) == "restart", text


def test_classify_free_text_stays_none():
    """Anything off-list is free text — with a staged action the engine
    refuses to run a model turn for it (APPROVAL_REQUIRED)."""
    for text in [
        "what about carol?",
        "yes but change the subject first",
        "maybe later",
        "can you cc dave too",
    ]:
        assert _classify_review_response(text) is None, text


# ---------- pending_actions queue (Phase 1 item 8, finding A4) ----------


def test_queue_reads_legacy_singular_first():
    """A pre-Phase-1 singular pending_action is the queue head; clearing pops
    it before any list entries, then the list drains FIFO."""
    legacy = _fake_send_email_action()
    queued = {**_fake_send_email_action(), "call_id": "c2"}
    session = _fake_session({"pending_action": legacy, "pending_actions": [queued]})

    actions = get_pending_actions(session)
    assert actions[0] == legacy
    assert actions[1]["call_id"] == "c2"

    assert clear_pending_action(session) == legacy
    assert get_pending_action(session)["call_id"] == "c2"
    assert clear_pending_action(session)["call_id"] == "c2"
    assert get_pending_action(session) is None
    assert clear_pending_action(session) is None
    # Fully drained — neither key lingers in metadata.
    assert "pending_action" not in session.session_metadata
    assert "pending_actions" not in session.session_metadata


def test_mark_action_executing_stamps_queue_head_only():
    a1 = {**_fake_send_email_action(), "call_id": "c1"}
    a2 = {**_fake_send_email_action(), "call_id": "c2"}
    session = _fake_session({"pending_actions": [a1, a2]})

    mark_action_executing(session)

    queue = session.session_metadata["pending_actions"]
    assert queue[0]["status"] == "executing"
    assert "status" not in queue[1]


# ---------- _summarize_pending_action ----------


def test_summarize_send_email():
    summary = _summarize_pending_action(
        "send_email",
        {"to": ["a@x.com", "b@x.com"], "subject": "Hi"},
    )
    assert "Hi" in summary
    assert "a@x.com" in summary and "b@x.com" in summary


def test_summarize_create_event():
    summary = _summarize_pending_action(
        "create_event",
        {"summary": "Sync", "attendees": ["bob@x.com"]},
    )
    assert "Sync" in summary
    assert "bob@x.com" in summary


def test_summarize_unknown_kind_falls_back():
    summary = _summarize_pending_action("mystery", {})
    assert "approval" in summary.lower()


# ---------- _resolve_pending_action: approve happy-path ----------


@pytest.mark.asyncio
async def test_resolve_approve_executes_and_clears():
    action = _fake_send_email_action()
    session = _fake_session({"pending_action": action})

    with patch(
        "app.core.session_engine.execute_pending_action",
        new=AsyncMock(return_value="Email sent to alice@example.com."),
    ), patch(
        "app.core.session_engine._rewrite_staged_tool_result",
        new=AsyncMock(return_value=True),
    ), patch(
        "app.core.session_engine._safe_commit",
        new=AsyncMock(return_value=None),
    ) as commit_mock:
        note = await _resolve_pending_action(
            db=None, session=session, intent="approve", user_text="/approve",
            action=action,
        )

    assert "alice@example.com" in note
    assert session.status == "active"
    assert "pending_action" not in session.session_metadata
    # Should tell the model NOT to re-call the tool.
    assert "do not" in note.lower() or "don't" in note.lower()
    # Two-phase execute: 'executing' stamp committed BEFORE the send, result
    # committed after — so a crash in between can't double-send.
    stages = [c.kwargs.get("stage") or c.args[-1] for c in commit_mock.call_args_list]
    assert stages == ["mark_action_executing", "record_action_executed"]


@pytest.mark.asyncio
async def test_resolve_approve_of_executing_action_refuses_resend():
    """An action stamped 'executing' means a previous approve was interrupted
    between the send and the result-commit — re-approving must NOT re-send."""
    action = _fake_send_email_action()
    action["status"] = "executing"
    session = _fake_session({"pending_action": action})

    execute = AsyncMock(return_value="should not run")
    with patch(
        "app.core.session_engine.execute_pending_action", new=execute,
    ), patch(
        "app.core.session_engine._rewrite_staged_tool_result",
        new=AsyncMock(return_value=True),
    ), patch(
        "app.core.session_engine._safe_commit",
        new=AsyncMock(return_value=None),
    ):
        note = await _resolve_pending_action(
            db=None, session=session, intent="approve", user_text="/approve",
            action=action,
        )

    execute.assert_not_awaited()
    assert session.status == "active"
    assert "pending_action" not in session.session_metadata
    assert "verify" in note.lower()


@pytest.mark.asyncio
async def test_resolve_approve_failure_leaves_clean_state():
    """If the staged send fails, we still clear the pause but the model
    needs to know to apologize and offer to retry."""
    action = _fake_send_email_action()
    session = _fake_session({"pending_action": action})

    with patch(
        "app.core.session_engine.execute_pending_action",
        new=AsyncMock(side_effect=RuntimeError("Gmail timeout")),
    ), patch(
        "app.core.session_engine._rewrite_staged_tool_result",
        new=AsyncMock(return_value=True),
    ), patch(
        "app.core.session_engine._safe_commit",
        new=AsyncMock(return_value=None),
    ):
        note = await _resolve_pending_action(
            db=None, session=session, intent="approve", user_text="/approve",
            action=action,
        )

    assert "Gmail timeout" in note
    assert "apologize" in note.lower() or "fail" in note.lower()
    assert session.status == "active"
    assert "pending_action" not in session.session_metadata


# ---------- _resolve_pending_action: revise ----------


@pytest.mark.asyncio
async def test_resolve_revise_clears_and_notes_revision():
    action = _fake_send_email_action()
    session = _fake_session({"pending_action": action})

    with patch(
        "app.core.session_engine._rewrite_staged_tool_result",
        new=AsyncMock(return_value=True),
    ):
        note = await _resolve_pending_action(
            db=None, session=session, intent="revise",
            user_text="/revise make it warmer",
            action=action,
        )

    assert "make it warmer" in note
    assert "SendEmail" in note  # tells model to re-call the tool
    assert session.status == "active"
    assert "pending_action" not in session.session_metadata


@pytest.mark.asyncio
async def test_resolve_revise_without_detail_asks_for_clarification():
    action = _fake_send_email_action()
    session = _fake_session({"pending_action": action})

    with patch(
        "app.core.session_engine._rewrite_staged_tool_result",
        new=AsyncMock(return_value=True),
    ):
        note = await _resolve_pending_action(
            db=None, session=session, intent="revise",
            user_text="/revise",
            action=action,
        )

    assert "ask" in note.lower() or "clarif" in note.lower() or "what to change" in note.lower()


# ---------- _resolve_pending_action: restart ----------


@pytest.mark.asyncio
async def test_resolve_restart_drops_action_and_disallows_restage():
    action = _fake_send_email_action()
    session = _fake_session({"pending_action": action})

    with patch(
        "app.core.session_engine._rewrite_staged_tool_result",
        new=AsyncMock(return_value=True),
    ):
        note = await _resolve_pending_action(
            db=None, session=session, intent="restart",
            user_text="/restart",
            action=action,
        )

    assert "cancel" in note.lower()
    assert "do not" in note.lower() or "don't" in note.lower()
    assert session.status == "active"
    assert "pending_action" not in session.session_metadata
