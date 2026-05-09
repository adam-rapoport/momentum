"""User preferences REST API — Sprint 6 Chunk C.

Currently exposes the model preferences slice. Stored under the existing
`users.preferences` JSONB column (no migration needed) using the keys
`light_model` and `heavy_model`.

Endpoints:
  GET  /api/v1/preferences/models   — current picks + available registry
  PUT  /api/v1/preferences/models   — update one or both picks
"""
from __future__ import annotations

import logging
from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.default_user import get_default_user
from app.core.model_registry import get_available_models, is_model_available
from app.dependencies import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/preferences", tags=["preferences"])


class ModelPreferencesUpdate(BaseModel):
    light_model: str | None = Field(
        None,
        description=(
            "Model ID for the light slot. Pass an empty string or null to "
            "clear the preference and fall back to the env-var default."
        ),
    )
    heavy_model: str | None = Field(
        None,
        description=(
            "Model ID for the heavy slot. Pass an empty string or null to "
            "clear the preference and fall back to the env-var default."
        ),
    )


def _public_view(user_preferences: dict) -> dict:
    light_pick = user_preferences.get("light_model") or None
    heavy_pick = user_preferences.get("heavy_model") or None

    available_light = [asdict(m) for m in get_available_models(role="light")]
    available_heavy = [asdict(m) for m in get_available_models(role="heavy")]

    return {
        "light_model": light_pick,
        "heavy_model": heavy_pick,
        "effective_light_model": (
            light_pick
            if light_pick and is_model_available(light_pick, role="light")
            else settings.groq_model
        ),
        "effective_heavy_model": (
            heavy_pick
            if heavy_pick and is_model_available(heavy_pick, role="heavy")
            else settings.groq_heavy_model
        ),
        "available_light_models": available_light,
        "available_heavy_models": available_heavy,
    }


@router.get("/models")
async def get_model_preferences(db: AsyncSession = Depends(get_db)) -> dict:
    user = await get_default_user(db)
    return _public_view(user.preferences or {})


@router.put("/models")
async def put_model_preferences(
    payload: ModelPreferencesUpdate,
    db: AsyncSession = Depends(get_db),
) -> dict:
    user = await get_default_user(db)
    prefs = dict(user.preferences or {})

    raw = payload.model_dump(exclude_unset=True)

    if "light_model" in raw:
        new_light = raw["light_model"]
        if new_light:
            if not is_model_available(new_light, role="light"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Model '{new_light}' is not an available light-slot model.",
                )
            prefs["light_model"] = new_light
        else:
            prefs.pop("light_model", None)

    if "heavy_model" in raw:
        new_heavy = raw["heavy_model"]
        if new_heavy:
            if not is_model_available(new_heavy, role="heavy"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Model '{new_heavy}' is not an available heavy-slot model.",
                )
            prefs["heavy_model"] = new_heavy
        else:
            prefs.pop("heavy_model", None)

    user.preferences = prefs
    await db.flush()
    await db.commit()
    return _public_view(prefs)
