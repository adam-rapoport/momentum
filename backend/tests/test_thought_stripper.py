"""Unit tests for the Gemma <thought>...</thought> stream filter (Chunk F).

Gemma 4 emits chain-of-thought reasoning directly in its text stream.
The stripper in google_client removes those blocks before they reach the
UI. Must be safe across chunk boundaries — the tags can straddle chunks.
"""
from __future__ import annotations

from app.core.google_client import _ThoughtStripper


def test_plain_text_passes_through_unchanged():
    s = _ThoughtStripper()
    assert s.feed("hello world") == "hello world"
    assert s.flush() == ""


def test_whole_tag_in_one_feed():
    s = _ThoughtStripper()
    assert s.feed("hi <thought>private</thought> bye") == "hi  bye"
    assert s.flush() == ""


def test_character_by_character_stream():
    s = _ThoughtStripper()
    out = ""
    for ch in "a<thought>secret</thought>b":
        out += s.feed(ch)
    out += s.flush()
    assert out == "ab"


def test_tag_split_across_chunks():
    s = _ThoughtStripper()
    out = s.feed("visible <thou")
    out += s.feed("ght>hidden</thou")
    out += s.feed("ght> tail")
    out += s.flush()
    assert out == "visible  tail"


def test_multiple_thought_blocks():
    s = _ThoughtStripper()
    out = s.feed("a<thought>x</thought>b<thought>y</thought>c")
    out += s.flush()
    assert out == "abc"


def test_unclosed_thought_at_end_is_dropped():
    # If the stream ends inside an unclosed thought block, we should drop
    # the partial content rather than leak it.
    s = _ThoughtStripper()
    out = s.feed("visible<thought>never closes")
    out += s.flush()
    assert out == "visible"


def test_partial_open_tag_held_across_chunks():
    s = _ThoughtStripper()
    # "<" alone could be the start of an open tag — hold it.
    out = s.feed("word <")
    assert out == "word "
    # Complete the tag across chunks.
    out += s.feed("thought>secret</thought> ok")
    out += s.flush()
    assert out == "word  ok"


def test_angle_bracket_that_isnt_a_tag_yields_through():
    # "<a>" is not the start of <thought> — must not be held forever.
    s = _ThoughtStripper()
    out = s.feed("before <a>after")
    out += s.flush()
    assert out == "before <a>after"


def test_empty_feeds_are_noops():
    s = _ThoughtStripper()
    assert s.feed("") == ""
    assert s.flush() == ""


def test_close_tag_without_open_passes_through():
    # We only suppress content between matched <thought> and </thought>.
    # A stray close tag with no open partner isn't our problem to clean.
    s = _ThoughtStripper()
    out = s.feed("text </thought> more")
    out += s.flush()
    assert out == "text </thought> more"


def test_adjacent_thought_blocks():
    s = _ThoughtStripper()
    out = s.feed("<thought>a</thought><thought>b</thought>end")
    out += s.flush()
    assert out == "end"
