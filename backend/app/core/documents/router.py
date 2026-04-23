"""Routes document operations between the local-filesystem store and the
Google Docs adapter based on the user's integration state.

Design for simplicity (per plan):
- **Write**: if Google connected, write to Google. Else local.
- **Read/Edit**: look up whether the document lives in Google (checked via
  the slug -> google_doc_id index on the Integration row). If it does and
  Google is connected, route there. Otherwise try local. This way docs
  created in one mode don't silently disappear when the user flips state.
- **List**: when Google is connected, return Google docs + any local docs
  that aren't also in the Google index. When disconnected, local only.

The tools (`ReadDocument`, `WriteDocument`, …) call the router; they never
talk to the adapters directly.
"""
from __future__ import annotations

import logging
from dataclasses import asdict
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.documents import local_store
from app.core.integrations import google_docs as gdocs
from app.core.integrations.google_oauth import PROVIDER as GOOGLE_PROVIDER
from app.models import Integration, Project

logger = logging.getLogger(__name__)


async def _google_index(db: AsyncSession, user_id: UUID) -> dict[str, str]:
    """Returns the slug -> google_doc_id map, or {} if not connected."""
    integration = await db.scalar(
        select(Integration).where(
            Integration.user_id == user_id, Integration.provider == GOOGLE_PROVIDER
        )
    )
    if integration is None or integration.status != "connected":
        return {}
    return dict(((integration.meta or {}).get("google_doc_index") or {}))


def _info_from_google(info: gdocs.GoogleDocInfo) -> dict[str, Any]:
    d = asdict(info)
    d["backend"] = "google_docs"
    return d


def _info_from_local(info: local_store.DocumentInfo) -> dict[str, Any]:
    d = asdict(info)
    d["backend"] = "local"
    d["url"] = None
    d["google_doc_id"] = None
    return d


async def write_document(
    db: AsyncSession,
    user_id: UUID,
    project: Project,
    title: str,
    content_markdown: str,
    document_id: str | None = None,
) -> dict:
    """Write to Google if connected, otherwise local."""
    if await gdocs.is_connected(db, user_id):
        info = await gdocs.write_document(
            db, user_id, title=title, content_markdown=content_markdown, document_id=document_id
        )
        return _info_from_google(info)
    info = await local_store.write_document(
        project=project, title=title, content_markdown=content_markdown, document_id=document_id
    )
    return _info_from_local(info)


async def read_document(
    db: AsyncSession, user_id: UUID, project: Project, document_id: str
) -> tuple[dict, str, str]:
    """Returns (frontmatter_dict, body, backend_name)."""
    index = await _google_index(db, user_id)
    if document_id in index:
        fm, body = await gdocs.read_document(db, user_id, document_id)
        return fm, body, "google_docs"
    fm, body = await local_store.read_document(project, document_id)
    return fm, body, "local"


async def edit_document(
    db: AsyncSession,
    user_id: UUID,
    project: Project,
    document_id: str,
    old_string: str,
    new_string: str,
    expected_occurrences: int = 1,
) -> dict:
    index = await _google_index(db, user_id)
    if document_id in index:
        info = await gdocs.edit_document(
            db,
            user_id,
            document_id=document_id,
            old_string=old_string,
            new_string=new_string,
            expected_occurrences=expected_occurrences,
        )
        return _info_from_google(info)
    info = await local_store.edit_document(
        project=project,
        document_id=document_id,
        old_string=old_string,
        new_string=new_string,
        expected_occurrences=expected_occurrences,
    )
    return _info_from_local(info)


async def get_document_url(
    db: AsyncSession, user_id: UUID, document_id: str
) -> str | None:
    """Cheap lookup used when building the approval bar — return the
    Google Docs URL for this slug if we have one, else None (meaning it's
    either a local doc or doesn't exist)."""
    index = await _google_index(db, user_id)
    google_doc_id = index.get(document_id)
    if not google_doc_id:
        return None
    return f"https://docs.google.com/document/d/{google_doc_id}/edit"


async def list_documents(
    db: AsyncSession, user_id: UUID, project: Project
) -> list[dict]:
    """Merge Google + local views so users don't "lose" docs on flip."""
    out: list[dict] = []
    google_slugs: set[str] = set()

    if await gdocs.is_connected(db, user_id):
        for info in await gdocs.list_documents(db, user_id):
            out.append(_info_from_google(info))
            google_slugs.add(info.document_id)

    for info in await local_store.list_documents(project):
        if info.document_id in google_slugs:
            continue  # already represented by the Google entry
        out.append(_info_from_local(info))

    return out
