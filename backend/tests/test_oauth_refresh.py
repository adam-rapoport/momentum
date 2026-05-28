"""Unit tests for the Google OAuth proactive-refresh decision (Sprint 7 F4).

Pure logic only — no DB, no HTTP. The startup pass + on-use refresh both
key off `_should_refresh`, so this locks in the "refresh ahead of expiry"
behavior and the widened safety margin.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.core.integrations.google_oauth import _REFRESH_MARGIN, _should_refresh


def _now() -> datetime:
    return datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)


def test_missing_expiry_always_refreshes():
    assert _should_refresh(None, now=_now()) is True


def test_token_well_within_validity_is_not_refreshed():
    # An hour of life left, far outside the margin.
    expires_at = _now() + timedelta(minutes=60)
    assert _should_refresh(expires_at, now=_now()) is False


def test_token_inside_margin_is_refreshed():
    # 5 minutes left is inside the 10-minute margin — refresh proactively
    # rather than handing a soon-to-die token to a long-running turn.
    expires_at = _now() + timedelta(minutes=5)
    assert _should_refresh(expires_at, now=_now()) is True


def test_already_expired_token_is_refreshed():
    expires_at = _now() - timedelta(minutes=1)
    assert _should_refresh(expires_at, now=_now()) is True


def test_margin_is_wider_than_the_old_two_minutes():
    # Regression guard: a token with 3 min left would have slipped through the
    # old 2-minute window but must now be refreshed.
    assert _REFRESH_MARGIN >= timedelta(minutes=10)
    expires_at = _now() + timedelta(minutes=3)
    assert _should_refresh(expires_at, now=_now()) is True


def test_boundary_at_exactly_the_margin_is_not_refreshed():
    # Exactly `margin` away: strictly-less-than comparison means not yet.
    expires_at = _now() + _REFRESH_MARGIN
    assert _should_refresh(expires_at, now=_now()) is False
