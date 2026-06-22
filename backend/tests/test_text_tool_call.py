"""Unit tests for the tool-call-as-text detector.

A weak model (e.g. Groq's Scout) occasionally emits a tool call as plain text
instead of using the function-calling interface — e.g. it literally writes
`SaveMemory("...", "...", "decision")` as its reply. The call never runs and
nothing is saved, with no error. The session engine detects this shape (a line
starting with a REGISTERED tool name + `(`) and retries the turn once with a
corrective nudge. These tests cover the detector that gates that retry.
"""
from __future__ import annotations

from app.core.session_engine import _looks_like_text_tool_call

TOOLS = {"SaveMemory", "RecallMemory", "WriteDocument", "WebSearch"}


def test_detects_whole_message_as_tool_call():
    # The exact failure mode seen in testing: the whole reply is the call.
    text = 'SaveMemory("Rachel owns the renewal", "Rachel owns renewal", "decision")'
    assert _looks_like_text_tool_call(text, TOOLS) is True


def test_detects_tool_call_on_a_later_line():
    text = "Sure, I'll remember that.\nSaveMemory(\"x\", \"y\", \"team\")"
    assert _looks_like_text_tool_call(text, TOOLS) is True


def test_detects_with_leading_whitespace():
    text = "   RecallMemory(query=\"helix renewal\")"
    assert _looks_like_text_tool_call(text, TOOLS) is True


def test_ignores_prose_mentioning_a_tool_name():
    # Merely talking about a tool must NOT trip the detector.
    text = "RecallMemory is the tool I use to look things up. Let me know!"
    assert _looks_like_text_tool_call(text, TOOLS) is False


def test_ignores_unknown_function_name():
    # A `Foo(...)` shape whose name isn't a registered tool is just prose/code.
    text = "calculate(2, 3) returns 5 in most languages."
    assert _looks_like_text_tool_call(text, TOOLS) is False


def test_ignores_tool_name_not_at_line_start():
    # The call shape must begin the line; an inline mention is not a call.
    text = "You can call SaveMemory(x) if you want to persist it."
    assert _looks_like_text_tool_call(text, TOOLS) is False


def test_empty_and_none_text():
    assert _looks_like_text_tool_call("", TOOLS) is False
    assert _looks_like_text_tool_call(None, TOOLS) is False  # type: ignore[arg-type]


def test_no_tools_registered_never_matches():
    assert _looks_like_text_tool_call("SaveMemory(\"x\")", set()) is False


def test_normal_assistant_answer_is_not_a_tool_call():
    text = "A simple framework for prioritizing a backlog is RICE scoring."
    assert _looks_like_text_tool_call(text, TOOLS) is False
