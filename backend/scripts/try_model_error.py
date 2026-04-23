"""Smoke test: simulate Groq rejecting a turn with tool_use_failed and
verify the WebSocket handler surfaces the new MODEL_TOOL_CALL_FAILED
error (not a generic INTERNAL_ERROR) so the Next.js dev overlay stays
quiet and the frontend can render the inline amber banner.

Doesn't hit Groq. Patches `process_message` to raise a fake
`openai.APIError` and captures every `send_json` call on a mock
WebSocket.

Usage:
  .venv/bin/python -m scripts.try_model_error
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
from openai import APIError

from app.api.websocket import _handle_user_message


class FakeWebSocket:
    """Minimal stand-in for `fastapi.WebSocket.send_json`."""

    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def send_json(self, payload: dict) -> None:
        self.sent.append(payload)


def _fake_api_error(message: str) -> APIError:
    req = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    return APIError(message, request=req, body=None)


def _fake_process_message_raising(exc: BaseException):
    """Return a function matching process_message's signature that raises
    the given exception on first iteration."""

    async def inner(**_kwargs):
        # Process message is an async generator; an immediate raise is enough.
        if False:
            yield  # pragma: no cover — pretend this is an async generator
        raise exc

    return inner


async def run_case(description: str, exc: BaseException, expected_code: str) -> None:
    print(f"\n== {description} ==")
    print(f"  simulated exc: {exc!r}")

    # Patch the session engine's process_message entry point used by the WS.
    fake = _fake_process_message_raising(exc)
    with patch("app.api.websocket.process_message", new=fake):
        ws = FakeWebSocket()
        await _handle_user_message(
            ws,  # type: ignore[arg-type]
            uuid4(),
            "doesn't matter — the patched generator raises immediately.",
        )

    if not ws.sent:
        print("  FAIL — WebSocket received no frame")
        raise AssertionError("no frame emitted")
    frame = ws.sent[0]
    code = frame.get("code")
    msg = frame.get("message", "")
    marker = "ok" if code == expected_code else "FAIL"
    print(f"  [{marker}] frame.code = {code!r} (expected {expected_code!r})")
    print(f"  frame.message[:90] = {msg[:90]!r}")
    assert code == expected_code


async def main() -> None:
    from app.core.session_engine import CommitFailedError

    # 1. The real-world Groq rejection message from our failed turn.
    await run_case(
        "tool_use_failed — Groq's 'Failed to call a function'",
        _fake_api_error(
            "Failed to call a function. Please adjust your prompt. See 'failed_generation' for more details."
        ),
        "MODEL_TOOL_CALL_FAILED",
    )

    # 2. Alternative phrasings that should also route to the tool-call bucket.
    await run_case(
        "tool_use_failed — literal 'tool_use_failed' substring",
        _fake_api_error("tool_use_failed: invalid function call"),
        "MODEL_TOOL_CALL_FAILED",
    )

    # 3. A non-tool-call APIError should fall into the generic model-service bucket.
    await run_case(
        "generic model-service failure (rate limit / 503)",
        _fake_api_error("Service temporarily unavailable"),
        "MODEL_API_ERROR",
    )

    # 4. A DB commit failure (Chunk B) should surface as DB_ERROR.
    await run_case(
        "db commit failure at persist_user_message stage",
        CommitFailedError("persist_user_message", RuntimeError("connection reset")),
        "DB_ERROR",
    )

    print("\nAll error-handling cases passed.")


if __name__ == "__main__":
    asyncio.run(main())
