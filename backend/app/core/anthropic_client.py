"""Native Anthropic SDK client for Claude models.

Like Gemini 3.x (app.core.google_genai_client), Claude is served through its
official SDK rather than an OpenAI-compat shim — Anthropic's first-party API
is the documented, full-fidelity path for streaming and tool use.

Contract: `stream_message` yields the same StreamChunk / StreamResult /
ToolCall objects as the other clients, so `app.core.llm` dispatches to either
path transparently.

Translation notes:
  - Anthropic has no system role inside `messages`; system messages are
    collected into the top-level `system` string.
  - Assistant tool calls become `tool_use` content blocks; OpenAI-style
    arguments arrive as a JSON string and Anthropic wants a dict (`input`).
  - Tool results become `tool_result` blocks inside a USER message, and all
    results for one round of (possibly parallel) calls must be grouped into
    the SINGLE next user message — same grouping the genai client does.
  - `thinking` is deliberately not sent (v1 simplicity); the chosen models
    run fine without it.
"""
from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator

from app.config import settings
from app.core.cost_tracker import calculate_cost_usd
from app.core.llm_types import StreamChunk, StreamResult, ToolCall

logger = logging.getLogger(__name__)

try:  # Stay import-safe if the SDK is missing (mirrors google_genai_client).
    import anthropic

    _ANTHROPIC_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only without the SDK
    anthropic = None  # type: ignore[assignment]
    _ANTHROPIC_AVAILABLE = False

# max_tokens caps thinking + visible text together on Opus 5 (thinking is on
# by default there), so 8192 risked truncated answers; every current Claude
# model supports >=64k output, and unused budget costs nothing.
MAX_TOKENS = 16000

# Anthropic stop_reason -> the plain strings the rest of the app expects
# (mirrors what the OpenAI-compat clients emit).
_FINISH_REASONS = {
    "end_turn": "stop",
    "tool_use": "tool_calls",
    "max_tokens": "max_tokens",
    "stop_sequence": "stop",
}

_clients: dict[str, "anthropic.AsyncAnthropic"] = {}


def get_client(api_key: str | None = None) -> "anthropic.AsyncAnthropic":
    if not _ANTHROPIC_AVAILABLE:
        raise RuntimeError(
            "The anthropic SDK is not installed. Run `pip install anthropic` "
            "to use Claude models."
        )
    key = api_key or settings.anthropic_api_key
    if not key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not configured — set it in .env or connect "
            "Anthropic in Settings to route turns to Claude models."
        )
    client = _clients.get(key)
    if client is None:
        client = anthropic.AsyncAnthropic(api_key=key)
        _clients[key] = client
    return client


def _parse_arguments(raw: str | None) -> dict:
    """OpenAI-style JSON-string arguments -> dict for Anthropic's `input`.
    Bad JSON / non-dict values degrade to {} (same guard as the genai client)."""
    try:
        args = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return {}
    return args if isinstance(args, dict) else {}


def _messages_to_anthropic(messages: list[dict]) -> tuple[str | None, list[dict]]:
    """Translate OpenAI-format chat messages into (system, messages).

    - system           -> collected into the top-level system string
    - user             -> {"role": "user", "content": text}
    - assistant text   -> text content block
    - assistant tool   -> tool_use content blocks (arguments parsed to dict)
    - tool result      -> tool_result block; CONSECUTIVE tool results are
                          grouped into ONE user message (parallel calls must
                          all be answered in the single next user turn)
    """
    system_parts: list[str] = []
    out: list[dict] = []
    pending_results: list[dict] = []

    def _flush_results() -> None:
        if pending_results:
            out.append({"role": "user", "content": list(pending_results)})
            pending_results.clear()

    for msg in messages:
        role = msg.get("role")
        if role != "tool":
            _flush_results()

        if role == "system":
            content = msg.get("content")
            if content:
                system_parts.append(content)

        elif role == "user":
            out.append({"role": "user", "content": msg.get("content") or ""})

        elif role == "assistant":
            blocks: list[dict] = []
            text = msg.get("content")
            if text:
                blocks.append({"type": "text", "text": text})
            for tc in msg.get("tool_calls") or []:
                fn = tc.get("function", {})
                blocks.append(
                    {
                        "type": "tool_use",
                        "id": tc.get("id", ""),
                        "name": fn.get("name", ""),
                        "input": _parse_arguments(fn.get("arguments")),
                    }
                )
            if blocks:
                out.append({"role": "assistant", "content": blocks})

        elif role == "tool":
            pending_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": msg.get("tool_call_id", ""),
                    "content": msg.get("content") or "",
                }
            )

    _flush_results()
    system = "\n\n".join(system_parts) if system_parts else None
    return system, out


def _tools_to_anthropic(tools: list[dict] | None) -> list[dict] | None:
    """OpenAI function-format tools -> Anthropic {name, description,
    input_schema} specs."""
    if not tools:
        return None
    out = []
    for t in tools:
        fn = t.get("function", t)
        out.append(
            {
                "name": fn.get("name", ""),
                "description": fn.get("description", ""),
                "input_schema": fn.get("parameters")
                or {"type": "object", "properties": {}},
            }
        )
    return out


async def stream_message(
    messages: list[dict],
    model: str,
    tools: list[dict] | None = None,
    api_key: str | None = None,
) -> AsyncIterator[StreamChunk | StreamResult]:
    """Stream a chat completion from Anthropic. Same contract as
    `groq_client.stream_message`."""
    client = get_client(api_key)
    system, converted = _messages_to_anthropic(messages)
    anthropic_tools = _tools_to_anthropic(tools)

    kwargs: dict = {
        "model": model,
        "max_tokens": MAX_TOKENS,
        "messages": converted,
    }
    if system:
        kwargs["system"] = system
    if anthropic_tools:
        kwargs["tools"] = anthropic_tools

    collected: list[str] = []
    async with client.messages.stream(**kwargs) as stream:
        async for text in stream.text_stream:
            collected.append(text)
            yield StreamChunk(text=text)
        final = await stream.get_final_message()

    tool_calls = [
        ToolCall(
            id=block.id,
            name=block.name,
            arguments_json=json.dumps(block.input or {}),
        )
        for block in final.content
        if getattr(block, "type", None) == "tool_use"
    ]

    raw_stop = final.stop_reason or ""
    finish_reason = _FINISH_REASONS.get(raw_stop, raw_stop or None)
    if finish_reason not in ("stop", "tool_calls", "max_tokens", None):
        logger.warning(
            "anthropic stream ended with stop_reason=%s (model=%s)",
            raw_stop, model,
        )

    input_tokens = final.usage.input_tokens or 0
    output_tokens = final.usage.output_tokens or 0
    yield StreamResult(
        text="".join(collected),
        tool_calls=tool_calls,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=calculate_cost_usd(model, input_tokens, output_tokens),
        finish_reason=finish_reason,
    )
