"""WebSocket contract tests — plan item 30 (T2).

The WS event JSON is the de-facto frontend API: the desktop app's stream
reducer (frontend/lib/ws.ts) switch-cases on these exact shapes. These tests
pin them, byte for byte, by patching `process_message` in the websocket
module to yield one of each engine event, plus the error-code mapping and
the Phase 0 origin/token gate (close code 1008).

Runs against the real `app.main.app` via the `client` fixture (TestClient +
lifespan; the migrated throwaway test DB — see conftest's DATABASE_URL pin).
"""
from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4

import pytest
from starlette.websockets import WebSocketDisconnect

from app.config import settings
from app.core.session_engine import (
    AwaitingReviewEvent,
    CommitFailedError,
    DoneEvent,
    TextEvent,
    ToolResultEvent,
    ToolStartEvent,
)

SESSION_ID = "11111111-2222-3333-4444-555555555555"

_PENDING_ACTION = {
    "kind": "send_email",
    "tool_name": "SendEmail",
    "params": {"to": ["alice@example.com"], "subject": "Hi", "body_markdown": "Hello"},
    "preview": {"to": ["alice@example.com"], "subject": "Hi", "body_snippet": "Hello"},
    "staged_at": "2026-06-09T00:00:00+00:00",
}


def _one_of_each_events():
    """One engine event of every type, with distinctive field values so the
    serialized frames can be asserted exactly."""
    return [
        TextEvent(text="Hello"),
        ToolStartEvent(call_id="c1", name="TestEcho", input={"value": "ping"}),
        ToolResultEvent(call_id="c1", name="TestEcho", output="echo:ping", is_error=False),
        AwaitingReviewEvent(
            kind="send_email",
            deliverable_kind="send_email",
            document_id=None,
            summary_for_user="Send email 'Hi' to alice@example.com",
            url=None,
            model="test-model",
            pending_action=_PENDING_ACTION,
        ),
        DoneEvent(
            input_tokens=42,
            output_tokens=7,
            cost_usd=Decimal("0.00123"),
            total_cost_usd=Decimal("0.00456"),
            cancelled=False,
            model="test-model",
        ),
    ]


def _scripted_process_message(events):
    async def _fake(**_kwargs):
        for event in events:
            yield event

    return _fake


def _raising_process_message(exc: BaseException):
    async def _fake(**_kwargs):
        if False:  # pragma: no cover — makes this an async generator
            yield
        raise exc

    return _fake


# ---------- happy-path event JSON shapes ----------


def test_stream_event_json_shapes(client):
    fake = _scripted_process_message(_one_of_each_events())
    with patch("app.api.websocket.process_message", new=fake):
        with client.websocket_connect("/ws") as ws:
            ws.send_json(
                {"type": "session.message", "session_id": SESSION_ID, "content": "hi"}
            )
            frames = [ws.receive_json() for _ in range(5)]

    assert frames[0] == {
        "type": "stream.text",
        "session_id": SESSION_ID,
        "text": "Hello",
    }
    assert frames[1] == {
        "type": "stream.tool_start",
        "session_id": SESSION_ID,
        "call_id": "c1",
        "name": "TestEcho",
        "input": {"value": "ping"},
    }
    assert frames[2] == {
        "type": "stream.tool_result",
        "session_id": SESSION_ID,
        "call_id": "c1",
        "name": "TestEcho",
        "output": "echo:ping",
        "is_error": False,
    }
    assert frames[3] == {
        "type": "stream.awaiting_review",
        "session_id": SESSION_ID,
        "kind": "send_email",
        "deliverable_kind": "send_email",
        "document_id": None,
        "summary_for_user": "Send email 'Hi' to alice@example.com",
        "url": None,
        "model": "test-model",
        "pending_action": _PENDING_ACTION,
    }
    assert frames[4] == {
        "type": "stream.done",
        "session_id": SESSION_ID,
        "usage": {
            "input_tokens": 42,
            "output_tokens": 7,
            # Decimals cross the wire as strings, not floats.
            "cost_usd": "0.00123",
            "total_cost_usd": "0.00456",
        },
        "metadata": {"cancelled": False, "model": "test-model"},
    }


def test_socket_survives_across_turns(client):
    """The read loop must keep serving after a completed turn — one socket,
    many turns, is the frontend's usage pattern."""
    fake = _scripted_process_message([TextEvent(text="ok")])
    with patch("app.api.websocket.process_message", new=fake):
        with client.websocket_connect("/ws") as ws:
            for _ in range(2):
                ws.send_json(
                    {"type": "session.message", "session_id": SESSION_ID, "content": "x"}
                )
                assert ws.receive_json()["text"] == "ok"


def test_second_message_for_busy_session_rejected_with_turn_in_progress(client):
    """Phase 1 (A1/A3): turns run as tasks so the read loop keeps receiving;
    a second session.message while one is in flight is rejected with
    TURN_IN_PROGRESS instead of queueing or interleaving."""
    import asyncio

    async def _slow(**_kwargs):
        yield TextEvent(text="started")
        # Park until the connection is torn down (cancel) — long enough that
        # the second message definitely arrives mid-turn.
        await asyncio.sleep(30)
        yield TextEvent(text="never sent")  # pragma: no cover

    with patch("app.api.websocket.process_message", new=_slow):
        with client.websocket_connect("/ws") as ws:
            ws.send_json(
                {"type": "session.message", "session_id": SESSION_ID, "content": "one"}
            )
            assert ws.receive_json()["text"] == "started"

            ws.send_json(
                {"type": "session.message", "session_id": SESSION_ID, "content": "two"}
            )
            frame = ws.receive_json()
            assert frame["type"] == "error"
            assert frame["code"] == "TURN_IN_PROGRESS"
            assert frame["session_id"] == SESSION_ID
        # Closing the socket cancels the parked turn task (read-loop cleanup);
        # if it didn't, the TestClient context exit would hang here.


def test_cancel_frame_received_while_turn_streams(client):
    """The whole point of task-based turns: a session.cancel sent mid-turn is
    read and applied immediately, not after the turn finishes."""
    import asyncio

    from app.core.session_engine import _cancel_key
    from app.dependencies import kv_store

    cancelled_seen = {"value": False}

    async def _waits_for_cancel(*, session_id, kv, **_kwargs):
        yield TextEvent(text="streaming")
        for _ in range(200):  # ~2s budget — fails loudly rather than hanging
            if await kv.exists(_cancel_key(session_id)):
                cancelled_seen["value"] = True
                break
            await asyncio.sleep(0.01)
        yield DoneEvent(
            input_tokens=0,
            output_tokens=0,
            cost_usd=Decimal("0"),
            total_cost_usd=Decimal("0"),
            cancelled=cancelled_seen["value"],
            model="test-model",
        )

    with patch("app.api.websocket.process_message", new=_waits_for_cancel):
        with client.websocket_connect("/ws") as ws:
            ws.send_json(
                {"type": "session.message", "session_id": SESSION_ID, "content": "go"}
            )
            assert ws.receive_json()["text"] == "streaming"
            ws.send_json({"type": "session.cancel", "session_id": SESSION_ID})
            done = ws.receive_json()

    assert cancelled_seen["value"] is True
    assert done["type"] == "stream.done"
    assert done["metadata"]["cancelled"] is True
    # Cleanup parity with the real engine: drop the flag we set.
    client.portal.call(kv_store.delete, _cancel_key(SESSION_ID))


# ---------- error codes ----------


def test_validation_error_on_malformed_message(client):
    with client.websocket_connect("/ws") as ws:
        # Missing session_id.
        ws.send_json({"type": "session.message", "content": "hi"})
        frame = ws.receive_json()
        assert frame["type"] == "error"
        assert frame["code"] == "VALIDATION_ERROR"
        assert "session_id" in frame["message"]

        # Malformed cancel too — and the loop stays alive after each.
        ws.send_json({"type": "session.cancel"})
        frame = ws.receive_json()
        assert frame["code"] == "VALIDATION_ERROR"


def test_unknown_message_type(client):
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "bogus.frame"})
        frame = ws.receive_json()
        assert frame == {
            "type": "error",
            "code": "UNKNOWN_MESSAGE_TYPE",
            "message": "unknown type: bogus.frame",
        }


def test_not_found_for_unknown_session(client):
    """No patch here: the REAL process_message raises ValueError before any
    LLM work when the session row doesn't exist."""
    missing = str(uuid4())
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "session.message", "session_id": missing, "content": "hi"})
        frame = ws.receive_json()
        assert frame["type"] == "error"
        assert frame["code"] == "NOT_FOUND"
        assert frame["session_id"] == missing


def test_db_error_on_commit_failure(client):
    exc = CommitFailedError("persist_user_message", RuntimeError("disk full"))
    with patch("app.api.websocket.process_message", new=_raising_process_message(exc)):
        with client.websocket_connect("/ws") as ws:
            ws.send_json(
                {"type": "session.message", "session_id": SESSION_ID, "content": "hi"}
            )
            frame = ws.receive_json()
    assert frame["type"] == "error"
    assert frame["code"] == "DB_ERROR"
    assert frame["session_id"] == SESSION_ID
    # User-facing copy, not a stack trace.
    assert "rolled back" in frame["message"]
    assert "disk full" not in frame["message"]


def test_internal_error_on_unexpected_crash(client):
    exc = RuntimeError("kaboom")
    with patch("app.api.websocket.process_message", new=_raising_process_message(exc)):
        with client.websocket_connect("/ws") as ws:
            ws.send_json(
                {"type": "session.message", "session_id": SESSION_ID, "content": "hi"}
            )
            frame = ws.receive_json()
    assert frame["code"] == "INTERNAL_ERROR"
    assert "kaboom" not in frame["message"]


# ---------- session.cancel ----------


def test_cancel_sets_kv_flag(client):
    from app.core.session_engine import _cancel_key
    from app.dependencies import kv_store

    sid = uuid4()
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "session.cancel", "session_id": str(sid)})
        # cancel produces no reply frame; prove the loop is still alive.
        ws.send_json({"type": "bogus"})
        assert ws.receive_json()["code"] == "UNKNOWN_MESSAGE_TYPE"

    assert client.portal.call(kv_store.exists, _cancel_key(sid))


# ---------- Phase 0 trust boundary: origin + token (close code 1008) ----------


def test_ws_rejects_disallowed_origin(client):
    with pytest.raises(WebSocketDisconnect) as excinfo:
        with client.websocket_connect("/ws", headers={"Origin": "https://evil.example"}):
            pass
    assert excinfo.value.code == 1008


def test_ws_allows_local_and_tauri_origins(client):
    for origin in ("http://localhost:3000", "http://127.0.0.1:8000", "tauri://localhost"):
        with client.websocket_connect("/ws", headers={"Origin": origin}):
            pass  # accept succeeded


def test_ws_requires_token_when_configured(client, monkeypatch):
    monkeypatch.setattr(settings, "auth_token", "per-launch-secret")

    # No token → policy violation close.
    with pytest.raises(WebSocketDisconnect) as excinfo:
        with client.websocket_connect("/ws"):
            pass
    assert excinfo.value.code == 1008

    # Wrong token → same.
    with pytest.raises(WebSocketDisconnect) as excinfo:
        with client.websocket_connect("/ws?token=wrong"):
            pass
    assert excinfo.value.code == 1008

    # Correct token as query param → accepted.
    with client.websocket_connect("/ws?token=per-launch-secret"):
        pass
