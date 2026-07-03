"""Unit tests for the native Anthropic client's translation + streaming layer.

Mirrors tests/test_google_genai_client.py: the message/tool translators are
pure functions over plain dicts, and the streaming path runs against a fake
SDK client — no network anywhere.
"""
from __future__ import annotations

import json
from contextlib import asynccontextmanager
from decimal import Decimal
from types import SimpleNamespace

import pytest

pytest.importorskip("anthropic")

from app.core import anthropic_client as a  # noqa: E402
from app.core.llm_types import StreamChunk, StreamResult  # noqa: E402

WEATHER_TOOL = {
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "Get the weather for a city.",
        "parameters": {
            "type": "object",
            "properties": {"city": {"type": "string"}},
            "required": ["city"],
            "additionalProperties": False,
        },
    },
}


def test_tools_to_anthropic_handles_empty():
    assert a._tools_to_anthropic(None) is None
    assert a._tools_to_anthropic([]) is None


def test_tools_to_anthropic_converts_function_format():
    tools = a._tools_to_anthropic([WEATHER_TOOL])
    assert tools == [
        {
            "name": "get_weather",
            "description": "Get the weather for a city.",
            "input_schema": WEATHER_TOOL["function"]["parameters"],
        }
    ]


def test_tools_to_anthropic_defaults_missing_parameters():
    tools = a._tools_to_anthropic(
        [{"type": "function", "function": {"name": "noop", "description": ""}}]
    )
    assert tools[0]["input_schema"] == {"type": "object", "properties": {}}


def test_system_messages_collected_into_system_string():
    system, messages = a._messages_to_anthropic(
        [
            {"role": "system", "content": "Be terse."},
            {"role": "system", "content": "Use tools."},
            {"role": "user", "content": "hi"},
        ]
    )
    assert system == "Be terse.\n\nUse tools."
    assert messages == [{"role": "user", "content": "hi"}]


def test_assistant_tool_calls_become_tool_use_blocks():
    _system, messages = a._messages_to_anthropic(
        [
            {"role": "user", "content": "weather in Paris?"},
            {
                "role": "assistant",
                "content": "Checking.",
                "tool_calls": [
                    {
                        "id": "call_abc",
                        "type": "function",
                        "function": {
                            "name": "get_weather",
                            "arguments": '{"city": "Paris"}',
                        },
                    }
                ],
            },
            {"role": "tool", "tool_call_id": "call_abc", "content": "14C"},
        ]
    )
    assert messages[1]["role"] == "assistant"
    assert messages[1]["content"] == [
        {"type": "text", "text": "Checking."},
        {
            "type": "tool_use",
            "id": "call_abc",
            "name": "get_weather",
            "input": {"city": "Paris"},
        },
    ]
    assert messages[2] == {
        "role": "user",
        "content": [
            {"type": "tool_result", "tool_use_id": "call_abc", "content": "14C"}
        ],
    }


def test_parallel_tool_results_grouped_into_one_user_message():
    # Anthropic requires every parallel call's result in the SINGLE next user
    # message — same grouping contract as the genai client.
    _system, messages = a._messages_to_anthropic(
        [
            {"role": "user", "content": "weather in Paris and London?"},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "get_weather", "arguments": '{"city": "Paris"}'},
                    },
                    {
                        "id": "call_2",
                        "type": "function",
                        "function": {"name": "get_weather", "arguments": '{"city": "London"}'},
                    },
                ],
            },
            {"role": "tool", "tool_call_id": "call_1", "content": "14C"},
            {"role": "tool", "tool_call_id": "call_2", "content": "11C"},
            {"role": "assistant", "content": "Paris 14, London 11."},
        ]
    )
    assert [m["role"] for m in messages] == ["user", "assistant", "user", "assistant"]
    grouped = messages[2]["content"]
    assert [b["tool_use_id"] for b in grouped] == ["call_1", "call_2"]
    assert [b["content"] for b in grouped] == ["14C", "11C"]


def test_malformed_tool_args_degrade_to_empty_dict():
    _system, messages = a._messages_to_anthropic(
        [
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "c1",
                        "type": "function",
                        "function": {"name": "get_weather", "arguments": "{not json"},
                    }
                ],
            },
        ]
    )
    assert messages[0]["content"][0]["input"] == {}


def test_non_dict_tool_args_degrade_to_empty_dict():
    assert a._parse_arguments('"a bare string"') == {}
    assert a._parse_arguments("[1, 2]") == {}
    assert a._parse_arguments(None) == {}


# ---- streaming against a fake SDK client ------------------------------------


class _FakeStream:
    def __init__(self, texts: list[str], final) -> None:
        self._texts = texts
        self._final = final

    @property
    def text_stream(self):
        async def _iter():
            for t in self._texts:
                yield t

        return _iter()

    async def get_final_message(self):
        return self._final


class _FakeAnthropicClient:
    """Stands in for anthropic.AsyncAnthropic: `messages.stream(**kwargs)` is
    an async context manager yielding a _FakeStream."""

    def __init__(self, texts: list[str], final) -> None:
        self.calls: list[dict] = []
        outer = self

        class _Messages:
            @asynccontextmanager
            async def stream(self, **kwargs):
                outer.calls.append(kwargs)
                yield _FakeStream(texts, final)

        self.messages = _Messages()


def _final_message(content, stop_reason="end_turn", input_tokens=10, output_tokens=5):
    return SimpleNamespace(
        content=content,
        stop_reason=stop_reason,
        usage=SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens),
    )


async def test_stream_yields_text_then_result_with_tool_calls(monkeypatch):
    final = _final_message(
        content=[
            SimpleNamespace(type="text", text="Checking…"),
            SimpleNamespace(
                type="tool_use",
                id="toolu_1",
                name="get_weather",
                input={"city": "Paris"},
            ),
        ],
        stop_reason="tool_use",
    )
    fake = _FakeAnthropicClient(["Check", "ing…"], final)
    monkeypatch.setattr(a, "get_client", lambda api_key=None: fake)

    events = [
        e
        async for e in a.stream_message(
            [
                {"role": "system", "content": "Be terse."},
                {"role": "user", "content": "weather?"},
            ],
            model="claude-sonnet-5",
            tools=[WEATHER_TOOL],
        )
    ]
    assert [e.text for e in events if isinstance(e, StreamChunk)] == ["Check", "ing…"]
    result = events[-1]
    assert isinstance(result, StreamResult)
    assert result.text == "Checking…"
    assert result.finish_reason == "tool_calls"
    assert result.input_tokens == 10 and result.output_tokens == 5
    assert result.cost_usd > Decimal("0")  # registry model has pricing
    [tc] = result.tool_calls
    assert tc.id == "toolu_1"
    assert tc.name == "get_weather"
    assert json.loads(tc.arguments_json) == {"city": "Paris"}
    assert tc.thought_signature is None

    # The request carried system/tools in Anthropic's shapes.
    call = fake.calls[0]
    assert call["system"] == "Be terse."
    assert call["tools"][0]["name"] == "get_weather"
    assert call["messages"] == [{"role": "user", "content": "weather?"}]


async def test_stream_maps_end_turn_to_stop(monkeypatch):
    final = _final_message(content=[SimpleNamespace(type="text", text="hi")])
    fake = _FakeAnthropicClient(["hi"], final)
    monkeypatch.setattr(a, "get_client", lambda api_key=None: fake)
    events = [
        e
        async for e in a.stream_message(
            [{"role": "user", "content": "hi"}], model="claude-haiku-4-5"
        )
    ]
    assert events[-1].finish_reason == "stop"
    # No system/tools provided -> the kwargs must omit them entirely.
    assert "system" not in fake.calls[0]
    assert "tools" not in fake.calls[0]


def test_get_client_raises_clearly_without_key(monkeypatch):
    monkeypatch.setattr(a.settings, "anthropic_api_key", None)
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        a.get_client(api_key=None)


def test_clients_cached_per_key(monkeypatch):
    a._clients.clear()
    c1 = a.get_client("key-one")
    c2 = a.get_client("key-one")
    c3 = a.get_client("key-two")
    assert c1 is c2
    assert c1 is not c3
    a._clients.clear()
