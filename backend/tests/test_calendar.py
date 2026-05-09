"""Unit tests for Calendar adapter pure-logic helpers.

The Google API calls are mocked elsewhere — here we exercise the
time-parsing and interval-math used by find_availability, because
those are the bits most likely to misbehave on real data.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.core.integrations.google_calendar import (
    _merge_intervals,
    _parse_aware_iso,
    _subtract_intervals,
    _tz_name,
)


# ---------- _parse_aware_iso ----------


def test_parse_aware_iso_accepts_offset():
    dt = _parse_aware_iso("2026-04-25T14:00:00-07:00", "start")
    assert dt.tzinfo is not None
    assert dt.utcoffset() == timedelta(hours=-7)


def test_parse_aware_iso_accepts_utc():
    dt = _parse_aware_iso("2026-04-25T14:00:00+00:00", "start")
    assert dt.utcoffset() == timedelta(0)


def test_parse_aware_iso_rejects_naive():
    with pytest.raises(ValueError, match="missing a timezone offset"):
        _parse_aware_iso("2026-04-25T14:00:00", "start")


def test_parse_aware_iso_rejects_nonsense():
    with pytest.raises(ValueError, match="ISO-8601"):
        _parse_aware_iso("tomorrow at 2", "start")


# ---------- _merge_intervals ----------


def _dt(h: int, m: int = 0) -> datetime:
    return datetime(2026, 4, 25, h, m, tzinfo=timezone.utc)


def test_merge_intervals_empty():
    assert _merge_intervals([]) == []


def test_merge_intervals_non_overlapping_returns_sorted():
    ivs = [(_dt(14), _dt(15)), (_dt(10), _dt(11))]
    assert _merge_intervals(ivs) == [(_dt(10), _dt(11)), (_dt(14), _dt(15))]


def test_merge_intervals_overlapping_merges():
    ivs = [(_dt(10), _dt(12)), (_dt(11), _dt(13))]
    assert _merge_intervals(ivs) == [(_dt(10), _dt(13))]


def test_merge_intervals_touching_intervals_merge():
    # Back-to-back meetings with no gap should collapse into one busy block.
    ivs = [(_dt(10), _dt(11)), (_dt(11), _dt(12))]
    assert _merge_intervals(ivs) == [(_dt(10), _dt(12))]


def test_merge_intervals_contained_interval_merges():
    ivs = [(_dt(9), _dt(17)), (_dt(12), _dt(13))]
    assert _merge_intervals(ivs) == [(_dt(9), _dt(17))]


# ---------- _subtract_intervals ----------


def test_subtract_no_busy_returns_full_window():
    gaps = _subtract_intervals(_dt(9), _dt(17), [])
    assert gaps == [(_dt(9), _dt(17))]


def test_subtract_busy_covers_entire_window():
    gaps = _subtract_intervals(_dt(9), _dt(17), [(_dt(8), _dt(18))])
    assert gaps == []


def test_subtract_busy_in_middle_yields_two_gaps():
    gaps = _subtract_intervals(_dt(9), _dt(17), [(_dt(11), _dt(12))])
    assert gaps == [(_dt(9), _dt(11)), (_dt(12), _dt(17))]


def test_subtract_busy_at_start_and_end():
    busy = [(_dt(9), _dt(10)), (_dt(16), _dt(17))]
    gaps = _subtract_intervals(_dt(9), _dt(17), busy)
    assert gaps == [(_dt(10), _dt(16))]


def test_subtract_busy_outside_window_ignored():
    busy = [(_dt(7), _dt(8)), (_dt(18), _dt(20))]
    gaps = _subtract_intervals(_dt(9), _dt(17), busy)
    assert gaps == [(_dt(9), _dt(17))]


def test_subtract_busy_overlapping_window_edges_clipped():
    busy = [(_dt(8), _dt(10)), (_dt(16), _dt(18))]
    gaps = _subtract_intervals(_dt(9), _dt(17), busy)
    assert gaps == [(_dt(10), _dt(16))]


def test_subtract_with_merged_input_yields_correct_slots():
    # Simulate the full pipeline: two overlapping meetings should leave
    # one morning gap and one afternoon gap.
    raw = [(_dt(10), _dt(11, 30)), (_dt(11), _dt(12, 30)), (_dt(14), _dt(15))]
    merged = _merge_intervals(raw)
    gaps = _subtract_intervals(_dt(9), _dt(17), merged)
    assert gaps == [
        (_dt(9), _dt(10)),
        (_dt(12, 30), _dt(14)),
        (_dt(15), _dt(17)),
    ]


# ---------- _tz_name ----------


def test_tz_name_utc():
    dt = datetime(2026, 4, 25, tzinfo=timezone.utc)
    assert _tz_name(dt) == "UTC"


def test_tz_name_offset_no_iana():
    dt = datetime(2026, 4, 25, tzinfo=timezone(timedelta(hours=-7)))
    # No IANA name available — we fall back to whatever tzname() returns
    # which is implementation-specific, but never crashes.
    result = _tz_name(dt)
    assert isinstance(result, str) and result
