"""REST endpoints for the memory panel in the frontend.

List is served from the DB index; detail reads the markdown body from disk.
Document upload reuses the onboarding ingestion pipeline (reference memory +
heavy-model extraction) with panel-specific tags.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.default_user import get_default_project, get_default_user
from app.core.doc_ingest import ingest_reference_document
from app.core.memory.store import list_memories, read_memory_file
from app.dependencies import get_db
from app.models import MemoryRecord, Project
from app.schemas.memory import MemoryRecordDetail, MemoryRecordSummary

router = APIRouter(prefix="/memory", tags=["memory"])


async def _resolve_project(
    db: AsyncSession, project_id: UUID | None
) -> Project:
    if project_id is None:
        user = await get_default_user(db)
        return await get_default_project(db, user.organization_id)
    project = await db.scalar(select(Project).where(Project.id == project_id))
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")
    return project


@router.get("", response_model=list[MemoryRecordSummary])
async def list_memory_records(
    project_id: UUID | None = None,
    q: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> list[MemoryRecord]:
    """List memories, optionally filtered by `q` — a case-insensitive keyword
    match over each memory's name AND content (via the search_text index)."""
    project = await _resolve_project(db, project_id)
    return await list_memories(db=db, project=project, q=q)


@router.post("/documents")
async def upload_memory_document(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Upload a document from the Memory panel: store its text as a
    `reference` memory, then extract derived memories (best-effort)."""
    user = await get_default_user(db)
    project = await get_default_project(db, user.organization_id)
    content = await file.read()
    return await ingest_reference_document(
        db,
        user=user,
        project=project,
        filename=file.filename or "upload",
        content=content,
        reference_tags=["upload"],
        extract_tags=["from-document"],
        summary_note=f"Uploaded from the Memory panel ({file.filename})",
    )


@router.get("/{record_id}", response_model=MemoryRecordDetail)
async def get_memory_record(
    record_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> dict:
    record = await db.scalar(select(MemoryRecord).where(MemoryRecord.id == record_id))
    if record is None:
        raise HTTPException(status_code=404, detail="memory record not found")
    _, body = read_memory_file(record)
    return {
        "id": record.id,
        "project_id": record.project_id,
        "type": record.type,
        "title": record.title,
        "slug": record.slug,
        "summary": record.summary,
        "tags": record.tags,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
        "file_path": record.file_path,
        "body": body.strip(),
    }
