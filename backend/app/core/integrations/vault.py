"""Symmetric encryption for OAuth tokens at rest.

We use Fernet (AES-128-CBC + HMAC-SHA256 from the `cryptography` library).
The key is a urlsafe base64-encoded 32-byte value supplied via the
`CREDENTIAL_VAULT_KEY` env var. Generate one with:

    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

Design choices:
- Tokens are serialized to JSON before encryption, so rotating providers
  or adding fields (scopes, refresh, expiry) doesn't change the call sites.
- We lazily construct the Fernet instance so the app can boot without a
  key set (only the `/integrations/google/connect` path requires it).
"""
from __future__ import annotations

import json
from datetime import datetime
from functools import lru_cache
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings


class VaultNotConfigured(RuntimeError):
    """Raised when encrypt/decrypt is called without `CREDENTIAL_VAULT_KEY` set."""


class VaultDecodeError(RuntimeError):
    """Raised when a stored blob fails to decrypt — key rotated or blob corrupt."""


@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    key = settings.credential_vault_key
    if not key:
        raise VaultNotConfigured(
            "CREDENTIAL_VAULT_KEY is not set. Generate one with "
            "`python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"` "
            "and add it to backend/.env."
        )
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except ValueError as e:
        raise VaultNotConfigured(
            f"CREDENTIAL_VAULT_KEY is set but invalid ({e}). It must be a "
            "urlsafe base64-encoded 32-byte key."
        ) from e


def _json_default(obj: Any) -> Any:
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"cannot serialize {type(obj).__name__}")


def encrypt_credentials(payload: dict) -> bytes:
    raw = json.dumps(payload, default=_json_default).encode("utf-8")
    return _fernet().encrypt(raw)


def decrypt_credentials(blob: bytes) -> dict:
    if not blob:
        return {}
    try:
        raw = _fernet().decrypt(blob)
    except InvalidToken as e:
        raise VaultDecodeError(
            "Could not decrypt stored credentials. The vault key may have "
            "been rotated — disconnect and reconnect the integration."
        ) from e
    return json.loads(raw.decode("utf-8"))
