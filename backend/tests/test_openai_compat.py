"""Tests for the shared OpenAI-compatible streaming loop (Phase 3 item 18,
finding A31) and the provider shims layered on it.

The loop used to be triplicated across groq/openai/google clients; these
tests pin the single copy's behavior — text deltas, tool-call accumulation,
usage/cost — against a scripted fake AsyncOpenAI client, plus the Google
shim's thought-stripper wrapper.
"""
from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

from app.core import google_client, openai_compat
from app.core.llm_types import StreamChunk, StreamResult


def _chunk(
    *,
    content: str | None = None,
    tool_calls: list | None = None,
    finish_reason: str | None = None,
    usage: SimpleNamespace | None = None,
) -> SimpleNamespace:
    """Build a fake ChatCompletionChunk with the attributes the loop reads."""
    choices = []
    if content is not None or tool_calls is not None or finish_reason is not None:
        choices.append(
            SimpleNamespace(
                delta=SimpleNamespace(content=content, tool_calls=tool_calls),
                finish_reason=finish_reason,
            )
        )
    return SimpleNamespace(choices=choices, usage=usage)


def _tc_delta(index: int, id: str | None, name: str | None, arguments: str | None):
    return SimpleNamespace(
        index=index,
        id=id,
        function=SimpleNamespace(name=name, arguments=arguments),
    )


class _FakeClient:
    """Stands in for AsyncOpenAI: records the request kwargs and streams a
    scripted chunk sequence."""

    def __init__(self, chunks: list) -> None:
        self.kwargs: dict | None = None

        async def create(**kwargs):
            self.kwargs = kwargs

            async def _iter():
                for c in chunks:
                    yield c

            return _iter()

        self.chat = SimpleNamespace(completions=SimpleNamespace(create=create))


async def _drain(client, model: str, tools=None) -> list:
    return [
        e
        async for e in openai_compat.stream_chat(
            client, [{"role": "user", "content": "hi"}], model=model, tools=tools
        )
    ]


async def test_text_deltas_stream_then_final_result():
    client = _FakeClient(
        [
            _chunk(content="Hello "),
            _chunk(content="world"),
            _chunk(finish_reason="stop"),
        ]
    )
    events = await _drain(client, "llama-3.1-8b-instant")
    assert [type(e) for e in events] == [StreamChunk, StreamChunk, StreamResult]
    assert events[0].text == "Hello "
    result = events[-1]
    assert result.text == "Hello world"
    assert result.finish_reason == "stop"
    assert result.tool_calls == []


async def test_tool_call_deltas_accumulate_across_chunks():
    client = _FakeClient(
        [
            _chunk(tool_calls=[_tc_delta(0, "call_a", "get_weather", '{"city":')]),
            _chunk(tool_calls=[_tc_delta(0, None, None, ' "Paris"}')]),
            # Second parallel call arrives interleaved at index 1.
            _chunk(tool_calls=[_tc_delta(1, "call_b", "get_time", "{}")]),
            # Malformed delta with no name ever — must be dropped.
            _chunk(tool_calls=[_tc_delta(2, "call_c", None, '{"x": 1}')]),
            _chunk(finish_reason="tool_calls"),
        ]
    )
    events = await _drain(client, "llama-3.1-8b-instant")
    result = events[-1]
    assert isinstance(result, StreamResult)
    assert [(tc.id, tc.name, tc.arguments_json) for tc in result.tool_calls] == [
        ("call_a", "get_weather", '{"city": "Paris"}'),
        ("call_b", "get_time", "{}"),
    ]
    assert result.finish_reason == "tool_calls"


async def test_usage_chunk_sets_tokens_and_cost():
    usage = SimpleNamespace(prompt_tokens=1_000_000, completion_tokens=1_000_000)
    client = _FakeClient([_chunk(content="x"), _chunk(usage=usage)])
    events = await _drain(client, "llama-3.1-8b-instant")
    result = events[-1]
    assert result.input_tokens == 1_000_000
    assert result.output_tokens == 1_000_000
    # llama-3.1-8b-instant is $0.05/$0.08 per MTok.
    assert result.cost_usd == Decimal("0.13")


async def test_none_usage_fields_default_to_zero():
    # Groq can omit individual usage fields (None) on some responses.
    usage = SimpleNamespace(prompt_tokens=None, completion_tokens=None)
    client = _FakeClient([_chunk(usage=usage)])
    result = (await _drain(client, "llama-3.1-8b-instant"))[-1]
    assert result.input_tokens == 0
    assert result.output_tokens == 0
    assert result.cost_usd == Decimal("0")


async def test_thought_signatures_stripped_from_outbound_messages():
    # The Gemini-only key threaded through history (item 19) must never hit an
    # OpenAI-compat wire — strict providers could 400 on it.
    client = _FakeClient([_chunk(finish_reason="stop")])
    messages = [
        {"role": "user", "content": "hi"},
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "c1",
                    "type": "function",
                    "function": {"name": "t", "arguments": "{}"},
                    "thought_signature": "b64sig",
                }
            ],
        },
        {"role": "tool", "tool_call_id": "c1", "content": "ok"},
    ]
    events = [
        e async for e in openai_compat.stream_chat(client, messages, model="m")
    ]
    assert events  # stream ran
    sent = client.kwargs["messages"]
    assert "thought_signature" not in sent[1]["tool_calls"][0]
    # The original tool_call dict (engine state) is NOT mutated.
    assert messages[1]["tool_calls"][0]["thought_signature"] == "b64sig"


async def test_tools_forwarded_with_auto_tool_choice():
    client = _FakeClient([_chunk(finish_reason="stop")])
    tools = [{"type": "function", "function": {"name": "t", "parameters": {}}}]
    await _drain(client, "m", tools=tools)
    assert client.kwargs["tools"] == tools
    assert client.kwargs["tool_choice"] == "auto"
    assert client.kwargs["stream"] is True

    client2 = _FakeClient([_chunk(finish_reason="stop")])
    await _drain(client2, "m", tools=None)
    assert "tools" not in client2.kwargs


# ---- the Google shim's quirk wrappers ---------------------------------------


async def test_gemma_thought_blocks_stripped_by_google_shim(monkeypatch):
    client = _FakeClient(
        [
            _chunk(content="<thought>internal reasoning"),
            _chunk(content=" continues</thought>The answer "),
            _chunk(content="is 4."),
            _chunk(finish_reason="stop"),
        ]
    )
    monkeypatch.setattr(google_client, "get_client", lambda api_key=None: client)
    events = [
        e
        async for e in google_client.stream_message(
            [{"role": "user", "content": "2+2?"}], model="gemma-4-31b-it"
        )
    ]
    chunks = [e.text for e in events if isinstance(e, StreamChunk)]
    result = events[-1]
    assert isinstance(result, StreamResult)
    # No thought text reaches the caller, and StreamResult.text matches what
    # was actually streamed (the filtered text), not the raw wire text.
    assert "internal reasoning" not in "".join(chunks)
    assert "".join(chunks) == "The answer is 4."
    assert result.text == "The answer is 4."


async def test_non_gemma_google_models_pass_through_unstripped(monkeypatch):
    client = _FakeClient(
        [_chunk(content="<thought>not stripped for gemini</thought>ok"), _chunk(finish_reason="stop")]
    )
    monkeypatch.setattr(google_client, "get_client", lambda api_key=None: client)
    events = [
        e
        async for e in google_client.stream_message(
            [{"role": "user", "content": "hi"}], model="gemini-3.5-flash"
        )
    ]
    result = events[-1]
    assert result.text == "<thought>not stripped for gemini</thought>ok"


def test_groq_client_reexports_shared_types():
    # The harness (and any older caller) imports the stream types from
    # groq_client; they must be the SAME objects as app.core.llm_types.
    from app.core import groq_client, llm_types

    assert groq_client.StreamChunk is llm_types.StreamChunk
    assert groq_client.StreamResult is llm_types.StreamResult
    assert groq_client.ToolCall is llm_types.ToolCall
