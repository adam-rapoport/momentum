"""Tests for the bounded retry in app.core.llm.stream_message (Phase 1
item 9, finding A15).

Policy under test: transient provider failures (429 / 5xx / connection
errors) are retried up to len(RETRY_DELAYS) times with backoff — but ONLY
when the stream hasn't yielded anything yet. A partially-yielded stream is
never retried (the caller already surfaced text to the user; re-running the
request would duplicate it). Non-transient errors (auth, 4xx) raise
immediately.
"""
from __future__ import annotations

import httpx
import openai
import pytest
from google.genai import errors as genai_errors

from app.core import llm
from app.core.llm_types import StreamChunk, StreamResult


def _status_error(cls, status: int, message: str):
    req = httpx.Request("POST", "https://example.test/v1/chat/completions")
    return cls(message, response=httpx.Response(status, request=req), body=None)


@pytest.fixture(autouse=True)
def _fast_retries(monkeypatch):
    """Keep the backoff schedule's shape (two retries) but don't sleep."""
    monkeypatch.setattr(llm, "RETRY_DELAYS", (0.0, 0.0))


@pytest.fixture
def dispatch_script(monkeypatch):
    """Replace llm._dispatch with a scripted stand-in. Each entry in
    `script` is either an exception (raised before yielding), a list of
    events to yield, or a tuple (events_then, exception) for the
    partial-stream case."""
    state = {"script": [], "calls": 0}

    async def _fake(messages, model, tools=None, api_key=None):
        state["calls"] += 1
        step = state["script"].pop(0)
        if isinstance(step, BaseException):
            raise step
        if isinstance(step, tuple):
            events, exc = step
            for event in events:
                yield event
            raise exc
        for event in step:
            yield event

    monkeypatch.setattr(llm, "_dispatch", _fake)
    return state


async def _drain() -> list:
    return [
        e
        async for e in llm.stream_message(
            [{"role": "user", "content": "hi"}], model="m"
        )
    ]


async def test_transient_error_before_first_chunk_is_retried(dispatch_script):
    dispatch_script["script"] = [
        _status_error(openai.RateLimitError, 429, "slow down"),
        [StreamChunk(text="ok"), StreamResult(text="ok")],
    ]
    events = await _drain()
    assert dispatch_script["calls"] == 2
    assert [type(e) for e in events] == [StreamChunk, StreamResult]


async def test_5xx_and_connection_errors_are_transient(dispatch_script):
    req = httpx.Request("POST", "https://example.test")
    dispatch_script["script"] = [
        _status_error(openai.InternalServerError, 500, "boom"),
        openai.APIConnectionError(request=req),
        [StreamResult(text="ok")],
    ]
    events = await _drain()
    assert dispatch_script["calls"] == 3  # initial + both retries
    assert isinstance(events[0], StreamResult)


async def test_genai_429_is_transient(dispatch_script):
    dispatch_script["script"] = [
        genai_errors.ClientError(429, {"error": {"message": "quota"}}),
        [StreamResult(text="ok")],
    ]
    await _drain()
    assert dispatch_script["calls"] == 2


async def test_non_transient_error_raises_immediately(dispatch_script):
    dispatch_script["script"] = [
        _status_error(openai.AuthenticationError, 401, "bad key"),
        [StreamResult(text="never reached")],
    ]
    with pytest.raises(openai.AuthenticationError):
        await _drain()
    assert dispatch_script["calls"] == 1


async def test_no_retry_after_partial_stream(dispatch_script):
    """The crucial safety rule: once a chunk reached the caller, a retry
    would duplicate already-streamed text — raise instead."""
    dispatch_script["script"] = [
        ([StreamChunk(text="partial ")], _status_error(openai.RateLimitError, 429, "x")),
        [StreamResult(text="never reached")],
    ]
    with pytest.raises(openai.RateLimitError):
        await _drain()
    assert dispatch_script["calls"] == 1


async def test_retries_are_bounded(dispatch_script):
    dispatch_script["script"] = [
        _status_error(openai.RateLimitError, 429, "1"),
        _status_error(openai.RateLimitError, 429, "2"),
        _status_error(openai.RateLimitError, 429, "3"),
    ]
    with pytest.raises(openai.RateLimitError, match="3"):
        await _drain()
    # initial attempt + len(RETRY_DELAYS) retries, then give up.
    assert dispatch_script["calls"] == 3
