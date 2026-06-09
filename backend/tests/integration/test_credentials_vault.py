"""Credential store round-trip against the real DB (plan item 31 / T3).

Ports scripts/try_credentials.py: resolve → store → resolve → delete →
resolve, proving stored-key-beats-env and the clean env fallback, plus the
corrupt-blob → env fallback that a rotated vault key produces.
"""
from __future__ import annotations

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import select

from app.config import settings
from app.core import credentials
from app.core.integrations import vault
from app.models import Integration

PROVIDER = "llm:groq"
STORED_KEY = "gsk_stored_0000000000000000000000000000000000000000abcd"
ENV_KEY = "gsk_from_env"

pytestmark = pytest.mark.asyncio


@pytest.fixture
def vault_key(monkeypatch):
    key = Fernet.generate_key().decode()
    monkeypatch.setattr(settings, "credential_vault_key", key)
    vault._fernet.cache_clear()
    yield key
    vault._fernet.cache_clear()


@pytest.fixture
def env_groq_key(monkeypatch):
    monkeypatch.setattr(settings, "groq_api_key", ENV_KEY)
    return ENV_KEY


async def test_store_resolve_delete_cycle(db, seeded, vault_key, env_groq_key):
    user = seeded["user"]

    # 1) Nothing stored → env fallback.
    assert await credentials.resolve_api_key(db, user.id, PROVIDER) == ENV_KEY

    # 2) Stored key takes precedence over env.
    await credentials.store_api_key(db, user.id, PROVIDER, STORED_KEY)
    assert await credentials.resolve_api_key(db, user.id, PROVIDER) == STORED_KEY

    # 3) Status view reports source=stored with the masked suffix, no secret.
    status = await credentials.get_key_status(db, user.id)
    groq = next(s for s in status if s["provider"] == PROVIDER)
    assert groq["source"] == "stored"
    assert groq["key_suffix"] == STORED_KEY[-4:]
    assert STORED_KEY not in str(status)

    # 4) The full key lives only in the encrypted blob.
    row = await db.scalar(
        select(Integration).where(
            Integration.user_id == user.id, Integration.provider == PROVIDER
        )
    )
    assert STORED_KEY.encode() not in row.encrypted_credentials

    # 5) configured_llm_providers includes groq either way.
    assert "groq" in await credentials.configured_llm_providers(db, user.id)

    # 6) Delete → env fallback again; second delete is a no-op.
    assert await credentials.delete_api_key(db, user.id, PROVIDER) is True
    assert await credentials.resolve_api_key(db, user.id, PROVIDER) == ENV_KEY
    assert await credentials.delete_api_key(db, user.id, PROVIDER) is False


async def test_store_overwrites_existing_row(db, seeded, vault_key):
    user = seeded["user"]
    await credentials.store_api_key(db, user.id, PROVIDER, "gsk_old_key_1111")
    await credentials.store_api_key(db, user.id, PROVIDER, "gsk_new_key_2222")

    assert await credentials.resolve_api_key(db, user.id, PROVIDER) == "gsk_new_key_2222"
    rows = (
        await db.scalars(
            select(Integration).where(
                Integration.user_id == user.id, Integration.provider == PROVIDER
            )
        )
    ).all()
    assert len(rows) == 1  # upsert, not a second row
    assert rows[0].meta["key_suffix"] == "2222"


async def test_corrupt_blob_falls_back_to_env(db, seeded, vault_key, env_groq_key):
    """A blob that no longer decrypts (rotated vault key, disk corruption)
    must not hard-break a turn — resolution falls back to the env key."""
    user = seeded["user"]
    await credentials.store_api_key(db, user.id, PROVIDER, STORED_KEY)

    row = await db.scalar(
        select(Integration).where(
            Integration.user_id == user.id, Integration.provider == PROVIDER
        )
    )
    row.encrypted_credentials = b"gAAAAA-not-a-real-fernet-token"
    await db.commit()

    assert await credentials.resolve_api_key(db, user.id, PROVIDER) == ENV_KEY


async def test_resolve_without_env_or_store_returns_none(db, seeded, monkeypatch):
    monkeypatch.setattr(settings, "groq_api_key", None)
    assert await credentials.resolve_api_key(db, seeded["user"].id, PROVIDER) is None


async def test_resolve_unknown_provider_raises(db, seeded):
    with pytest.raises(ValueError):
        await credentials.resolve_api_key(db, seeded["user"].id, "llm:bogus")
