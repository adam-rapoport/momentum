"""Connections REST API — C8 (Sprint 7).

Manages user-supplied provider API keys (LLM + search) that the Connections
UI collects, replacing hand-edited `.env` entries. Keys are stored
Fernet-encrypted via `app.core.credentials`; this module only ever returns
masked, secret-free status.

Endpoints:
  GET    /api/v1/connections                      — status of all key providers
  POST   /api/v1/connections/{provider}/validate  — live ✓/✗ ping (no store)
  PUT    /api/v1/connections/{provider}           — validate-then-store a key
  DELETE /api/v1/connections/{provider}           — remove a stored key
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import credentials
from app.core.default_user import get_default_user
from app.core.integrations.vault import VaultNotConfigured
from app.core.key_validation import validate_key
from app.dependencies import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/connections", tags=["connections"])


class KeyPayload(BaseModel):
    api_key: str = Field(..., min_length=1, description="The provider API key.")


def _ensure_known(provider: str) -> None:
    if provider not in credentials.KEY_PROVIDERS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown connection provider '{provider}'.",
        )


async def _single_status(db: AsyncSession, user_id, provider: str) -> dict:
    rows = await credentials.get_key_status(db, user_id)
    return next(s for s in rows if s["provider"] == provider)


@router.get("")
async def list_connections(db: AsyncSession = Depends(get_db)) -> dict:
    user = await get_default_user(db)
    return {"connections": await credentials.get_key_status(db, user.id)}


@router.post("/{provider}/validate")
async def validate_connection(
    provider: str,
    payload: KeyPayload,
    db: AsyncSession = Depends(get_db),
) -> dict:
    _ensure_known(provider)
    result = await validate_key(provider, payload.api_key)
    return {"ok": result.ok, "detail": result.detail}


@router.put("/{provider}")
async def put_connection(
    provider: str,
    payload: KeyPayload,
    db: AsyncSession = Depends(get_db),
) -> dict:
    _ensure_known(provider)
    user = await get_default_user(db)

    result = await validate_key(provider, payload.api_key)
    if not result.ok:
        # Hard failure (bad/revoked key). Don't store it.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=result.detail
        )

    try:
        await credentials.store_api_key(db, user.id, provider, payload.api_key)
    except VaultNotConfigured as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e

    return {"detail": result.detail, "connection": await _single_status(db, user.id, provider)}


@router.delete("/{provider}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_connection(
    provider: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    _ensure_known(provider)
    user = await get_default_user(db)
    await credentials.delete_api_key(db, user.id, provider)
