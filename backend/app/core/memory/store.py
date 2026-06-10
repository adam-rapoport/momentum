"""Filesystem-backed memory store.

Design: markdown files on disk are the source of truth. The `memory_records`
DB table is an index for fast listing/filtering from the API. Every save
writes the file AND upserts the row, then regenerates MEMORY.md.

Layout:
    <memory_root>/<project_slug>/<type>_<slug>.md   — one memory
    <memory_root>/<project_slug>/MEMORY.md           — auto-generated index
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import MemoryRecord, Project

ALLOWED_TYPES = {"stakeholder", "decision", "product", "team", "lessons", "reference"}

# YAML parser/writer: we only support the minimal subset we emit ourselves
# (flat key/value strings, plus a tags list). Keeps us dependency-free and
# avoids PyYAML — external memory files don't exist yet, so we control
# the format 100%.
_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n?", re.DOTALL)


def get_memory_root() -> Path:
    """Resolve the memory root directory. Honours the MEMORY_ROOT env var if set;
    otherwise defaults to `<pmomentum>/data/memory` (sibling of the backend dir).
    """
    if settings.memory_root:
        p = Path(settings.memory_root).expanduser()
        if p.is_absolute():
            return p
    # Fall back to a path computed from this file's location so it works
    # regardless of the caller's cwd.
    backend_dir = Path(__file__).resolve().parents[3]  # backend/
    return (backend_dir.parent / "data" / "memory").resolve()


def slugify(value: str, max_length: int = 60) -> str:
    """Turn a title into a filesystem-safe slug."""
    value = value.strip().lower()
    value = re.sub(r"[^\w\s-]", "", value)
    value = re.sub(r"[\s_-]+", "-", value).strip("-")
    return value[:max_length] or "untitled"


def project_memory_dir(project: Project) -> Path:
    root = get_memory_root()
    return root / (project.slug or "default")


def _render_frontmatter(data: dict) -> str:
    lines = ["---"]
    for k, v in data.items():
        if isinstance(v, list):
            if not v:
                lines.append(f"{k}: []")
            else:
                rendered = ", ".join(f'"{str(item)}"' for item in v)
                lines.append(f"{k}: [{rendered}]")
        elif v is None:
            continue
        else:
            s = str(v).replace("\n", " ")
            lines.append(f"{k}: {s}")
    lines.append("---")
    return "\n".join(lines)


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Lightweight frontmatter parser — enough to read back what we wrote."""
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    fm_block = m.group(1)
    body = text[m.end():]
    data: dict = {}
    for raw_line in fm_block.splitlines():
        if not raw_line.strip() or ":" not in raw_line:
            continue
        k, _, v = raw_line.partition(":")
        k = k.strip()
        v = v.strip()
        if v.startswith("[") and v.endswith("]"):
            inner = v[1:-1].strip()
            if not inner:
                data[k] = []
            else:
                items = [
                    seg.strip().strip('"').strip("'") for seg in inner.split(",") if seg.strip()
                ]
                data[k] = items
        else:
            data[k] = v
    return data, body


def render_markdown(
    *,
    title: str,
    mem_type: str,
    slug: str,
    summary: str | None,
    tags: list[str],
    content: str,
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
) -> str:
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    frontmatter = _render_frontmatter(
        {
            "title": title,
            "type": mem_type,
            "slug": slug,
            "summary": summary or "",
            "tags": tags or [],
            "created_at": (created_at.isoformat() if created_at else now),
            "updated_at": (updated_at.isoformat() if updated_at else now),
        }
    )
    body = content.strip() + "\n" if content else ""
    return f"{frontmatter}\n\n{body}"


async def _regenerate_index(db: AsyncSession, project: Project) -> None:
    """Rewrite MEMORY.md to match the current DB state."""
    stmt = (
        select(MemoryRecord)
        .where(MemoryRecord.project_id == project.id)
        .order_by(MemoryRecord.type, MemoryRecord.title)
    )
    records = (await db.scalars(stmt)).all()

    lines = ["# Memory Index", ""]
    if not records:
        lines.append("_No memories yet._")
    else:
        by_type: dict[str, list[MemoryRecord]] = {}
        for r in records:
            by_type.setdefault(r.type, []).append(r)
        for mem_type in sorted(by_type):
            lines.append(f"## {mem_type.title()}")
            lines.append("")
            for r in by_type[mem_type]:
                filename = Path(r.file_path).name
                suffix = f" — {r.summary}" if r.summary else ""
                lines.append(f"- [{r.title}]({filename}){suffix}")
            lines.append("")

    index_path = project_memory_dir(project) / "MEMORY.md"
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text("\n".join(lines), encoding="utf-8")


async def save_memory(
    *,
    db: AsyncSession,
    project: Project,
    mem_type: str,
    title: str,
    content: str,
    summary: str | None = None,
    tags: list[str] | None = None,
) -> MemoryRecord:
    if mem_type not in ALLOWED_TYPES:
        raise ValueError(
            f"invalid memory type '{mem_type}'. Allowed: {sorted(ALLOWED_TYPES)}"
        )
    tags = tags or []
    directory = project_memory_dir(project)
    directory.mkdir(parents=True, exist_ok=True)

    async def _record_for(s: str) -> MemoryRecord | None:
        return await db.scalar(
            select(MemoryRecord).where(
                MemoryRecord.project_id == project.id,
                MemoryRecord.type == mem_type,
                MemoryRecord.slug == s,
            )
        )

    # Same (type, slug, title) is an upsert — re-saving a memory updates it
    # in place. A DIFFERENT title that happens to slugify to the same slug
    # ("Q3 plan!" vs "Q3 plan?") must NOT silently overwrite someone else's
    # memory (finding A28): suffix -2, -3, … until we hit a free slug or this
    # title's own previously-suffixed slot.
    slug = slugify(title)
    existing = await _record_for(slug)
    if existing is not None and existing.title != title:
        base, n = slug, 2
        while True:
            slug = f"{base}-{n}"
            existing = await _record_for(slug)
            if existing is None or existing.title == title:
                break
            n += 1

    filename = f"{mem_type}_{slug}.md"
    file_path = directory / filename

    if existing is not None:
        existing.title = title
        existing.summary = summary
        existing.tags = list(tags)
        existing.file_path = str(file_path)
        existing.search_text = f"{title}\n{summary or ''}\n{content}"
        record = existing
        created_at = existing.created_at
    else:
        record = MemoryRecord(
            id=uuid4(),
            project_id=project.id,
            type=mem_type,
            title=title,
            slug=slug,
            summary=summary,
            tags=list(tags),
            file_path=str(file_path),
            search_text=f"{title}\n{summary or ''}\n{content}",
        )
        db.add(record)
        created_at = None

    # Flush BEFORE touching the filesystem (finding A28): a constraint
    # violation used to surface only after the markdown file was already
    # written, leaving the file and the DB index permanently diverged.
    await db.flush()

    markdown = render_markdown(
        title=title,
        mem_type=mem_type,
        slug=slug,
        summary=summary,
        tags=list(tags),
        content=content,
        created_at=created_at,
    )
    file_path.write_text(markdown, encoding="utf-8")

    await _regenerate_index(db, project)
    return record


async def list_memories(
    *,
    db: AsyncSession,
    project: Project,
    mem_type: str | None = None,
) -> list[MemoryRecord]:
    stmt = select(MemoryRecord).where(MemoryRecord.project_id == project.id)
    if mem_type is not None:
        stmt = stmt.where(MemoryRecord.type == mem_type)
    stmt = stmt.order_by(MemoryRecord.type, MemoryRecord.updated_at.desc())
    return list((await db.scalars(stmt)).all())


def read_memory_file(record: MemoryRecord) -> tuple[dict, str]:
    """Return (frontmatter_dict, body_markdown) for a memory file."""
    path = Path(record.file_path)
    if not path.exists():
        return ({}, f"_(file missing: {record.file_path})_")
    text = path.read_text(encoding="utf-8")
    return _parse_frontmatter(text)


async def get_project(db: AsyncSession, project_id) -> Project:
    project = await db.scalar(select(Project).where(Project.id == project_id))
    if project is None:
        raise ValueError(f"project {project_id} not found")
    return project
