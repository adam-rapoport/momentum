"""Memory-panel document upload (feedback round 4).

POST /api/v1/memory/documents shares the onboarding ingestion core
(app.core.doc_ingest) but stamps panel-specific tags (no "onboarding").
"""
from __future__ import annotations

from io import BytesIO

import pytest
from fastapi import HTTPException, UploadFile

from app.api import memory as memory_api
from app.config import settings
from app.core import doc_ingest
from app.core.memory.store import list_memories

pytestmark = pytest.mark.asyncio


def _const_async(value):
    async def _f(*args, **kwargs):
        return value

    return _f


@pytest.fixture(autouse=True)
def _tmp_memory_root(tmp_path, monkeypatch):
    """Write memory markdown to a throwaway dir, not the repo's data/memory."""
    monkeypatch.setattr(settings, "memory_root", str(tmp_path / "memory"))


@pytest.fixture
def _as_seeded_user(seeded, monkeypatch):
    monkeypatch.setattr(memory_api, "get_default_user", _const_async(seeded["user"]))
    monkeypatch.setattr(
        memory_api, "get_default_project", _const_async(seeded["project"])
    )


async def test_memory_upload_saves_reference_with_panel_tags(
    db, seeded, monkeypatch, _as_seeded_user
):
    # Stub extraction: this test is about the route + tags, not the model.
    monkeypatch.setattr(
        doc_ingest, "extract_memories_from_document", _const_async([])
    )

    upload = UploadFile(BytesIO(b"# Strategy\n\nWe focus on activation."), filename="strategy.md")
    result = await memory_api.upload_memory_document(file=upload, db=db)

    assert result["memory_id"]
    assert result["memories_created"] == 0
    assert result["char_count"] > 0

    refs = await list_memories(db=db, project=seeded["project"], mem_type="reference")
    assert len(refs) == 1
    # Panel uploads are NOT tagged "onboarding".
    assert refs[0].tags == ["upload"]


async def test_memory_upload_rejects_unsupported_extension(
    db, seeded, _as_seeded_user
):
    upload = UploadFile(BytesIO(b"binary"), filename="photo.png")
    with pytest.raises(HTTPException) as exc:
        await memory_api.upload_memory_document(file=upload, db=db)
    assert exc.value.status_code == 400


async def test_memory_upload_passes_panel_extract_tags(
    db, seeded, monkeypatch, _as_seeded_user
):
    captured: dict = {}

    async def _capture(db_, **kwargs):
        captured.update(kwargs)
        return []

    monkeypatch.setattr(doc_ingest, "extract_memories_from_document", _capture)

    upload = UploadFile(BytesIO(b"notes"), filename="notes.txt")
    await memory_api.upload_memory_document(file=upload, db=db)

    assert captured["tags"] == ["from-document"]
