"""Thin configuration shim pointing the shared OpenAI-compat streaming
implementation (app.core.openai_compat) at Google AI Studio.

Google exposes Gemini + Gemma models at
https://generativelanguage.googleapis.com/v1beta/openai/ which speaks the
OpenAI Chat Completions API. We reuse the `openai` SDK with a custom
`base_url` — same pattern as `groq_client.py`.

Two Google-specific quirks live here, as wrappers around the shared stream:
  - Gemma emits chain-of-thought wrapped in `<thought>...</thought>` tags
    directly in its text stream; `_ThoughtStripper` removes them in-flight.
  - Mid-stream truncations (finish_reason=length / content_filter) are
    silent on the wire; we log them to diagnose skill-flow breaks.

NOTE: we deliberately do NOT set `parallel_tool_calls: False` on requests.
The OpenAI-compat shim still merges Gemini's parallel calls into
concatenated JSON regardless of that flag, and setting it seems to cause
truncated mid-stream terminations on follow-up turns. The session engine
has a salvage path in `_split_concatenated_json_args` that handles the
concatenation-on-parse case instead.
"""
from __future__ import annotations

import logging
from collections.abc import AsyncIterator

from openai import AsyncOpenAI

from app.config import settings
from app.core.llm_types import StreamChunk, StreamResult
from app.core.openai_compat import stream_chat

logger = logging.getLogger(__name__)

GOOGLE_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"

# Gemma 4 emits chain-of-thought reasoning wrapped in `<thought>...</thought>`
# tags, directly in its text stream. These should not reach the UI — they're
# noisy, long, and confusing to users. We strip them in-flight below.
_THOUGHT_OPEN = "<thought>"
_THOUGHT_CLOSE = "</thought>"


class _ThoughtStripper:
    """Streaming filter that removes <thought>...</thought> blocks.

    Safe across chunk boundaries: holds back any text that might be a partial
    tag until it can decide whether to yield or suppress it.
    """

    def __init__(self) -> None:
        self._buffer = ""
        self._inside = False

    def feed(self, chunk: str) -> str:
        if not chunk:
            return ""
        self._buffer += chunk
        out: list[str] = []
        while True:
            if self._inside:
                idx = self._buffer.find(_THOUGHT_CLOSE)
                if idx < 0:
                    # No close tag yet; consume nothing but drop almost
                    # everything. Keep only the trailing chars that could
                    # be a partial close tag.
                    self._buffer = self._buffer[-(len(_THOUGHT_CLOSE) - 1):]
                    break
                # Found close tag — drop everything up to + including it.
                self._buffer = self._buffer[idx + len(_THOUGHT_CLOSE):]
                self._inside = False
            else:
                idx = self._buffer.find(_THOUGHT_OPEN)
                if idx < 0:
                    # No open tag at all — yield everything except what
                    # might be a partial open tag at the end.
                    last_lt = self._buffer.rfind("<")
                    if last_lt >= 0 and _THOUGHT_OPEN.startswith(self._buffer[last_lt:]):
                        out.append(self._buffer[:last_lt])
                        self._buffer = self._buffer[last_lt:]
                    else:
                        out.append(self._buffer)
                        self._buffer = ""
                    break
                out.append(self._buffer[:idx])
                self._buffer = self._buffer[idx + len(_THOUGHT_OPEN):]
                self._inside = True
        return "".join(out)

    def flush(self) -> str:
        """Called at end of stream. If we're still inside a thought block,
        drop the remaining buffer. Otherwise return any held content."""
        if self._inside:
            self._buffer = ""
            return ""
        result = self._buffer
        self._buffer = ""
        return result


# Clients are cached by API key so per-user keys (from the Connections UI /
# C8) each get their own reused client. `api_key=None` falls back to the env
# default, preserving the original behavior.
_clients: dict[str, AsyncOpenAI] = {}


def get_client(api_key: str | None = None) -> AsyncOpenAI:
    key = api_key or settings.google_ai_api_key
    if not key:
        raise RuntimeError(
            "GOOGLE_AI_API_KEY is not configured — set it in .env or connect "
            "Google in Settings to route turns to Google-hosted models."
        )
    client = _clients.get(key)
    if client is None:
        client = AsyncOpenAI(api_key=key, base_url=GOOGLE_BASE_URL)
        _clients[key] = client
    return client


async def stream_message(
    messages: list[dict],
    model: str,
    tools: list[dict] | None = None,
    api_key: str | None = None,
) -> AsyncIterator[StreamChunk | StreamResult]:
    """Stream a chat completion from Google AI Studio. Same contract as
    `groq_client.stream_message` — the shared loop, wrapped with the Gemma
    thought-stripper and abnormal-finish logging (see module docstring).
    """
    # Only Gemma emits visible <thought> blocks; skip the overhead for other
    # Google models (Gemini).
    stripper = _ThoughtStripper() if model.startswith("gemma-") else None
    # Text that actually passed the stripper — StreamResult.text must match
    # what the caller saw, not the raw stream with thought blocks in it.
    filtered_text: list[str] = []

    inner = stream_chat(get_client(api_key), messages, model=model, tools=tools)
    try:
        async for event in inner:
            if isinstance(event, StreamChunk):
                if stripper is None:
                    yield event
                    continue
                text = stripper.feed(event.text)
                if text:
                    filtered_text.append(text)
                    yield StreamChunk(text=text)
                continue

            # StreamResult — flush any held-back text first.
            if stripper is not None:
                tail = stripper.flush()
                if tail:
                    filtered_text.append(tail)
                    yield StreamChunk(text=tail)
                event.text = "".join(filtered_text)

            # Mid-stream truncations (finish_reason=length, content_filter,
            # malformed) are silent on the wire; log them so we can diagnose
            # skill-flow breaks.
            if event.finish_reason not in ("stop", "tool_calls", None):
                logger.warning(
                    "google stream ended with finish_reason=%s (model=%s, "
                    "text_len=%d, tool_calls=%d)",
                    event.finish_reason, model, len(event.text),
                    len(event.tool_calls),
                )
            yield event
    finally:
        # Deterministic close so a consumer that bails early can't leave a
        # dangling HTTP stream behind the shared generator.
        await inner.aclose()
