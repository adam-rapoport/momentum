"""Onboarding REST API — C8 (Sprint 7).

Backs the first-run wizard. For now it exposes the gating signal the
frontend uses to decide whether to show onboarding, plus a "mark complete"
write. The getting-to-know-you endpoints (profile text + document upload)
are added in a later phase.

Endpoints:
  GET  /api/v1/onboarding/status    — is the app configured enough to chat?
  POST /api/v1/onboarding/complete  — record that the wizard was finished
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import credentials
from app.core.default_user import get_default_project, get_default_user
from app.core.ingest import UnsupportedFileType, parse_upload
from app.core.memory.store import save_memory
from app.core.model_registry import get_available_models
from app.dependencies import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/onboarding", tags=["onboarding"])

MAX_UPLOAD_BYTES = 10_000_000  # 10 MB


class ProfilePayload(BaseModel):
    # All optional — the user fills in whatever they want.
    role: str | None = None          # role & working style
    company: str | None = None       # company & product
    goals: str | None = None         # goals & key stakeholders


@router.get("/status")
async def onboarding_status(db: AsyncSession = Depends(get_db)) -> dict:
    user = await get_default_user(db)
    configured = await credentials.configured_llm_providers(db, user.id)
    has_light = bool(
        get_available_models(role="light", configured_providers=configured)
    )
    has_heavy = bool(
        get_available_models(role="heavy", configured_providers=configured)
    )
    completed_at = (user.preferences or {}).get("onboarding_completed_at")
    # "configured" = enough to start chatting (at least one usable LLM key).
    return {
        "configured": bool(configured),
        "has_light_provider": has_light,
        "has_heavy_provider": has_heavy,
        "completed_at": completed_at,
    }


@router.post("/complete")
async def complete_onboarding(db: AsyncSession = Depends(get_db)) -> dict:
    user = await get_default_user(db)
    prefs = dict(user.preferences or {})
    prefs["onboarding_completed_at"] = datetime.now(timezone.utc).isoformat()
    user.preferences = prefs
    await db.flush()
    await db.commit()
    return {"completed_at": prefs["onboarding_completed_at"]}


@router.post("/profile")
async def save_profile(
    payload: ProfilePayload,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Write the getting-to-know-you answers into the memory system so the
    agent has context from message one. Each non-empty section becomes a
    memory record (reusing the same store the SaveMemory tool uses)."""
    user = await get_default_user(db)
    project = await get_default_project(db, user.organization_id)

    # (section text, memory type, title) — only the sections the user filled.
    sections = [
        (payload.role, "team", "About me & how I work"),
        (payload.company, "product", "Company & product"),
        (payload.goals, "product", "Goals & key stakeholders"),
    ]
    written: list[str] = []
    for content, mem_type, title in sections:
        if content and content.strip():
            await save_memory(
                db=db,
                project=project,
                mem_type=mem_type,
                title=title,
                content=content.strip(),
                summary="Captured during onboarding",
                tags=["onboarding"],
            )
            written.append(title)

    await db.commit()
    return {"saved": written}


@router.post("/documents")
async def upload_document(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Parse an uploaded PDF/Word/Markdown/text file and store its text as a
    `reference` memory record."""
    user = await get_default_user(db)
    project = await get_default_project(db, user.organization_id)

    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large (max {MAX_UPLOAD_BYTES // 1_000_000} MB).",
        )

    try:
        parsed = parse_upload(file.filename or "upload", content)
    except UnsupportedFileType as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e

    if not parsed.text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Couldn't extract any text from that file.",
        )

    record = await save_memory(
        db=db,
        project=project,
        mem_type="reference",
        title=parsed.title,
        content=parsed.text,
        summary=f"Uploaded during onboarding ({file.filename})",
        tags=["onboarding", "upload"],
    )
    await db.commit()
    return {
        "title": parsed.title,
        "memory_id": str(record.id),
        "char_count": len(parsed.text),
    }
