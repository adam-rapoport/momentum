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


def _strip_thought_signatures(messages: list[dict]) -> list[dict]:
    """Drop the Gemini-only `thought_signature` key from assistant tool_calls.

    The session engine threads it through OpenAI-format history so the native
    google-genai client can replay it (item 19); it is NOT part of the Chat
    Completions wire format and a strict provider could 400 on it (reachable
    when the user switches a session from a Gemini 3.x model to any
    OpenAI-compat one). Copies only what it touches.
    """
    cleaned = None
    for i, msg in enumerate(messages):
        if msg.get("role") != "assistant":
            continue
        if not any("thought_signature" in tc for tc in msg.get("tool_calls") or []):
            continue
        if cleaned is None:
            cleaned = list(messages)
        cleaned[i] = {
            **msg,
            "tool_calls": [
                {k: v for k, v in tc.items() if k != "thought_signature"}
                for tc in msg["tool_calls"]
            ],
        }
    return cleaned if cleaned is not None else messages


def _delta_text(content: object) -> str:
    """The user-visible text carried by one streamed delta's `content`.

    Almost every provider sends a plain string. Mistral's reasoning models
    (Mistral Large 4, verified live 2026-11-11) instead send a LIST of typed
    parts on the same Chat Completions wire: `{"type": "thinking", ...}` for
    the model's reasoning and `{"type": "text", "text": ...}` for the answer,
    sometimes both in one delta. Appending that list to the text buffer used
    to kill the turn ("expected str instance, list found").

    Keep the text parts and drop the reasoning — the same treatment Gemma's
    `<thought>` blocks get in google_client: reasoning is never shown to the
    user or stored in history. Anything unrecognised yields "" rather than
    raising, so a new part type degrades to missing text, not a dead turn.
    """
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for part in content:
        if isinstance(part, str):
            parts.append(part)
            continue
        if isinstance(part, dict):
            kind, text = part.get("type"), part.get("text")
        else:  # SDK may hand back typed objects instead of dicts
            kind, text = getattr(part, "type", None), getattr(part, "text", None)
        if kind == "text" and isinstance(text, str):
            parts.append(text)
    return "".join(parts)


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
        "messages": _strip_thought_signatures(messages),
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
                text = _delta_text(delta.content)
                if text:
                    collected_text.append(text)
                    yield StreamChunk(text=text)
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
