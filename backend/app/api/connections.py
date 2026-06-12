"""Connections REST API — C8 (Sprint 7).

Manages user-supplied provider API keys (LLM + search) that the Connections
UI collects, replacing hand-edited `.env` entries. Keys are stored
Fernet-encrypted via `app.core.credentials`; this module only ever returns
masked, secret-free status.

Endpoints:
  GET    /api/v1/connections                      — status of all key providers
  GET    /api/v1/connections/ollama/models        — installed local models
  POST   /api/v1/connections/{provider}/validate  — live ✓/✗ ping (no store)
  PUT    /api/v1/connections/{provider}           — validate-then-store a key
  DELETE /api/v1/connections/{provider}           — remove a stored key
"""
from __future__ import annotations

import asyncio
import logging

import httpx
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


@router.get("/ollama/models")
async def list_ollama_models(db: AsyncSession = Depends(get_db)) -> dict:
    """Installed models on the user's Ollama server, for the model dropdown.

    Ollama's catalog is whatever the user has pulled locally, so the list is
    live: GET {base}/api/tags for the names, then POST {base}/api/show per
    model (best-effort, parallel) for tool-calling capability + context
    length. Local-only calls — works identically from the packaged sidecar.
    """
    user = await get_default_user(db)
    base = await credentials.resolve_api_key(db, user.id, "llm:ollama")
    if not base:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ollama is not connected — add your server URL first.",
        )
    base = base.rstrip("/")

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            res = await client.get(f"{base}/api/tags")
            res.raise_for_status()
            names = [
                m.get("name") or m.get("model")
                for m in (res.json().get("models") or [])
            ]
            names = [n for n in names if n]
        except Exception as e:  # noqa: BLE001 — server down/not ollama/etc.
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Couldn't reach Ollama at {base} — is it running?",
            ) from e

        async def _details(name: str) -> dict:
            supports_tools = False
            context_length: int | None = None
            try:
                show = await client.post(f"{base}/api/show", json={"model": name})
                show.raise_for_status()
                body = show.json()
                supports_tools = "tools" in (body.get("capabilities") or [])
                info = body.get("model_info") or {}
                for key, value in info.items():
                    if key.endswith(".context_length") and isinstance(value, int):
                        context_length = value
                        break
            except Exception:  # noqa: BLE001 — capability probe is best-effort
                pass
            return {
                "id": f"ollama:{name}",
                "name": name,
                "supports_tools": supports_tools,
                "context_length": context_length,
            }

        models = list(await asyncio.gather(*(_details(n) for n in names[:50])))

    return {"base_url": base, "models": models}


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
