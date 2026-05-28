"""Thin wrapper around the OpenAI SDK pointed at OpenAI itself.

Unlike `groq_client` and `google_client` (which aim the `openai` SDK at a
different provider's base URL), this talks to OpenAI's own API at
https://api.openai.com/v1 with the user's OpenAI key. Same streaming
contract as the other providers so `app.core.llm` can dispatch to it
transparently. Paid provider — the key needs billing enabled.
"""
from __future__ import annotations

from collections.abc import AsyncIterator

from openai import AsyncOpenAI

from app.config import settings
from app.core.cost_tracker import calculate_cost_usd
from app.core.groq_client import StreamChunk, StreamResult, ToolCall

# Clients are cached by API key so per-user keys (from the Connections UI)
# each get their own reused client.
_clients: dict[str, AsyncOpenAI] = {}


def get_client(api_key: str | None = None) -> AsyncOpenAI:
    key = api_key or settings.openai_api_key
    if not key:
        raise RuntimeError(
            "OPENAI_API_KEY is not configured — set it in .env or connect "
            "OpenAI in Settings to route turns to OpenAI models."
        )
    client = _clients.get(key)
    if client is None:
        client = AsyncOpenAI(api_key=key)
        _clients[key] = client
    return client


async def stream_message(
    messages: list[dict],
    model: str,
    tools: list[dict] | None = None,
    api_key: str | None = None,
) -> AsyncIterator[StreamChunk | StreamResult]:
    """Stream a chat completion from OpenAI. Same contract as
    `groq_client.stream_message` — yields StreamChunks for text deltas, then
    a final StreamResult with text, tool calls, usage, and cost.
    """
    client = get_client(api_key)

    request_kwargs: dict = {
        "model": model,
        "messages": messages,
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    if tools:
        request_kwargs["tools"] = tools
        request_kwargs["tool_choice"] = "auto"

    stream = await client.chat.completions.create(**request_kwargs)

    collected_text: list[str] = []
    tool_calls_by_index: dict[int, dict] = {}
    input_tokens = 0
    output_tokens = 0
    finish_reason: str | None = None

    async for chunk in stream:
        if chunk.choices:
            choice = chunk.choices[0]
            delta = choice.delta
            if delta and delta.content:
                collected_text.append(delta.content)
                yield StreamChunk(text=delta.content)
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
        if getattr(chunk, "usage", None):
            input_tokens = chunk.usage.prompt_tokens or 0
            output_tokens = chunk.usage.completion_tokens or 0

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

    yield StreamResult(
        text=full_text,
        tool_calls=tool_calls,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=calculate_cost_usd(model, input_tokens, output_tokens),
        finish_reason=finish_reason,
    )
