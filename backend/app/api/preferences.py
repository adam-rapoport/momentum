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
from app.core import credentials
from app.core.default_user import get_default_user
from app.core.model_registry import REGISTRY, get_available_models, is_model_available
from app.core.search import DEFAULT_PROVIDER, VALID_PROVIDERS
from app.dependencies import get_db
from app.models import Organization

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/preferences", tags=["preferences"])


class SearchPreferenceUpdate(BaseModel):
    provider: str = Field(..., description="Active search provider: 'tavily' or 'perplexity'.")


class ProfileUpdate(BaseModel):
    # Both optional — the onboarding wizard sends whichever the user filled.
    display_name: str | None = Field(
        None, max_length=200, description="What the app calls the user (Sidebar)."
    )
    workspace_name: str | None = Field(
        None, max_length=200, description="The workspace/organization display name."
    )


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


def _public_view(user_preferences: dict, configured: set[str]) -> dict:
    light_pick = user_preferences.get("light_model") or None
    heavy_pick = user_preferences.get("heavy_model") or None

    # Both slots offer EVERY available model — the light/heavy distinction is
    # only about which turns route where, not which models you're allowed to
    # pick. (role stays on each entry as a hint, but doesn't gate the picker.)
    available_all = [
        asdict(m)
        for m in get_available_models(role=None, configured_providers=configured)
    ]
    available_light = available_all
    available_heavy = available_all

    return {
        "light_model": light_pick,
        "heavy_model": heavy_pick,
        # The FULL registry, unfiltered by configured providers — the
        # onboarding wizard offers a model choice BEFORE the key is saved.
        # The PUT endpoint still validates picks against what's configured.
        "registry_models": [asdict(m) for m in REGISTRY],
        "effective_light_model": (
            light_pick
            if light_pick
            and is_model_available(light_pick, configured_providers=configured)
            else settings.groq_model
        ),
        "effective_heavy_model": (
            heavy_pick
            if heavy_pick
            and is_model_available(heavy_pick, configured_providers=configured)
            else settings.groq_heavy_model
        ),
        "available_light_models": available_light,
        "available_heavy_models": available_heavy,
    }


@router.get("/models")
async def get_model_preferences(db: AsyncSession = Depends(get_db)) -> dict:
    user = await get_default_user(db)
    configured = await credentials.configured_llm_providers(db, user.id)
    return _public_view(user.preferences or {}, configured)


@router.put("/models")
async def put_model_preferences(
    payload: ModelPreferencesUpdate,
    db: AsyncSession = Depends(get_db),
) -> dict:
    user = await get_default_user(db)
    configured = await credentials.configured_llm_providers(db, user.id)
    prefs = dict(user.preferences or {})

    raw = payload.model_dump(exclude_unset=True)

    if "light_model" in raw:
        new_light = raw["light_model"]
        if new_light:
            if not is_model_available(new_light, configured_providers=configured):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Model '{new_light}' isn't available — its provider may not be connected.",
                )
            prefs["light_model"] = new_light
        else:
            prefs.pop("light_model", None)

    if "heavy_model" in raw:
        new_heavy = raw["heavy_model"]
        if new_heavy:
            if not is_model_available(new_heavy, configured_providers=configured):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Model '{new_heavy}' isn't available — its provider may not be connected.",
                )
            prefs["heavy_model"] = new_heavy
        else:
            prefs.pop("heavy_model", None)

    user.preferences = prefs
    await db.flush()
    await db.commit()
    return _public_view(prefs, configured)


async def _profile_view(db: AsyncSession) -> dict:
    user = await get_default_user(db)
    org = await db.get(Organization, user.organization_id)
    return {
        "display_name": user.display_name,
        "workspace_name": org.name if org else None,
    }


@router.get("/profile")
async def get_profile(db: AsyncSession = Depends(get_db)) -> dict:
    """The local user's display name + workspace name (drives the Sidebar)."""
    return await _profile_view(db)


@router.put("/profile")
async def put_profile(
    payload: ProfileUpdate,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Set the user's display name and/or workspace name. Blank values are
    ignored so the onboarding wizard can send a partial update without
    wiping the existing name."""
    user = await get_default_user(db)
    raw = payload.model_dump(exclude_unset=True)

    if "display_name" in raw:
        name = (raw["display_name"] or "").strip()
        if name:
            user.display_name = name

    if "workspace_name" in raw:
        workspace = (raw["workspace_name"] or "").strip()
        if workspace:
            org = await db.get(Organization, user.organization_id)
            if org is not None:
                org.name = workspace

    await db.flush()
    await db.commit()
    return await _profile_view(db)


@router.get("/search")
async def get_search_preferences(db: AsyncSession = Depends(get_db)) -> dict:
    user = await get_default_user(db)
    statuses = {s["provider"]: s for s in await credentials.get_key_status(db, user.id)}
    pref = (user.preferences or {}).get("search_provider")
    return {
        "provider": pref if pref in VALID_PROVIDERS else DEFAULT_PROVIDER,
        "tavily_configured": statuses.get("search:tavily", {}).get("configured", False),
        "perplexity_configured": statuses.get("search:perplexity", {}).get("configured", False),
    }


@router.put("/search")
async def put_search_preferences(
    payload: SearchPreferenceUpdate,
    db: AsyncSession = Depends(get_db),
) -> dict:
    if payload.provider not in VALID_PROVIDERS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"provider must be one of {VALID_PROVIDERS}",
        )
    user = await get_default_user(db)
    prefs = dict(user.preferences or {})
    prefs["search_provider"] = payload.provider
    user.preferences = prefs
    await db.flush()
    await db.commit()
    return {"provider": payload.provider}
