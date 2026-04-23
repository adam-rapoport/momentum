"""Integrations REST API — Sprint 3 Chunk D (Google Docs).

Endpoints:
  GET  /api/v1/integrations/google/status    — is it connected? email?
  POST /api/v1/integrations/google/connect   — returns { authorize_url }
  GET  /api/v1/integrations/google/callback  — OAuth redirect target
  DELETE /api/v1/integrations/google         — disconnect

The callback is not a JSON API — it's the URL Google redirects the user's
browser to. We finish the token exchange and then redirect back to
`FRONTEND_ORIGIN/settings?google=connected` (or `?google=error`).
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.default_user import get_default_user
from app.core.integrations.google_oauth import (
    OAuthFlowError,
    OAuthNotConfigured,
    complete_authorization,
    disconnect,
    get_integration,
    integration_public_view,
    start_authorization,
)
from app.core.integrations.vault import VaultNotConfigured
from app.dependencies import get_db, get_redis

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/integrations", tags=["integrations"])


@router.get("/google/status")
async def google_status(db: AsyncSession = Depends(get_db)) -> dict:
    user = await get_default_user(db)
    integration = await get_integration(db, user.id)
    return integration_public_view(integration)


@router.post("/google/connect")
async def google_connect(
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> dict:
    user = await get_default_user(db)
    try:
        authorize_url = await start_authorization(redis, user.id)
    except OAuthNotConfigured as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except VaultNotConfigured as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    return {"authorize_url": authorize_url}


@router.get("/google/callback")
async def google_callback(
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    """Google redirects the browser here with ?code=...&state=... (or error=...).
    We complete the exchange and redirect back to the settings page."""
    frontend_settings_url = f"{settings.frontend_origin.rstrip('/')}/settings"
    error = request.query_params.get("error")
    if error:
        return RedirectResponse(
            f"{frontend_settings_url}?google=error&reason={error}", status_code=302
        )

    code = request.query_params.get("code")
    state = request.query_params.get("state")
    if not code or not state:
        return RedirectResponse(
            f"{frontend_settings_url}?google=error&reason=missing_code_or_state",
            status_code=302,
        )

    try:
        await complete_authorization(db, redis, code, state)
    except (OAuthFlowError, OAuthNotConfigured, VaultNotConfigured) as e:
        logger.warning("google oauth callback failed: %s", e)
        return RedirectResponse(
            f"{frontend_settings_url}?google=error&reason=exchange_failed",
            status_code=302,
        )

    return RedirectResponse(f"{frontend_settings_url}?google=connected", status_code=302)


@router.delete("/google", status_code=status.HTTP_204_NO_CONTENT)
async def google_disconnect(db: AsyncSession = Depends(get_db)) -> None:
    user = await get_default_user(db)
    await disconnect(db, user.id)
