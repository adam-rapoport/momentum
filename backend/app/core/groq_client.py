"""Thin wrapper around the OpenAI SDK pointed at Groq.

Groq serves the OpenAI Chat Completions API at https://api.groq.com/openai/v1.
Using the official `openai` SDK with a custom `base_url` is the documented path.
"""
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from decimal import Decimal

from openai import AsyncOpenAI

from app.config import settings
from app.core.cost_tracker import calculate_cost_usd


@dataclass
class StreamChunk:
    text: str


@dataclass
class ToolCall:
    """A tool call requested by the LLM. `arguments_json` is a raw JSON string
    as emitted by the model — we leave parsing to the caller so we don't
    choke a whole stream on one bad call.
    """
    id: str
    name: str
    arguments_json: str


@dataclass
class StreamResult:
    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: Decimal = Decimal("0")
    finish_reason: str | None = None


# Clients are cached by API key so that per-user keys (from the Connections
# UI / C8) each get their own reused client. When `api_key` is None we fall
# back to the env default — that path is byte-for-byte the old behavior.
_clients: dict[str, AsyncOpenAI] = {}


def get_client(api_key: str | None = None) -> AsyncOpenAI:
    key = api_key or settings.groq_api_key
    if not key:
        # Mirror openai_client / google_client: a clear, correct message instead
        # of AsyncOpenAI(api_key=None) raising about the wrong (OPENAI) env var.
        raise RuntimeError(
            "GROQ_API_KEY is not configured — set it in .env or connect "
            "Groq in Settings to route turns to Groq models."
        )
    client = _clients.get(key)
    if client is None:
        client = AsyncOpenAI(api_key=key, base_url=settings.groq_base_url)
        _clients[key] = client
    return client


async def stream_message(
    messages: list[dict],
    model: str | None = None,
    tools: list[dict] | None = None,
    api_key: str | None = None,
) -> AsyncIterator[StreamChunk | StreamResult]:
    """Stream a chat completion. Yields StreamChunks for each text delta,
    then a final StreamResult with text, tool calls, usage, and cost.

    Tool calls arrive as streamed deltas; we accumulate them in-flight and
    only surface the assembled list on the StreamResult at the end.
    """
    model = model or settings.groq_model
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
        if chunk.usage:
            # Groq can omit individual usage fields (None) on some responses;
            # Decimal(None) in calculate_cost_usd would kill the turn.
            input_tokens = chunk.usage.prompt_tokens or 0
            output_tokens = chunk.usage.completion_tokens or 0

    full_text = "".join(collected_text)
    tool_calls = [
        ToolCall(id=slot["id"] or "", name=slot["name"] or "", arguments_json=slot["arguments"])
        for _, slot in sorted(tool_calls_by_index.items())
        if slot["name"]  # drop malformed calls with no name
    ]

    yield StreamResult(
        text=full_text,
        tool_calls=tool_calls,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=calculate_cost_usd(model, input_tokens, output_tokens),
        finish_reason=finish_reason,
    )
