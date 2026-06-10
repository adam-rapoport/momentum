"""Unit tests for the F5 native google-genai client's translation layer.

Phase 3 item 19 (findings A12/A13): these are written against the REAL SDK
types (`google.genai.types`) so the translation layer is validated against
the actual API contract — raw-JSON-Schema tool parameters, grouped function
responses for parallel calls, and thought signatures persisted through the
ToolCall/Message.content round-trip instead of a process-local cache.
"""
from __future__ import annotations

import base64

import pytest

# The translator builds real genai `types`, so the SDK must be importable.
pytest.importorskip("google.genai")

from google.genai import types  # noqa: E402

from app.core import google_genai_client as g  # noqa: E402
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


def test_tools_to_genai_handles_empty():
    assert g._tools_to_genai(None) is None
    assert g._tools_to_genai([]) is None


def test_tools_to_genai_builds_one_declaration_per_tool():
    tools = g._tools_to_genai([WEATHER_TOOL])
    assert tools is not None and len(tools) == 1
    decls = tools[0].function_declarations
    assert len(decls) == 1
    assert decls[0].name == "get_weather"
    # Raw JSON Schema passes through `parameters_json_schema` untouched —
    # including `additionalProperties`, which types.Schema-based conversion
    # used to be the risk point for.
    assert decls[0].parameters_json_schema == WEATHER_TOOL["function"]["parameters"]
    assert decls[0].parameters is None


def test_every_registered_tool_schema_is_accepted():
    # The genai path must accept the app's REAL tool specs, not just toys.
    from app.core.tools import _load_builtin_tools, all_tools, to_openai_tools

    _load_builtin_tools()
    tools = g._tools_to_genai(to_openai_tools(all_tools()))
    assert tools is not None
    assert len(tools[0].function_declarations) == len(all_tools())


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


def test_parallel_tool_results_grouped_into_one_content():
    # Two parallel calls arrive as parts of ONE model Content; their results
    # must go back as two function_response parts in ONE user Content — not
    # one Content each (finding A12).
    messages = [
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
    _system, contents = g._messages_to_genai(messages)
    assert [c.role for c in contents] == ["user", "model", "user", "model"]
    model_parts = contents[1].parts
    assert [p.function_call.name for p in model_parts] == ["get_weather", "get_weather"]
    grouped = contents[2].parts
    assert len(grouped) == 2
    assert [p.function_response.response["result"] for p in grouped] == ["14C", "11C"]


def test_persisted_signature_is_replayed_on_function_call():
    # The signature now travels base64-encoded inside the tool_call dict
    # (persisted via the tool_use content block) — no process-local cache.
    raw = b"opaque-signature"
    messages = [
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_xyz",
                    "type": "function",
                    "function": {"name": "get_weather", "arguments": "{}"},
                    "thought_signature": base64.b64encode(raw).decode("ascii"),
                }
            ],
        },
    ]
    _system, contents = g._messages_to_genai(messages)
    assert contents[0].parts[0].thought_signature == raw


def test_corrupt_signature_is_dropped_not_fatal():
    messages = [
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "c1",
                    "type": "function",
                    "function": {"name": "get_weather", "arguments": "{}"},
                    "thought_signature": "%%% not base64 %%%",
                }
            ],
        },
    ]
    _system, contents = g._messages_to_genai(messages)
    assert contents[0].parts[0].thought_signature is None
    assert contents[0].parts[0].function_call.name == "get_weather"


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


# ---- streaming against real SDK response types ------------------------------


class _FakeGenaiClient:
    """Stands in for genai.Client: `aio.models.generate_content_stream`
    returns an async iterator over real GenerateContentResponse objects."""

    def __init__(self, chunks: list) -> None:
        self.calls: list[dict] = []
        outer = self

        class _Models:
            async def generate_content_stream(self, **kwargs):
                outer.calls.append(kwargs)

                async def _iter():
                    for c in chunks:
                        yield c

                return _iter()

        class _Aio:
            models = _Models()

        self.aio = _Aio()


def _response(parts: list, finish_reason=None, usage=None):
    return types.GenerateContentResponse(
        candidates=[
            types.Candidate(
                content=types.Content(role="model", parts=parts),
                finish_reason=finish_reason,
            )
        ],
        usage_metadata=usage,
    )


async def test_stream_yields_text_and_signed_tool_calls(monkeypatch):
    sig = b"\x01\x02opaque"
    chunks = [
        _response([types.Part(text="Checking…")]),
        _response(
            [
                types.Part(
                    function_call=types.FunctionCall(
                        name="get_weather", args={"city": "Paris"}
                    ),
                    thought_signature=sig,
                ),
                # Parallel second call without a signature.
                types.Part(
                    function_call=types.FunctionCall(
                        name="get_weather", args={"city": "London"}
                    )
                ),
            ],
            finish_reason=types.FinishReason.STOP,
            usage=types.GenerateContentResponseUsageMetadata(
                prompt_token_count=10, candidates_token_count=5
            ),
        ),
    ]
    fake = _FakeGenaiClient(chunks)
    monkeypatch.setattr(g, "get_client", lambda api_key=None: fake)

    events = [
        e
        async for e in g.stream_message(
            [{"role": "user", "content": "weather?"}],
            model="gemini-3.5-flash",
            tools=[WEATHER_TOOL],
        )
    ]
    assert isinstance(events[0], StreamChunk) and events[0].text == "Checking…"
    result = events[-1]
    assert isinstance(result, StreamResult)
    assert result.input_tokens == 10 and result.output_tokens == 5
    assert result.finish_reason == "stop"
    assert [tc.name for tc in result.tool_calls] == ["get_weather", "get_weather"]
    # Signature surfaces base64-encoded for persistence in Message.content…
    assert result.tool_calls[0].thought_signature == base64.b64encode(sig).decode()
    assert result.tool_calls[1].thought_signature is None
    # …and decodes back to the SDK's bytes through the translation layer.
    messages = [
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.name, "arguments": tc.arguments_json},
                    **(
                        {"thought_signature": tc.thought_signature}
                        if tc.thought_signature
                        else {}
                    ),
                }
                for tc in result.tool_calls
            ],
        }
    ]
    _system, contents = g._messages_to_genai(messages)
    assert contents[0].parts[0].thought_signature == sig
    assert contents[0].parts[1].thought_signature is None


async def test_stream_skips_thought_parts(monkeypatch):
    chunks = [
        _response([types.Part(text="internal", thought=True)]),
        _response([types.Part(text="visible")], finish_reason=types.FinishReason.STOP),
    ]
    fake = _FakeGenaiClient(chunks)
    monkeypatch.setattr(g, "get_client", lambda api_key=None: fake)
    events = [
        e
        async for e in g.stream_message(
            [{"role": "user", "content": "hi"}], model="gemini-3.5-flash"
        )
    ]
    texts = [e.text for e in events if isinstance(e, StreamChunk)]
    assert texts == ["visible"]
    assert events[-1].text == "visible"


def test_get_client_raises_clearly_without_key(monkeypatch):
    monkeypatch.setattr(g.settings, "google_ai_api_key", None)
    with pytest.raises(RuntimeError, match="GOOGLE_AI_API_KEY"):
        g.get_client(api_key=None)
