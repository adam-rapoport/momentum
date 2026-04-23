"""Google Docs adapter — exposes the same `read/write/edit/list` interface
as `app/core/documents/local_store.py` so the tools don't care which
backend they're hitting.

Design choices for MVP simplicity:
- Google-backed documents are identified by Google's own `documentId`. Our
  local `document_id` (a slug derived from the title) is stored in the
  doc's metadata so we can map slug → Google ID without a DB table.
- Listing: we keep a per-user index stored in the Integration.meta JSONB
  column (`google_doc_index: {slug: google_doc_id}`). Cheap and avoids a
  Drive-wide search. Cost: stale if the user deletes a doc on Google's
  side — we just surface a "not found" on read.
- Edit: fetch full plain-text body → exact-string replace → replace the
  whole body. Loses rich formatting on the replaced section but works
  reliably for a markdown-first UX. Same substring semantics as the local
  adapter.

Formatting caveat: Google Docs isn't markdown natively. We write headings
as prefix strings ("# ", "## ", bullets as "• ") — readable in Google
Docs but not true heading blocks. Adam gets a real Google Doc with the
content; true structural fidelity (headings, tables) is deferred.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from google.oauth2.credentials import Credentials as GoogleCredentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.documents.local_store import DocumentInfo
from app.core.integrations.google_oauth import (
    OAuthFlowError,
    PROVIDER,
    SCOPES,
    get_valid_access_token,
)
from app.core.memory.store import slugify
from app.models import Integration

logger = logging.getLogger(__name__)


class GoogleDocsNotConnected(RuntimeError):
    pass


class GoogleDocsError(RuntimeError):
    """Any Google API failure the user can act on — usually 'reconnect.'"""


async def _get_integration(db: AsyncSession, user_id) -> Integration:
    integration = await db.scalar(
        select(Integration).where(
            Integration.user_id == user_id, Integration.provider == PROVIDER
        )
    )
    if integration is None or integration.status != "connected":
        raise GoogleDocsNotConnected(
            "Google Docs is not connected. Visit Settings to connect."
        )
    return integration


async def _build_services(db: AsyncSession, integration: Integration):
    """Build the Docs + Drive clients with a currently-valid access token."""
    access_token = await get_valid_access_token(db, integration)
    creds = GoogleCredentials(token=access_token, scopes=SCOPES)
    # Both google-api-python-client calls are sync — we run them in a thread
    # so the event loop isn't blocked on Google I/O.
    docs = await asyncio.to_thread(build, "docs", "v1", credentials=creds, cache_discovery=False)
    drive = await asyncio.to_thread(build, "drive", "v3", credentials=creds, cache_discovery=False)
    return docs, drive


def _doc_url(google_doc_id: str) -> str:
    return f"https://docs.google.com/document/d/{google_doc_id}/edit"


def _extract_plaintext(doc: dict) -> str:
    """Walk a Google Docs JSON body and concatenate run text into a single
    plain-text string. Good enough for exact-string editing; loses style."""
    out: list[str] = []
    for element in (doc.get("body") or {}).get("content", []):
        para = element.get("paragraph")
        if not para:
            continue
        for run in para.get("elements", []):
            tr = run.get("textRun")
            if tr and "content" in tr:
                out.append(tr["content"])
    return "".join(out)


def _get_index(integration: Integration) -> dict[str, str]:
    return dict(((integration.meta or {}).get("google_doc_index") or {}))


def _set_index(integration: Integration, index: dict[str, str]) -> None:
    meta = dict(integration.meta or {})
    meta["google_doc_index"] = index
    integration.meta = meta


# ---------- Public interface (matches local_store shape) ----------


@dataclass
class GoogleDocInfo(DocumentInfo):
    """Extends DocumentInfo with a Google-specific URL field."""
    google_doc_id: str = ""
    url: str = ""


async def write_document(
    db: AsyncSession,
    user_id,
    title: str,
    content_markdown: str,
    document_id: str | None = None,
) -> GoogleDocInfo:
    integration = await _get_integration(db, user_id)
    docs, _ = await _build_services(db, integration)

    slug = slugify(document_id) if document_id else slugify(title)
    index = _get_index(integration)
    google_doc_id = index.get(slug)

    def _sync_write() -> tuple[str, int]:
        nonlocal google_doc_id
        if google_doc_id:
            # Overwrite: replace entire body with new content
            current = docs.documents().get(documentId=google_doc_id).execute()
            body_len = sum(
                el.get("endIndex", 1) - el.get("startIndex", 1)
                for el in (current.get("body") or {}).get("content", [])
            )
            requests: list[dict] = []
            # First wipe (if there's any content beyond the terminating newline)
            if body_len > 1:
                requests.append(
                    {
                        "deleteContentRange": {
                            "range": {"startIndex": 1, "endIndex": body_len},
                        }
                    }
                )
            requests.append(
                {"insertText": {"location": {"index": 1}, "text": content_markdown}}
            )
            docs.documents().batchUpdate(
                documentId=google_doc_id, body={"requests": requests}
            ).execute()
        else:
            created = docs.documents().create(body={"title": title}).execute()
            google_doc_id = created["documentId"]
            docs.documents().batchUpdate(
                documentId=google_doc_id,
                body={
                    "requests": [
                        {"insertText": {"location": {"index": 1}, "text": content_markdown}}
                    ]
                },
            ).execute()
        return google_doc_id, len(content_markdown)

    try:
        google_doc_id, char_count = await asyncio.to_thread(_sync_write)
    except HttpError as e:
        raise GoogleDocsError(f"Google Docs write failed: {e}") from e
    except OAuthFlowError:
        raise

    # Update the slug -> google_doc_id index on the Integration row
    index[slug] = google_doc_id
    _set_index(integration, index)
    await db.commit()

    now = datetime.now(timezone.utc).isoformat()
    return GoogleDocInfo(
        document_id=slug,
        title=title,
        file_path=_doc_url(google_doc_id),
        created_at=now,
        updated_at=now,
        char_count=char_count,
        google_doc_id=google_doc_id,
        url=_doc_url(google_doc_id),
    )


async def read_document(db: AsyncSession, user_id, document_id: str) -> tuple[dict, str]:
    integration = await _get_integration(db, user_id)
    index = _get_index(integration)
    google_doc_id = index.get(document_id)
    if not google_doc_id:
        raise FileNotFoundError(f"document '{document_id}' not found")
    docs, _ = await _build_services(db, integration)

    try:
        doc = await asyncio.to_thread(
            lambda: docs.documents().get(documentId=google_doc_id).execute()
        )
    except HttpError as e:
        if e.resp.status == 404:
            raise FileNotFoundError(f"document '{document_id}' not found on Google") from e
        raise GoogleDocsError(f"Google Docs read failed: {e}") from e

    body = _extract_plaintext(doc).rstrip("\n")
    fm = {
        "title": doc.get("title") or document_id,
        "slug": document_id,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "google_doc_id": google_doc_id,
        "url": _doc_url(google_doc_id),
    }
    return fm, body


async def edit_document(
    db: AsyncSession,
    user_id,
    document_id: str,
    old_string: str,
    new_string: str,
    expected_occurrences: int = 1,
) -> GoogleDocInfo:
    integration = await _get_integration(db, user_id)
    index = _get_index(integration)
    google_doc_id = index.get(document_id)
    if not google_doc_id:
        raise FileNotFoundError(f"document '{document_id}' not found")

    fm, body = await read_document(db, user_id, document_id)
    actual = body.count(old_string)
    if actual != expected_occurrences:
        raise ValueError(
            f"old_string appeared {actual} time(s) in document body, "
            f"expected {expected_occurrences}. "
            f"Use ReadDocument to see the current content, then retry with exact text."
        )
    new_body = body.replace(old_string, new_string)

    # Rewrite the whole body. This loses any existing rich formatting.
    await write_document(
        db,
        user_id,
        title=fm.get("title") or document_id,
        content_markdown=new_body,
        document_id=document_id,
    )
    now = datetime.now(timezone.utc).isoformat()
    return GoogleDocInfo(
        document_id=document_id,
        title=fm.get("title") or document_id,
        file_path=_doc_url(google_doc_id),
        created_at=now,
        updated_at=now,
        char_count=len(new_body),
        google_doc_id=google_doc_id,
        url=_doc_url(google_doc_id),
    )


async def list_documents(db: AsyncSession, user_id) -> list[GoogleDocInfo]:
    integration = await _get_integration(db, user_id)
    index = _get_index(integration)
    if not index:
        return []
    docs, _ = await _build_services(db, integration)

    results: list[GoogleDocInfo] = []

    def _sync_list() -> list[GoogleDocInfo]:
        out: list[GoogleDocInfo] = []
        for slug, google_doc_id in index.items():
            try:
                doc: dict[str, Any] = (
                    docs.documents().get(documentId=google_doc_id).execute()
                )
            except HttpError as e:
                if e.resp.status == 404:
                    continue  # stale index entry — skip silently
                logger.warning("google docs list error for %s: %s", slug, e)
                continue
            body = _extract_plaintext(doc)
            out.append(
                GoogleDocInfo(
                    document_id=slug,
                    title=doc.get("title") or slug,
                    file_path=_doc_url(google_doc_id),
                    created_at="",
                    updated_at=datetime.now(timezone.utc).isoformat(),
                    char_count=len(body),
                    google_doc_id=google_doc_id,
                    url=_doc_url(google_doc_id),
                )
            )
        return out

    results = await asyncio.to_thread(_sync_list)
    return results


async def is_connected(db: AsyncSession, user_id) -> bool:
    integration = await db.scalar(
        select(Integration).where(
            Integration.user_id == user_id, Integration.provider == PROVIDER
        )
    )
    return integration is not None and integration.status == "connected"
