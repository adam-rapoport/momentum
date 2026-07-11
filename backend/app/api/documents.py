"""REST endpoints for the artifacts panel in the frontend.

Listing is a thin wrapper around `app.core.documents.router.list_documents`
(which merges Google Docs + local-store views behind a `backend`
discriminator). Export converts a LOCAL document's markdown to Word/PDF on
demand — either written to a caller-chosen path (the desktop Save dialog)
or streamed back as a download (web dev).
"""
import asyncio
from pathlib import Path
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.default_user import get_default_project, get_default_user
from app.core.documents import local_store
from app.core.documents import router as docs_router
from app.core.documents.export import export_markdown, media_type_for
from app.core.memory.store import slugify
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


class DocumentExportRequest(BaseModel):
    document_id: str
    format: Literal["docx", "pdf"]
    project_id: UUID | None = None
    # Absolute target path chosen in the desktop Save dialog. Omitted in web
    # dev, where the converted bytes come back as a browser download instead.
    dest_path: str | None = None


@router.post("/export")
async def export_document_artifact(
    req: DocumentExportRequest,
    db: AsyncSession = Depends(get_db),
):
    project = await _resolve_project(db, req.project_id)
    try:
        frontmatter, body = await local_store.read_document(project, req.document_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="document not found") from None
    title = frontmatter.get("title") or req.document_id
    # CPU-bound (reportlab layout can take a few hundred ms on long docs) —
    # keep it off the event loop.
    data = await asyncio.to_thread(export_markdown, body, title, req.format)

    if req.dest_path:
        dest = Path(req.dest_path).expanduser()
        if not dest.is_absolute():
            raise HTTPException(status_code=400, detail="destination must be an absolute path")
        if not dest.parent.is_dir():
            raise HTTPException(status_code=400, detail="destination folder does not exist")
        await asyncio.to_thread(dest.write_bytes, data)
        return {"file_path": str(dest)}

    filename = f"{slugify(title) or req.document_id}.{req.format}"
    return Response(
        content=data,
        media_type=media_type_for(req.format),
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
