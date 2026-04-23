"""Local markdown document store.

Layout:
    <data_root>/documents/<project_slug>/<doc_id>.md

Each file has YAML frontmatter (title, slug, created_at, updated_at) and
a markdown body. Reuses the frontmatter helpers from the memory store so
the on-disk formats look the same.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.core.memory.store import (
    _parse_frontmatter,
    _render_frontmatter,
    get_memory_root,
    slugify,
)
from app.models import Project


@dataclass
class DocumentInfo:
    document_id: str
    title: str
    file_path: str
    created_at: str
    updated_at: str
    char_count: int


def get_documents_root() -> Path:
    """Resolve the documents root. Sits alongside `data/memory/` by default."""
    # Reuse the memory-root resolution logic but point at /documents/ instead.
    # memory_root default ends in `.../data/memory`; we walk up to `data/`.
    mem_root = get_memory_root()
    if mem_root.name == "memory":
        return mem_root.parent / "documents"
    # Honour an explicit override by looking for a sibling `documents` dir.
    return mem_root.parent / "documents"


def project_documents_dir(project: Project) -> Path:
    return get_documents_root() / (project.slug or "default")


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _render(title: str, slug: str, created_at: str, updated_at: str, body: str) -> str:
    frontmatter = _render_frontmatter(
        {
            "title": title,
            "slug": slug,
            "created_at": created_at,
            "updated_at": updated_at,
        }
    )
    body = body.strip() + "\n" if body.strip() else ""
    return f"{frontmatter}\n\n{body}"


def _info_from_file(path: Path, body: str, fm: dict) -> DocumentInfo:
    return DocumentInfo(
        document_id=fm.get("slug") or path.stem,
        title=fm.get("title") or path.stem,
        file_path=str(path),
        created_at=fm.get("created_at") or "",
        updated_at=fm.get("updated_at") or "",
        char_count=len(body),
    )


async def read_document(project: Project, document_id: str) -> tuple[dict, str]:
    path = project_documents_dir(project) / f"{document_id}.md"
    if not path.exists():
        raise FileNotFoundError(f"document '{document_id}' not found")
    text = path.read_text(encoding="utf-8")
    return _parse_frontmatter(text)


async def write_document(
    project: Project,
    title: str,
    content_markdown: str,
    document_id: str | None = None,
) -> DocumentInfo:
    slug = slugify(document_id) if document_id else slugify(title)
    directory = project_documents_dir(project)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{slug}.md"

    now = _now_iso()
    created_at = now
    if path.exists():
        existing_text = path.read_text(encoding="utf-8")
        fm, _ = _parse_frontmatter(existing_text)
        created_at = fm.get("created_at") or now

    markdown = _render(title=title, slug=slug, created_at=created_at, updated_at=now, body=content_markdown)
    path.write_text(markdown, encoding="utf-8")
    fm, body = _parse_frontmatter(markdown)
    return _info_from_file(path, body, fm)


async def edit_document(
    project: Project,
    document_id: str,
    old_string: str,
    new_string: str,
    expected_occurrences: int = 1,
) -> DocumentInfo:
    path = project_documents_dir(project) / f"{document_id}.md"
    if not path.exists():
        raise FileNotFoundError(f"document '{document_id}' not found")

    text = path.read_text(encoding="utf-8")
    fm, body = _parse_frontmatter(text)

    actual = body.count(old_string)
    if actual != expected_occurrences:
        raise ValueError(
            f"old_string appeared {actual} time(s) in document body, "
            f"expected {expected_occurrences}. "
            f"Use ReadDocument to see the current content, then retry with exact text."
        )

    new_body = body.replace(old_string, new_string)
    now = _now_iso()
    markdown = _render(
        title=fm.get("title") or document_id,
        slug=fm.get("slug") or document_id,
        created_at=fm.get("created_at") or now,
        updated_at=now,
        body=new_body,
    )
    path.write_text(markdown, encoding="utf-8")
    fm2, body2 = _parse_frontmatter(markdown)
    return _info_from_file(path, body2, fm2)


async def list_documents(project: Project) -> list[DocumentInfo]:
    directory = project_documents_dir(project)
    if not directory.exists():
        return []
    results: list[DocumentInfo] = []
    for path in sorted(directory.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        fm, body = _parse_frontmatter(text)
        results.append(_info_from_file(path, body, fm))
    results.sort(key=lambda d: d.updated_at, reverse=True)
    return results
