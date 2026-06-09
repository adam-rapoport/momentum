"""Unit tests for the Fernet credential vault (plan item 31 / T3).

Pure crypto-layer behavior; the DB-backed store/resolve/delete cycle lives in
tests/integration/test_credentials_vault.py.
"""
from __future__ import annotations

import pytest
from cryptography.fernet import Fernet

from app.config import settings
from app.core.integrations import vault
from app.core.integrations.vault import (
    VaultDecodeError,
    VaultNotConfigured,
    decrypt_credentials,
    encrypt_credentials,
)


@pytest.fixture
def vault_key(monkeypatch):
    """Install a throwaway vault key. `vault._fernet` is lru_cached, so the
    cache must be cleared when installing AND removing the key."""
    key = Fernet.generate_key().decode()
    monkeypatch.setattr(settings, "credential_vault_key", key)
    vault._fernet.cache_clear()
    yield key
    vault._fernet.cache_clear()


def test_encrypt_decrypt_round_trip(vault_key):
    payload = {"api_key": "gsk_secret", "scopes": ["a", "b"], "n": 3}
    blob = encrypt_credentials(payload)
    assert isinstance(blob, bytes)
    assert b"gsk_secret" not in blob  # actually encrypted, not encoded
    assert decrypt_credentials(blob) == payload


def test_decrypt_empty_blob_returns_empty_dict(vault_key):
    assert decrypt_credentials(b"") == {}


def test_decrypt_with_rotated_key_raises_decode_error(monkeypatch, vault_key):
    blob = encrypt_credentials({"api_key": "k"})
    # Rotate the key out from under the stored blob.
    monkeypatch.setattr(settings, "credential_vault_key", Fernet.generate_key().decode())
    vault._fernet.cache_clear()
    with pytest.raises(VaultDecodeError):
        decrypt_credentials(blob)


def test_missing_key_raises_not_configured(monkeypatch):
    monkeypatch.setattr(settings, "credential_vault_key", None)
    vault._fernet.cache_clear()
    try:
        with pytest.raises(VaultNotConfigured):
            encrypt_credentials({"api_key": "k"})
    finally:
        vault._fernet.cache_clear()


def test_invalid_key_raises_not_configured(monkeypatch):
    monkeypatch.setattr(settings, "credential_vault_key", "not-a-fernet-key")
    vault._fernet.cache_clear()
    try:
        with pytest.raises(VaultNotConfigured):
            encrypt_credentials({"api_key": "k"})
    finally:
        vault._fernet.cache_clear()
