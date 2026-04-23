"""REST endpoint for the artifacts panel in the frontend.

Thin wrapper around `app.core.documents.router.list_documents`. That
function already merges Google Docs + local-store views into a single
list with a `backend` discriminator, so we just expose it over HTTP.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.default_user import get_default_project, get_default_user
from app.core.documents import router as docs_router
from app.dependencies import get_db
from app.models import Project
from app.schemas.document import DocumentArtifact

router = APIRouter(prefix="/documents", tags=["documents"])


async def _resolve_project(db: AsyncSession, project_id: UUID | None) -> Project:
    if project_id is None:
        user = await get_default_user(db)
        return await get_default_project(db, user.organization_id)
    project = await db.scalar(select(Project).where(Project.id == project_id))
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")
    return project


@router.get("", response_model=list[DocumentArtifact])
async def list_document_artifacts(
    project_id: UUID | None = None,
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    project = await _resolve_project(db, project_id)
    user = await get_default_user(db)
    return await docs_router.list_documents(db=db, user_id=user.id, project=project)
