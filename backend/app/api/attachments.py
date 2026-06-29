"""Chat attachments — parse an uploaded doc and stash its text for one turn.

A file attached to a chat message is parsed to text and cached in the KV store
under `attachment:<id>` (1-hour TTL). The id rides along with the next
`session.message`; the session engine pulls the text back out and feeds it to
the model as context for that turn. Unlike the Memory-panel upload this does
NOT create a permanent memory — it's transient per-turn context, like dropping
a file into a chatbot.
"""
from __future__ import annotations

import json
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.core.ingest import parse_upload
from app.core.local_store import LocalKVStore
from app.dependencies import get_kv

router = APIRouter(prefix="/chat", tags=["chat"])

# Per-attachment text cap (chars) and how long the cached text lives before the
# user sends the message it's attached to.
MAX_ATTACHMENT_CHARS = 16_000
ATTACHMENT_TTL_SECONDS = 3600


def attachment_key(attachment_id: str) -> str:
    return f"attachment:{attachment_id}"


@router.post("/attachments")
async def upload_chat_attachment(
    file: UploadFile = File(...),
    kv: LocalKVStore = Depends(get_kv),
) -> dict:
    """Parse a PDF/DOCX/MD/TXT into text and cache it for the next turn."""
    content = await file.read()
    try:
        parsed = parse_upload(file.filename or "upload", content)
    except ValueError as e:  # unsupported type / unreadable
        raise HTTPException(status_code=400, detail=str(e)) from e
    text = parsed.text.strip()
    if not text:
        raise HTTPException(
            status_code=400,
            detail=f"No readable text found in '{parsed.title}'.",
        )
    attachment_id = str(uuid4())
    await kv.set(
        attachment_key(attachment_id),
        json.dumps({"filename": parsed.title, "text": text[:MAX_ATTACHMENT_CHARS]}),
        ex=ATTACHMENT_TTL_SECONDS,
    )
    return {
        "attachment_id": attachment_id,
        "filename": parsed.title,
        "char_count": len(parsed.text),
    }
