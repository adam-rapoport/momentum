"""Reference-doc upload → heavy-model memory extraction (feedback #5, Group 3).

Covers:
  - the heavy model's output is turned into real memories (stubbed model),
  - extraction is skipped cleanly when no provider key is available,
  - the upload endpoint keeps the reference memory even if extraction blows up.
"""
from __future__ import annotations

from io import BytesIO

import pytest
from fastapi import UploadFile

from app.api import onboarding
from app.config import settings
from app.core.groq_client import StreamResult
from app.core.memory import extract as extract_mod
from app.core.memory.extract import extract_memories_from_document
from app.core.memory.store import list_memories

pytestmark = pytest.mark.asyncio


def _fake_stream(text: str):
    """Build an async-generator stand-in for llm.stream_message that yields a
    single final StreamResult carrying `text`."""

    async def _gen(messages, model=None, tools=None, api_key=None):
        yield StreamResult(text=text)

    return _gen


def _const_async(value):
    async def _f(*args, **kwargs):
        return value

    return _f


@pytest.fixture(autouse=True)
def _tmp_memory_root(tmp_path, monkeypatch):
    """Write memory markdown to a throwaway dir, not the repo's data/memory."""
    monkeypatch.setattr(settings, "memory_root", str(tmp_path / "memory"))


async def test_extract_creates_memories_from_stubbed_model(db, seeded, monkeypatch):
    user, project = seeded["user"], seeded["project"]
    reply = """[
      {"type": "stakeholder", "title": "Sarah (VP Eng)",
       "summary": "Owns engineering.",
       "content": "Sarah is VP of Engineering and prefers async updates."},
      {"type": "decision", "title": "Q3 focus is activation",
       "summary": "Set in planning.",
       "content": "The team decided Q3's priority is activation."}
    ]"""
    monkeypatch.setattr(extract_mod.llm, "stream_message", _fake_stream(reply))
    monkeypatch.setattr(extract_mod.credentials, "resolve_api_key", _const_async("test-key"))

    created = await extract_memories_from_document(
        db, user=user, project=project, doc_title="Team doc", doc_text="full text here"
    )
    await db.commit()

    assert len(created) == 2
    assert {m.type for m in created} == {"stakeholder", "decision"}

    stored = await list_memories(db=db, project=project)
    assert "Sarah (VP Eng)" in {m.title for m in stored}


async def test_extract_skips_when_no_key(db, seeded, monkeypatch):
    user, project = seeded["user"], seeded["project"]
    monkeypatch.setattr(extract_mod.credentials, "resolve_api_key", _const_async(None))
    # If the model were called despite no key, surface it as a failure.
    monkeypatch.setattr(extract_mod.llm, "stream_message", _fake_stream("should-not-run"))

    created = await extract_memories_from_document(
        db, user=user, project=project, doc_title="x", doc_text="y"
    )
    assert created == []


async def test_upload_keeps_reference_when_extraction_fails(db, seeded, monkeypatch):
    user, project = seeded["user"], seeded["project"]
    monkeypatch.setattr(onboarding, "get_default_user", _const_async(user))
    monkeypatch.setattr(onboarding, "get_default_project", _const_async(project))
    monkeypatch.setattr(
        onboarding, "extract_memories_from_document", _const_async_raises()
    )

    upload = UploadFile(BytesIO(b"# Notes\n\nSarah is VP Eng."), filename="ref.md")
    result = await onboarding.upload_document(file=upload, db=db)

    # Extraction failed, but the upload still succeeds and the doc is saved.
    assert result["memories_created"] == 0
    assert result["memory_id"]
    refs = await list_memories(db=db, project=project, mem_type="reference")
    assert len(refs) == 1


def _const_async_raises():
    async def _boom(*args, **kwargs):
        raise RuntimeError("model unavailable")

    return _boom
