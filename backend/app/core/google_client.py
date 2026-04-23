"""Thin wrapper around Google AI Studio's OpenAI-compatible endpoint.

Google exposes Gemini + Gemma models at
https://generativelanguage.googleapis.com/v1beta/openai/ which speaks the
OpenAI Chat Completions API. We reuse the `openai` SDK with a custom
`base_url` — same pattern as `groq_client.py`.

Kept as a separate module (rather than folded into `groq_client`) so that
provider-specific quirks (e.g. Google's handling of `stream_options` or
usage reporting) can be patched without risking the Groq path.
"""
from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from decimal import Decimal

from openai import AsyncOpenAI

from app.config import settings
from app.core.cost_tracker import calculate_cost_usd
from app.core.groq_client import StreamChunk, StreamResult, ToolCall

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


_client: AsyncOpenAI | None = None


def get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        if not settings.google_ai_api_key:
            raise RuntimeError(
                "GOOGLE_AI_API_KEY is not configured — set it in .env to "
                "route turns to Google-hosted models."
            )
        _client = AsyncOpenAI(
            api_key=settings.google_ai_api_key,
            base_url=GOOGLE_BASE_URL,
        )
    return _client


async def stream_message(
    messages: list[dict],
    model: str,
    tools: list[dict] | None = None,
) -> AsyncIterator[StreamChunk | StreamResult]:
    """Stream a chat completion from Google AI Studio. Same contract as
    `groq_client.stream_message` — yields StreamChunks for text deltas,
    then a StreamResult with text, tool calls, usage, and cost.
    """
    client = get_client()

    request_kwargs: dict = {
        "model": model,
        "messages": messages,
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    if tools:
        request_kwargs["tools"] = tools
        request_kwargs["tool_choice"] = "auto"
    # NOTE: we deliberately do NOT set `parallel_tool_calls: False` here.
    # The OpenAI-compat shim still merges Gemini's parallel calls into
    # concatenated JSON regardless of that flag, and setting it seems to
    # cause truncated mid-stream terminations on follow-up turns. The
    # session engine has a salvage path in `_split_concatenated_json_args`
    # that handles the concatenation-on-parse case instead.

    stream = await client.chat.completions.create(**request_kwargs)

    collected_text: list[str] = []
    tool_calls_by_index: dict[int, dict] = {}
    input_tokens = 0
    output_tokens = 0
    finish_reason: str | None = None
    # Only Gemma emits visible <thought> blocks; skip the overhead for other
    # Google models (Gemini).
    stripper = _ThoughtStripper() if model.startswith("gemma-") else None

    async for chunk in stream:
        if chunk.choices:
            choice = chunk.choices[0]
            delta = choice.delta
            if delta and delta.content:
                content = delta.content
                if stripper is not None:
                    content = stripper.feed(content)
                if content:
                    collected_text.append(content)
                    yield StreamChunk(text=content)
            if delta and getattr(delta, "tool_calls", None):
                for tc_delta in delta.tool_calls:
                    idx = tc_delta.index
                    slot = tool_calls_by_index.setdefault(
                        idx, {"id": None, "name": None, "arguments": ""}
                    )
                    if tc_delta.id:
                        slot["id"] = tc_delta.id
                    fn = getattr(tc_delta, "function", None)
                    if fn:
                        if fn.name:
                            slot["name"] = fn.name
                        if fn.arguments:
                            slot["arguments"] += fn.arguments
            if choice.finish_reason:
                finish_reason = choice.finish_reason
        # Google reports usage in the final chunk (same as Groq/OpenAI when
        # stream_options.include_usage is set). Guard the attribute access
        # in case a provider-side change stops sending it.
        if getattr(chunk, "usage", None):
            input_tokens = chunk.usage.prompt_tokens or 0
            output_tokens = chunk.usage.completion_tokens or 0

    # Flush any held-back text after the stream ends.
    if stripper is not None:
        tail = stripper.flush()
        if tail:
            collected_text.append(tail)
            yield StreamChunk(text=tail)

    full_text = "".join(collected_text)
    tool_calls = [
        ToolCall(
            id=slot["id"] or "",
            name=slot["name"] or "",
            arguments_json=slot["arguments"],
        )
        for _, slot in sorted(tool_calls_by_index.items())
        if slot["name"]  # drop malformed deltas with no name
    ]

    # Mid-stream truncations (finish_reason=length, content_filter, malformed)
    # are silent on the wire; log them so we can diagnose skill-flow breaks.
    if finish_reason not in ("stop", "tool_calls", None):
        logger.warning(
            "google stream ended with finish_reason=%s (model=%s, text_len=%d, "
            "tool_calls=%d)",
            finish_reason, model, len(full_text), len(tool_calls),
        )

    yield StreamResult(
        text=full_text,
        tool_calls=tool_calls,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=calculate_cost_usd(model, input_tokens, output_tokens),
        finish_reason=finish_reason,
    )
