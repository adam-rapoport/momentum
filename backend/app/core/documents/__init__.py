"""Document storage for the PM agent.

Design mirrors the memory system: markdown files on disk are the source of
truth. Chunk A ships the local-filesystem implementation; Chunk D adds a
Google Docs adapter with the same interface so the tools stay unchanged.

Public interface (implemented by every adapter):

    async def read_document(project, document_id) -> tuple[frontmatter, body]
    async def write_document(project, title, content_markdown, document_id=None) -> DocumentInfo
    async def edit_document(project, document_id, old_string, new_string, expected_occurrences) -> DocumentInfo
    async def list_documents(project) -> list[DocumentInfo]

For now we re-export from `local_store` directly; the router swap happens in Chunk D.
"""
from __future__ import annotations

from app.core.documents.local_store import (
    DocumentInfo,
    edit_document,
    list_documents,
    read_document,
    write_document,
)

__all__ = [
    "DocumentInfo",
    "read_document",
    "write_document",
    "edit_document",
    "list_documents",
]
