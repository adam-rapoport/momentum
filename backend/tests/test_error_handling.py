"""Tests for WebSocket error classification (Sprint 4 Chunk B).

Ports `scripts/try_model_error.py` to pytest. We monkey-patch
`process_message` to raise specific exceptions and verify the websocket
handler emits the right error code + user-facing message.
"""
from __future__ import annotations

from unittest.mock import patch
from uuid import uuid4

import httpx
import pytest
from openai import APIError

from app.api.websocket import _handle_user_message
from app.core.session_engine import CommitFailedError


class _FakeWebSocket:
    """Minimal stand-in for `fastapi.WebSocket.send_json`."""

    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def send_json(self, payload: dict) -> None:
        self.sent.append(payload)


def _fake_api_error(message: str) -> APIError:
    req = httpx.Request("POST", "https://example.test/v1/chat/completions")
    return APIError(message, request=req, body=None)


def _patched_process_message(exc: BaseException):
    """Return an async-generator callable matching process_message's shape
    that raises `exc` on first iteration."""

    async def inner(**_kwargs):
        if False:  # pragma: no cover — makes this a generator
            yield
        raise exc

    return inner


async def _run_case(exc: BaseException) -> dict:
    fake = _patched_process_message(exc)
    with patch("app.api.websocket.process_message", new=fake):
        ws = _FakeWebSocket()
        await _handle_user_message(ws, uuid4(), "ignored")
    assert ws.sent, "websocket handler emitted no frame"
    return ws.sent[0]


async def test_groq_tool_use_failed_routes_to_model_tool_call_failed():
    frame = await _run_case(
        _fake_api_error(
            "Failed to call a function. Please adjust your prompt. See "
            "'failed_generation' for more details."
        )
    )
    assert frame["code"] == "MODEL_TOOL_CALL_FAILED"
    assert "retry" in frame["message"].lower()


async def test_literal_tool_use_failed_substring():
    frame = await _run_case(_fake_api_error("tool_use_failed: invalid function call"))
    assert frame["code"] == "MODEL_TOOL_CALL_FAILED"


async def test_generic_api_error_routes_to_model_api_error():
    frame = await _run_case(_fake_api_error("Service temporarily unavailable"))
    assert frame["code"] == "MODEL_API_ERROR"


async def test_rate_limit_error_routes_to_model_api_error():
    # Google's free-tier quota-exceeded (429). We treat this as a generic
    # API error since retrying in 38s isn't something the model can fix.
    frame = await _run_case(_fake_api_error("RESOURCE_EXHAUSTED: quota exceeded"))
    assert frame["code"] == "MODEL_API_ERROR"


async def test_commit_failed_routes_to_db_error():
    exc = CommitFailedError("persist_user_message", RuntimeError("connection reset"))
    frame = await _run_case(exc)
    assert frame["code"] == "DB_ERROR"
    assert "rolled back" in frame["message"].lower()


async def test_session_not_found_routes_to_not_found():
    frame = await _run_case(ValueError("session abc not found"))
    assert frame["code"] == "NOT_FOUND"


async def test_unexpected_exception_routes_to_internal_error():
    frame = await _run_case(RuntimeError("something weird"))
    assert frame["code"] == "INTERNAL_ERROR"
    # Should NOT leak the raw exception text — just a safe generic message.
    assert "something weird" not in frame["message"]
