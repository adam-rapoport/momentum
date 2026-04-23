"""Unit tests for the concatenated-JSON salvage path (Sprint 4 Chunk F).

Gemini/Gemma via the OpenAI-compat shim occasionally merges N parallel tool
calls into a single tool_call with `{...}{...}` arguments. The session
engine salvages this by splitting the string into separate dicts and
running the tool once per dict.
"""
from __future__ import annotations

from app.core.session_engine import _split_concatenated_json_args


def test_empty_input_returns_none():
    assert _split_concatenated_json_args("") is None
    assert _split_concatenated_json_args("   ") is None


def test_single_valid_json_returns_none():
    # Valid JSON on its own doesn't need salvaging — return None so the
    # caller takes the fast path through json.loads.
    assert _split_concatenated_json_args('{"type":"product"}') is None
    assert _split_concatenated_json_args('{}') is None


def test_concatenated_three_objects():
    raw = '{"type":"product"}{"type":"decision"}{"type":"stakeholder"}'
    result = _split_concatenated_json_args(raw)
    assert result == [
        {"type": "product"},
        {"type": "decision"},
        {"type": "stakeholder"},
    ]


def test_concatenated_with_whitespace_between():
    raw = '{"a":1}  {"b":2}'
    assert _split_concatenated_json_args(raw) == [{"a": 1}, {"b": 2}]


def test_concatenated_with_commas_between():
    # Some providers might emit a comma-separated list that isn't wrapped
    # in an array; treat it like concatenation.
    raw = '{"a":1},{"b":2}'
    assert _split_concatenated_json_args(raw) == [{"a": 1}, {"b": 2}]


def test_garbage_input_returns_none():
    assert _split_concatenated_json_args("not json at all") is None


def test_partially_broken_concatenation_returns_none():
    # If the string starts with valid JSON but trails into garbage, the
    # salvage must refuse — we don't want to half-run a tool with the
    # parseable prefix and silently drop the rest.
    assert _split_concatenated_json_args('{"type":"product"}{"broken":') is None


def test_nested_objects_split_correctly():
    raw = '{"outer":{"inner":1}}{"next":2}'
    assert _split_concatenated_json_args(raw) == [
        {"outer": {"inner": 1}},
        {"next": 2},
    ]


def test_single_object_with_trailing_whitespace_is_valid():
    # A valid JSON with whitespace at the end should be treated as single.
    assert _split_concatenated_json_args('{"a":1}  ') is None


def test_non_dict_objects_return_none():
    # We specifically want dict-shaped tool args; arrays or primitives
    # shouldn't silently become tool invocations.
    assert _split_concatenated_json_args('[1,2,3]') is None
    assert _split_concatenated_json_args('{"a":1}[1,2]') is None
