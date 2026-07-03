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


async def test_quota_message_routes_to_model_rate_limited():
    # Google's free-tier quota-exceeded surfaces through the OpenAI-compat
    # endpoint as a bare APIError whose message carries the native status.
    # Phase 1 item 9: classified by message hint as MODEL_RATE_LIMITED.
    frame = await _run_case(_fake_api_error("RESOURCE_EXHAUSTED: quota exceeded"))
    assert frame["code"] == "MODEL_RATE_LIMITED"


# ---------- Phase 1 item 9: provider-neutral taxonomy ----------


def _status_error(cls, status: int, message: str):
    req = httpx.Request("POST", "https://example.test/v1/chat/completions")
    return cls(message, response=httpx.Response(status, request=req), body=None)


async def test_openai_auth_error_routes_to_model_auth_error():
    import openai

    frame = await _run_case(_status_error(openai.AuthenticationError, 401, "bad key"))
    assert frame["code"] == "MODEL_AUTH_ERROR"
    assert "Settings" in frame["message"]


async def test_openai_rate_limit_routes_to_model_rate_limited():
    import openai

    frame = await _run_case(_status_error(openai.RateLimitError, 429, "slow down"))
    assert frame["code"] == "MODEL_RATE_LIMITED"
    # A generic 429 keeps the provider-neutral guidance — no Groq/Gemini steer.
    assert "Gemini" not in frame["message"]


async def test_groq_free_tier_tpm_429_recommends_gemini():
    import openai

    # Groq's free-tier 429 body names the per-minute token cap. Because the
    # app's context exceeds that cap, retrying won't help — the message should
    # steer the user to Gemini's roomier free tier instead.
    msg = (
        "Rate limit reached for model `llama-3.1-8b-instant` in organization "
        "`org_x` on tokens per minute (TPM): Limit 6000, Used 5980. Visit "
        "https://console.groq.com to upgrade."
    )
    frame = await _run_case(_status_error(openai.RateLimitError, 429, msg))
    assert frame["code"] == "MODEL_RATE_LIMITED"
    assert "Gemini" in frame["message"]


async def test_context_length_message_routes_to_context_too_long():
    frame = await _run_case(
        _fake_api_error(
            "This model's maximum context length is 131072 tokens, however "
            "you requested 180000 tokens."
        )
    )
    assert frame["code"] == "MODEL_CONTEXT_TOO_LONG"


async def test_not_configured_runtime_error_routes_to_model_auth_error():
    frame = await _run_case(
        RuntimeError(
            "GROQ_API_KEY is not configured — set it in .env or connect "
            "Groq in Settings to route turns to Groq models."
        )
    )
    assert frame["code"] == "MODEL_AUTH_ERROR"
    # The message names the provider so the user knows which key to fix.
    assert "GROQ_API_KEY" in frame["message"]


async def test_genai_client_error_401_routes_to_model_auth_error():
    from google.genai import errors as genai_errors

    exc = genai_errors.ClientError(
        401, {"error": {"message": "API key not valid", "status": "UNAUTHENTICATED"}}
    )
    frame = await _run_case(exc)
    assert frame["code"] == "MODEL_AUTH_ERROR"


async def test_genai_client_error_429_routes_to_model_rate_limited():
    from google.genai import errors as genai_errors

    exc = genai_errors.ClientError(
        429, {"error": {"message": "quota exceeded", "status": "RESOURCE_EXHAUSTED"}}
    )
    frame = await _run_case(exc)
    assert frame["code"] == "MODEL_RATE_LIMITED"


async def test_genai_server_error_routes_to_model_api_error():
    from google.genai import errors as genai_errors

    exc = genai_errors.ServerError(503, {"error": {"message": "overloaded"}})
    frame = await _run_case(exc)
    assert frame["code"] == "MODEL_API_ERROR"


async def test_no_provider_configured_routes_to_dedicated_code():
    # Phase 3 item 18: the model router raises when NO provider has a key at
    # all — distinct from a per-provider auth failure (nothing to retry).
    from app.core.model_router import NoProviderConfiguredError

    frame = await _run_case(
        NoProviderConfiguredError(
            "No LLM provider is configured — Momentum has no API key to run "
            "a model with. Open Settings → Connections and connect Groq, "
            "Google AI, or OpenAI (or set an API key in .env)."
        )
    )
    assert frame["code"] == "NO_PROVIDER_CONFIGURED"
    assert "Settings" in frame["message"]


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
