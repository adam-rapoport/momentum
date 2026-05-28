"""Per-user API key storage + resolution for LLM and search providers.

This is the backend half of C8 (the Connections UI). It lets users supply
their own provider API keys through the app instead of hand-editing `.env`,
while keeping the `.env` path working for contributors and tests.

Resolution philosophy mirrors `app.core.model_router`: a user-supplied value
takes precedence, with the env-var default as the fallback. Here the
user-supplied value is an API key stored Fernet-encrypted in the generic
`integrations` table (same vault as OAuth tokens — see
`app.core.integrations.vault`). Provider strings are namespaced so these
key rows never collide with the OAuth `google` row:

    llm:groq          -> GROQ_API_KEY
    llm:google_ai     -> GOOGLE_AI_API_KEY   (Google AI Studio key, AIza...)
    search:tavily     -> TAVILY_API_KEY
    search:perplexity -> PERPLEXITY_API_KEY

Note `llm:google_ai` (the Gemini API key) is deliberately distinct from the
OAuth `google` integration (Docs/Gmail/Calendar). They are two different
Google connections and must never be conflated.
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.integrations.vault import (
    VaultDecodeError,
    VaultNotConfigured,
    decrypt_credentials,
    encrypt_credentials,
)
from app.models import Integration

# Provider string -> the `settings` attribute holding its env-var fallback.
LLM_PROVIDERS: dict[str, str] = {
    "llm:groq": "groq_api_key",
    "llm:google_ai": "google_ai_api_key",
}
SEARCH_PROVIDERS: dict[str, str] = {
    "search:tavily": "tavily_api_key",
    "search:perplexity": "perplexity_api_key",
}
KEY_PROVIDERS: dict[str, str] = {**LLM_PROVIDERS, **SEARCH_PROVIDERS}

# Maps an LLM credential provider to the model_registry provider name.
_REGISTRY_PROVIDER: dict[str, str] = {
    "llm:groq": "groq",
    "llm:google_ai": "google",
}

_GOOGLE_MODEL_PREFIXES = ("gemini-", "gemma-")


def llm_provider_for_model(model_id: str) -> str:
    """Map a model ID to the credential provider whose key serves it."""
    if model_id.startswith(_GOOGLE_MODEL_PREFIXES):
        return "llm:google_ai"
    return "llm:groq"


def _env_fallback(provider: str) -> str | None:
    attr = KEY_PROVIDERS.get(provider)
    if not attr:
        return None
    value = getattr(settings, attr, None)
    return value or None


async def _get_row(db: AsyncSession, user_id: UUID, provider: str) -> Integration | None:
    return await db.scalar(
        select(Integration).where(
            Integration.user_id == user_id, Integration.provider == provider
        )
    )


async def resolve_api_key(
    db: AsyncSession, user_id: UUID, provider: str
) -> str | None:
    """Return the usable API key for `provider`: the stored (decrypted) key if
    one is connected, otherwise the env-var fallback, otherwise None.

    A corrupt/undecryptable stored key falls back to env rather than raising,
    so a rotated vault key can't hard-break a turn.
    """
    if provider not in KEY_PROVIDERS:
        raise ValueError(f"unknown key provider '{provider}'")
    row = await _get_row(db, user_id, provider)
    if row is not None and row.status == "connected" and row.encrypted_credentials:
        try:
            creds = decrypt_credentials(row.encrypted_credentials)
            key = creds.get("api_key")
            if key:
                return key
        except (VaultDecodeError, VaultNotConfigured):
            pass  # fall through to env
    return _env_fallback(provider)


async def store_api_key(
    db: AsyncSession, user_id: UUID, provider: str, key: str
) -> Integration:
    """Upsert an encrypted API key for `provider`. Stores only the last-4
    suffix in plaintext (`meta.key_suffix`) for masked display; the full key
    lives only in the encrypted blob."""
    if provider not in KEY_PROVIDERS:
        raise ValueError(f"unknown key provider '{provider}'")
    key = key.strip()
    encrypted = encrypt_credentials({"api_key": key})
    now = datetime.now(timezone.utc)
    suffix = key[-4:] if len(key) >= 4 else key

    row = await _get_row(db, user_id, provider)
    if row is not None:
        row.encrypted_credentials = encrypted
        row.status = "connected"
        row.connected_at = now
        row.meta = {
            **(row.meta or {}),
            "key_suffix": suffix,
            "last_validated_at": now.isoformat(),
            "last_error": None,
        }
    else:
        row = Integration(
            id=uuid4(),
            user_id=user_id,
            provider=provider,
            status="connected",
            encrypted_credentials=encrypted,
            scopes=[],
            meta={
                "key_suffix": suffix,
                "last_validated_at": now.isoformat(),
                "last_error": None,
            },
            connected_at=now,
        )
        db.add(row)
    await db.commit()
    return row


async def delete_api_key(db: AsyncSession, user_id: UUID, provider: str) -> bool:
    """Remove a stored key so resolution falls back to env (or none). Returns
    True if a row was removed."""
    if provider not in KEY_PROVIDERS:
        raise ValueError(f"unknown key provider '{provider}'")
    row = await _get_row(db, user_id, provider)
    if row is None:
        return False
    await db.delete(row)
    await db.commit()
    return True


async def get_key_status(db: AsyncSession, user_id: UUID) -> list[dict]:
    """Public (no-secret) status of every key-based provider, for the
    Connections UI. `source` is where the active key comes from."""
    rows = {
        r.provider: r
        for r in (
            await db.scalars(
                select(Integration).where(
                    Integration.user_id == user_id,
                    Integration.provider.in_(list(KEY_PROVIDERS)),
                )
            )
        ).all()
    }
    out: list[dict] = []
    for provider in KEY_PROVIDERS:
        row = rows.get(provider)
        has_stored = bool(
            row and row.status == "connected" and row.encrypted_credentials
        )
        has_env = _env_fallback(provider) is not None
        meta = (row.meta or {}) if row else {}
        out.append(
            {
                "provider": provider,
                "configured": has_stored or has_env,
                "source": "stored" if has_stored else ("env" if has_env else "none"),
                "key_suffix": meta.get("key_suffix") if has_stored else None,
                "status": row.status if row else "disconnected",
                "last_validated_at": meta.get("last_validated_at"),
                "last_error": meta.get("last_error"),
            }
        )
    return out


async def configured_llm_providers(db: AsyncSession, user_id: UUID) -> set[str]:
    """The set of model_registry provider names ("groq", "google") that have a
    usable key for this user (stored or env). Drives user-aware model
    availability in the registry."""
    out: set[str] = set()
    for cred_provider, registry_name in _REGISTRY_PROVIDER.items():
        if await resolve_api_key(db, user_id, cred_provider) is not None:
            out.add(registry_name)
    return out
