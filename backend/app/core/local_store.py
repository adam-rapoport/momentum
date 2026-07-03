"""In-process key/value store with TTL — a tiny stand-in for the small,
transient slices of Redis that Momentum actually used.

Redis previously held exactly two things: a "cancel this turn" flag
(60s TTL) and a Google OAuth state token (5min TTL). Neither needs to
survive a restart, and the app runs in a single process — so a plain
in-memory dict with lazy expiry replaces Redis entirely. Dropping the
external service is what lets Momentum run as a single-user desktop
install with nothing to set up.

Only the handful of methods the app calls are implemented, with the same
signatures the old `redis.asyncio` client exposed (so call sites barely
change). Values are stored as strings to match the previous client's
`decode_responses=True` behavior.
"""

import time


class LocalKVStore:
    """Async, in-process key/value store with per-key expiry.

    Method shapes mirror the subset of the Redis client we used:
    ``set(key, value, ex=...)``, ``get``, ``exists``, ``delete``.
    """

    def __init__(self) -> None:
        # key -> (value, expires_at_monotonic | None)
        self._data: dict[str, tuple[str, float | None]] = {}

    def _live(self, key: str) -> bool:
        """Return True if the key exists and hasn't expired; evict if it has."""
        item = self._data.get(key)
        if item is None:
            return False
        _, expires_at = item
        if expires_at is not None and time.monotonic() >= expires_at:
            self._data.pop(key, None)
            return False
        return True

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        expires_at = time.monotonic() + ex if ex is not None else None
        self._data[key] = (str(value), expires_at)

    async def get(self, key: str) -> str | None:
        return self._data[key][0] if self._live(key) else None

    async def exists(self, key: str) -> int:
        # Redis returns the count of matching keys; callers only check truthiness.
        return 1 if self._live(key) else 0

    async def delete(self, key: str) -> None:
        self._data.pop(key, None)
