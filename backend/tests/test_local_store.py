"""Unit tests for the in-process KV store that replaced Redis.

Covers the four methods the app relies on (set/get/exists/delete) plus TTL
expiry — the behavior the OAuth-state and cancel-flag paths depend on.
"""
import app.core.local_store as local_store
from app.core.local_store import LocalKVStore


async def test_set_get_exists_delete():
    kv = LocalKVStore()
    await kv.set("k", "v")
    assert await kv.get("k") == "v"
    assert await kv.exists("k") == 1
    await kv.delete("k")
    assert await kv.get("k") is None
    assert await kv.exists("k") == 0


async def test_missing_key_is_safe():
    kv = LocalKVStore()
    assert await kv.get("nope") is None
    assert await kv.exists("nope") == 0
    await kv.delete("nope")  # must not raise


async def test_ttl_expiry(monkeypatch):
    clock = {"now": 1000.0}
    monkeypatch.setattr(local_store.time, "monotonic", lambda: clock["now"])

    kv = LocalKVStore()
    await kv.set("k", "v", ex=60)

    assert await kv.get("k") == "v"
    clock["now"] = 1059.9  # still inside the window
    assert await kv.exists("k") == 1
    clock["now"] = 1060.1  # past expiry
    assert await kv.get("k") is None
    assert await kv.exists("k") == 0
