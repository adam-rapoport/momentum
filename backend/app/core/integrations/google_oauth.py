"""Google OAuth 2.0 flow + token refresh + Integration-row helpers.

Single-user local-dev variant: simple state-token in Redis (5 min TTL),
no PKCE beyond Google's default flow. Refresh happens lazily on 401.

Scopes requested:
- documents         — create / read / edit Google Docs
- drive.file        — narrow Drive scope limited to files the app creates
  (we never see the user's full Drive)
"""
from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from uuid import UUID, uuid4

import httpx
from redis.asyncio import Redis
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

logger = logging.getLogger(__name__)

PROVIDER = "google_docs"
SCOPES = [
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive.file",
    "openid",
    "email",
]
AUTHORIZATION_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"

_STATE_TTL_SECONDS = 300  # 5 minutes; states aren't reusable


class OAuthNotConfigured(RuntimeError):
    pass


class OAuthFlowError(RuntimeError):
    """Raised for a recoverable OAuth failure (bad state, expired code, etc)."""


def _require_client_config() -> tuple[str, str, str]:
    if not settings.google_client_id or not settings.google_client_secret:
        raise OAuthNotConfigured(
            "GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET must be set in "
            "backend/.env before connecting Google Docs."
        )
    return (
        settings.google_client_id,
        settings.google_client_secret,
        settings.google_redirect_uri,
    )


def _state_key(state: str) -> str:
    return f"google_oauth:state:{state}"


async def start_authorization(redis: Redis, user_id: UUID) -> str:
    """Issue a signed state token, stash the user_id behind it in Redis, and
    return the Google consent URL to redirect the browser to."""
    client_id, _, redirect_uri = _require_client_config()

    # Ensure the vault is usable BEFORE sending the user on a round-trip
    # they can't complete — otherwise the callback would fail.
    try:
        from app.core.integrations.vault import _fernet  # noqa: F401
        _fernet()
    except VaultNotConfigured:
        raise

    state = secrets.token_urlsafe(32)
    await redis.set(_state_key(state), str(user_id), ex=_STATE_TTL_SECONDS)

    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "state": state,
        "access_type": "offline",  # we want a refresh token
        "prompt": "consent",  # force a fresh refresh token each time
        "include_granted_scopes": "true",
    }
    return f"{AUTHORIZATION_URL}?{urlencode(params)}"


async def _consume_state(redis: Redis, state: str) -> UUID:
    value = await redis.get(_state_key(state))
    if not value:
        raise OAuthFlowError(
            "Google OAuth state token is missing or expired. Start the "
            "connection flow again from Settings."
        )
    await redis.delete(_state_key(state))
    try:
        return UUID(value if isinstance(value, str) else value.decode())
    except (ValueError, AttributeError) as e:
        raise OAuthFlowError(f"invalid state value: {e}") from e


async def _exchange_code(code: str) -> dict:
    client_id, client_secret, redirect_uri = _require_client_config()
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post(
            TOKEN_URL,
            data={
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
        )
    if resp.status_code != 200:
        raise OAuthFlowError(f"Google rejected the code exchange ({resp.status_code}): {resp.text}")
    return resp.json()


async def _refresh_access_token(refresh_token: str) -> dict:
    client_id, client_secret, _ = _require_client_config()
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post(
            TOKEN_URL,
            data={
                "refresh_token": refresh_token,
                "client_id": client_id,
                "client_secret": client_secret,
                "grant_type": "refresh_token",
            },
        )
    if resp.status_code != 200:
        raise OAuthFlowError(
            f"Google refresh failed ({resp.status_code}): {resp.text}. "
            "Disconnect the integration in Settings and reconnect."
        )
    return resp.json()


async def _fetch_userinfo(access_token: str) -> dict:
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"}
        )
    if resp.status_code != 200:
        logger.warning("userinfo fetch failed %s: %s", resp.status_code, resp.text)
        return {}
    return resp.json()


async def complete_authorization(
    db: AsyncSession, redis: Redis, code: str, state: str
) -> Integration:
    """Called from the OAuth callback. Exchanges the code, encrypts tokens,
    upserts the Integration row for the user bound to the state token."""
    user_id = await _consume_state(redis, state)

    token_response = await _exchange_code(code)
    access_token = token_response.get("access_token")
    refresh_token = token_response.get("refresh_token")
    expires_in = int(token_response.get("expires_in") or 0)
    scopes = (token_response.get("scope") or "").split() or SCOPES
    if not access_token:
        raise OAuthFlowError("Google returned no access_token.")
    if not refresh_token:
        # Without offline consent we'd lack a refresh token — force a reconnect
        # rather than storing a short-lived access token that silently dies.
        raise OAuthFlowError(
            "Google did not return a refresh_token. Revoke the app from "
            "https://myaccount.google.com/permissions and reconnect."
        )

    expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

    userinfo = await _fetch_userinfo(access_token)

    credentials = {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_at": expires_at.isoformat(),
        "scopes": scopes,
    }
    encrypted = encrypt_credentials(credentials)

    existing = await db.scalar(
        select(Integration).where(
            Integration.user_id == user_id, Integration.provider == PROVIDER
        )
    )
    if existing:
        existing.encrypted_credentials = encrypted
        existing.scopes = scopes
        existing.status = "connected"
        existing.connected_at = datetime.now(timezone.utc)
        existing.last_refreshed_at = datetime.now(timezone.utc)
        existing.meta = {
            **(existing.meta or {}),
            "google_email": userinfo.get("email"),
            "google_name": userinfo.get("name"),
        }
        integration = existing
    else:
        integration = Integration(
            id=uuid4(),
            user_id=user_id,
            provider=PROVIDER,
            status="connected",
            encrypted_credentials=encrypted,
            scopes=scopes,
            meta={
                "google_email": userinfo.get("email"),
                "google_name": userinfo.get("name"),
            },
            connected_at=datetime.now(timezone.utc),
            last_refreshed_at=datetime.now(timezone.utc),
        )
        db.add(integration)

    await db.commit()
    return integration


async def disconnect(db: AsyncSession, user_id: UUID) -> bool:
    """Mark the integration as disconnected and wipe stored credentials."""
    existing = await db.scalar(
        select(Integration).where(
            Integration.user_id == user_id, Integration.provider == PROVIDER
        )
    )
    if not existing:
        return False
    existing.status = "disconnected"
    existing.encrypted_credentials = None
    existing.connected_at = None
    existing.last_refreshed_at = None
    await db.commit()
    return True


async def get_integration(db: AsyncSession, user_id: UUID) -> Integration | None:
    return await db.scalar(
        select(Integration).where(
            Integration.user_id == user_id, Integration.provider == PROVIDER
        )
    )


async def get_valid_access_token(
    db: AsyncSession, integration: Integration
) -> str:
    """Return a fresh access_token, refreshing via refresh_token if needed.

    Marks the integration `error` and re-raises if refresh fails — callers
    should surface a clear "reconnect in Settings" message to the user.
    """
    if not integration.encrypted_credentials:
        raise OAuthFlowError("Integration has no stored credentials — reconnect.")

    try:
        creds = decrypt_credentials(integration.encrypted_credentials)
    except (VaultDecodeError, VaultNotConfigured) as e:
        integration.status = "error"
        await db.commit()
        raise OAuthFlowError(str(e)) from e

    expires_at_str = creds.get("expires_at")
    try:
        expires_at = datetime.fromisoformat(expires_at_str) if expires_at_str else None
    except ValueError:
        expires_at = None

    # Refresh proactively if token has <2 minutes left (or expiry is missing).
    needs_refresh = (
        expires_at is None or expires_at - datetime.now(timezone.utc) < timedelta(minutes=2)
    )

    if not needs_refresh:
        return creds["access_token"]

    refresh_token = creds.get("refresh_token")
    if not refresh_token:
        integration.status = "error"
        await db.commit()
        raise OAuthFlowError("No refresh token stored — reconnect.")

    try:
        refreshed = await _refresh_access_token(refresh_token)
    except OAuthFlowError:
        integration.status = "error"
        await db.commit()
        raise

    new_access = refreshed.get("access_token")
    new_expires_in = int(refreshed.get("expires_in") or 0)
    if not new_access:
        integration.status = "error"
        await db.commit()
        raise OAuthFlowError("Refresh response missing access_token.")

    new_expires_at = datetime.now(timezone.utc) + timedelta(seconds=new_expires_in)
    updated = {
        **creds,
        "access_token": new_access,
        "expires_at": new_expires_at.isoformat(),
    }
    integration.encrypted_credentials = encrypt_credentials(updated)
    integration.last_refreshed_at = datetime.now(timezone.utc)
    await db.commit()
    return new_access


def integration_public_view(integration: Integration | None) -> dict:
    """Summary for the settings page — no secrets."""
    if integration is None:
        return {
            "provider": PROVIDER,
            "status": "disconnected",
            "connected_at": None,
            "google_email": None,
        }
    return {
        "provider": integration.provider,
        "status": integration.status,
        "connected_at": (
            integration.connected_at.isoformat() if integration.connected_at else None
        ),
        "google_email": (integration.meta or {}).get("google_email"),
    }
