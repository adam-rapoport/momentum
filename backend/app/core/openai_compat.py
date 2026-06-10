"""Shared OpenAI-compatible chat-completion streaming implementation.

Groq, OpenAI, and Google's OpenAI-compat endpoint all speak the same Chat
Completions streaming wire format. The delta-accumulation loop below used to
be triplicated across `groq_client` / `openai_client` / `google_client` and
was already diverging (finding A31) — this is now the single copy.

The provider modules are thin configuration shims: each resolves its API key
(stored or env), builds/caches an `AsyncOpenAI` client with its base_url, and
delegates here. Provider quirks stay in the shims — `google_client` wraps
this stream with the Gemma `<thought>`-stripper and abnormal-finish logging.
The native google-genai SDK path (`google_genai_client`) is the only client
that doesn't go through this module.
"""
from __future__ import annotations

from collections.abc import AsyncIterator

from openai import AsyncOpenAI

from app.core.cost_tracker import calculate_cost_usd
from app.core.llm_types import StreamChunk, StreamResult, ToolCall


async def stream_chat(
    client: AsyncOpenAI,
    messages: list[dict],
    model: str,
    tools: list[dict] | None = None,
) -> AsyncIterator[StreamChunk | StreamResult]:
    """Stream a chat completion. Yields StreamChunks for each text delta,
    then a final StreamResult with text, tool calls, usage, and cost.

    Tool calls arrive as streamed deltas; we accumulate them in-flight and
    only surface the assembled list on the StreamResult at the end.
    """
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
    # tool calls arrive as deltas keyed by index — accumulate name + arg chunks
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
        # Usage lands in the final chunk when stream_options.include_usage is
        # set. Guard the attribute access (a provider-side change must not
        # crash the loop) AND the individual fields — Groq can omit them
        # (None), and Decimal(None) in calculate_cost_usd would kill the turn.
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
