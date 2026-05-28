"""Unit tests for the F5 native google-genai client's translation layer.

These cover the pure message/tool translation and the in-loop thought-signature
cache — the parts written against the SDK's data shapes that we can exercise
without a live API call. End-to-end streaming is covered by
scripts/try_google_sdk.py.
"""
from __future__ import annotations

import pytest

# The translator builds real genai `types`, so the SDK must be importable.
pytest.importorskip("google.genai")

from app.core import google_genai_client as g  # noqa: E402


WEATHER_TOOL = {
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "Get the weather for a city.",
        "parameters": {
            "type": "object",
            "properties": {"city": {"type": "string"}},
            "required": ["city"],
        },
    },
}


def test_tools_to_genai_handles_empty():
    assert g._tools_to_genai(None) is None
    assert g._tools_to_genai([]) is None


def test_tools_to_genai_builds_one_declaration_per_tool():
    tools = g._tools_to_genai([WEATHER_TOOL])
    assert tools is not None and len(tools) == 1
    decls = tools[0].function_declarations
    assert len(decls) == 1
    assert decls[0].name == "get_weather"


def test_system_messages_collected_into_instruction():
    system, contents = g._messages_to_genai(
        [
            {"role": "system", "content": "Be terse."},
            {"role": "system", "content": "Use tools."},
            {"role": "user", "content": "hi"},
        ]
    )
    assert system == "Be terse.\n\nUse tools."
    assert len(contents) == 1
    assert contents[0].role == "user"
    assert contents[0].parts[0].text == "hi"


def test_assistant_text_maps_to_model_role():
    _system, contents = g._messages_to_genai(
        [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello there"},
        ]
    )
    assert [c.role for c in contents] == ["user", "model"]
    assert contents[1].parts[0].text == "hello there"


def test_tool_call_and_result_roundtrip():
    messages = [
        {"role": "user", "content": "weather in Paris?"},
        {
            "role": "assistant",
            "content": "",
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
        {"role": "tool", "tool_call_id": "call_abc", "content": '{"temp_c": 14}'},
    ]
    _system, contents = g._messages_to_genai(messages)
    # user, model(function_call), user(function_response)
    assert [c.role for c in contents] == ["user", "model", "user"]

    fc_part = contents[1].parts[0]
    assert fc_part.function_call.name == "get_weather"
    assert fc_part.function_call.args == {"city": "Paris"}

    # The tool result is keyed by the *function name*, looked up from the call id.
    fr_part = contents[2].parts[0]
    assert fr_part.function_response.name == "get_weather"
    assert fr_part.function_response.response == {"result": '{"temp_c": 14}'}


def test_cached_signature_is_replayed_on_function_call(monkeypatch):
    g._SIGNATURE_CACHE.clear()
    g._SIGNATURE_CACHE["call_xyz"] = b"opaque-signature"
    messages = [
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_xyz",
                    "type": "function",
                    "function": {"name": "get_weather", "arguments": "{}"},
                }
            ],
        },
    ]
    _system, contents = g._messages_to_genai(messages)
    assert contents[0].parts[0].thought_signature == b"opaque-signature"
    g._SIGNATURE_CACHE.clear()


def test_malformed_tool_args_degrade_to_empty_dict():
    messages = [
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
    _system, contents = g._messages_to_genai(messages)
    assert contents[0].parts[0].function_call.args == {}


def test_signature_cache_ignores_empty_and_bounds_size():
    g._SIGNATURE_CACHE.clear()
    g._remember_signature("", b"sig")          # no id
    g._remember_signature("id", b"")           # no signature
    assert len(g._SIGNATURE_CACHE) == 0

    for i in range(g._SIGNATURE_CACHE_MAX + 10):
        g._remember_signature(f"id{i}", b"sig")
    assert len(g._SIGNATURE_CACHE) == g._SIGNATURE_CACHE_MAX
    # Oldest evicted, newest retained.
    assert "id0" not in g._SIGNATURE_CACHE
    assert f"id{g._SIGNATURE_CACHE_MAX + 9}" in g._SIGNATURE_CACHE
    g._SIGNATURE_CACHE.clear()


def test_get_client_raises_clearly_without_key(monkeypatch):
    monkeypatch.setattr(g.settings, "google_ai_api_key", None)
    with pytest.raises(RuntimeError, match="GOOGLE_AI_API_KEY"):
        g.get_client(api_key=None)
