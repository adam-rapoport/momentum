"""Shared document→memories ingestion used by onboarding and the Memory panel.

One uploaded PDF/Word/Markdown/text file becomes:
  1. a `reference` memory holding the full text (committed first — the source
     of truth is never lost), then
  2. best-effort derived memories extracted by the user's heavy model
     (app.core.memory.extract) — a failure there leaves the reference intact.

Callers differ only in the tags they stamp and the summary note, so those are
parameters; everything else (size cap, parsing, commit ordering) lives here.
"""
from __future__ import annotations

import logging

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ingest import UnsupportedFileType, parse_upload
from app.core.memory.extract import extract_memories_from_document
from app.core.memory.store import save_memory
from app.models import Project, User

logger = logging.getLogger(__name__)

MAX_UPLOAD_BYTES = 10_000_000  # 10 MB


async def ingest_reference_document(
    db: AsyncSession,
    *,
    user: User,
    project: Project,
    filename: str,
    content: bytes,
    reference_tags: list[str],
    extract_tags: list[str],
    summary_note: str,
) -> dict:
    """Parse, store as a reference memory, then extract derived memories.

    Returns {title, memory_id, char_count, memories_created}. Raises
    HTTPException(400) for oversized/unsupported/empty uploads.
    """
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large (max {MAX_UPLOAD_BYTES // 1_000_000} MB).",
        )

    try:
        parsed = parse_upload(filename, content)
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
        summary=summary_note,
        tags=reference_tags,
    )
    # Persist the reference doc first so it's never lost, even if the
    # (best-effort) extraction step below fails.
    await db.commit()
    # Snapshot the id NOW: if extraction fails below, its rollback expires the
    # ORM object, and a later `record.id` would lazy-load outside the async
    # greenlet context (MissingGreenlet → the whole upload 500s even though
    # the document was saved).
    record_id = str(record.id)

    # Have the user's heavy model read the doc and turn its durable facts into
    # their own memories, so the agent has real context — not just a doc it
    # has to be asked to look up. Best-effort: a failure here leaves the
    # reference memory (already committed) intact.
    memories_created = 0
    try:
        derived = await extract_memories_from_document(
            db,
            user=user,
            project=project,
            doc_title=parsed.title,
            doc_text=parsed.text,
            tags=extract_tags,
        )
        await db.commit()
        memories_created = len(derived)
    except Exception:  # noqa: BLE001 — never let extraction break the upload
        await db.rollback()
        logger.exception("reference-doc memory extraction failed (reference saved)")

    return {
        "title": parsed.title,
        "memory_id": record_id,
        "char_count": len(parsed.text),
        "memories_created": memories_created,
    }
