"""Memory tools: SaveMemory and RecallMemory.

Memory is how the agent builds up context about the user's product, team,
stakeholders, and past decisions across sessions. Each saved memory is a
markdown file on disk PLUS an indexed row in `memory_records`.
"""
from __future__ import annotations

import logging

from sqlalchemy import select

from app.core.memory.store import (
    ALLOWED_TYPES,
    get_project,
    list_memories,
    read_memory_file,
    save_memory,
)
from app.core.tools import Tool, get_context, register
from app.models import MemoryRecord

logger = logging.getLogger(__name__)

_RECALL_CONTENT_LIMIT = 6  # include full body for up to N matches
_RECALL_BODY_CHAR_CAP = 3000  # truncate each body to this many chars

_TYPES_HELP = (
    "stakeholder (people — role, preferences, veto power), "
    "decision (a choice made, with rationale, date, decider), "
    "product (strategy, goals, roadmap state), "
    "team (structure, velocity, process quirks), "
    "lessons (what we learned from a launch/incident), "
    "reference (a pointer to where info lives — dashboard URL, doc, channel)"
)


async def _save_memory(input_data: dict) -> str:
    mem_type = (input_data.get("type") or "").strip().lower()
    title = (input_data.get("title") or "").strip()
    summary = (input_data.get("summary") or "").strip() or None
    content = (input_data.get("content") or "").strip()
    raw_tags = input_data.get("tags") or []
    if isinstance(raw_tags, str):
        raw_tags = [t.strip() for t in raw_tags.split(",") if t.strip()]
    tags = [str(t).strip() for t in raw_tags if str(t).strip()]

    if mem_type not in ALLOWED_TYPES:
        return (
            f"Error: 'type' must be one of {sorted(ALLOWED_TYPES)}. "
            f"Types: {_TYPES_HELP}"
        )
    if not title:
        return "Error: 'title' is required."
    if not content:
        return "Error: 'content' is required — the actual memory body to save."

    ctx = get_context()
    project = await get_project(ctx.db, ctx.project_id)
    record = await save_memory(
        db=ctx.db,
        project=project,
        mem_type=mem_type,
        title=title,
        content=content,
        summary=summary,
        tags=tags,
    )
    return (
        f"Saved {mem_type} memory '{title}' "
        f"(slug: {record.slug}, file: {record.file_path})."
    )


async def _recall_memory(input_data: dict) -> str:
    mem_type_raw = (input_data.get("type") or "").strip().lower()
    mem_type = mem_type_raw if mem_type_raw in ALLOWED_TYPES else None
    query = (input_data.get("query") or "").strip().lower()

    ctx = get_context()
    project = await get_project(ctx.db, ctx.project_id)
    records = await list_memories(db=ctx.db, project=project, mem_type=mem_type)

    if query:
        def match(r):
            hay = f"{r.title}\n{r.summary or ''}\n{' '.join(r.tags or [])}".lower()
            return query in hay
        records = [r for r in records if match(r)]

    if not records:
        scope = f" of type '{mem_type_raw}'" if mem_type_raw else ""
        q_part = f" matching '{query}'" if query else ""
        return f"No memories found{scope}{q_part}."

    lines = [f"Found {len(records)} memor{'y' if len(records) == 1 else 'ies'}:", ""]

    # Include full content for the first N (most recent). Beyond that, just
    # list the metadata so the model knows more exists and can request them.
    for i, r in enumerate(records):
        header = f"### [{r.type}] {r.title}"
        lines.append(header)
        if r.summary:
            lines.append(f"_Summary:_ {r.summary}")
        if r.tags:
            lines.append(f"_Tags:_ {', '.join(r.tags)}")
        lines.append(f"_Updated:_ {r.updated_at.isoformat() if r.updated_at else 'unknown'}")

        if i < _RECALL_CONTENT_LIMIT:
            _, body = read_memory_file(r)
            body = body.strip()
            if len(body) > _RECALL_BODY_CHAR_CAP:
                body = body[:_RECALL_BODY_CHAR_CAP].rstrip() + "\n\n…[truncated]"
            if body:
                lines.append("")
                lines.append(body)
        else:
            lines.append("_(body omitted — call RecallMemory again with a more specific query to see this one)_")

        lines.append("")
        lines.append("---")
        lines.append("")

    return "\n".join(lines).strip()


SaveMemory = register(
    Tool(
        name="SaveMemory",
        description=(
            "Save a lasting fact about the user's product, team, stakeholders, "
            "or decisions so it persists across sessions. Use this whenever you "
            "learn something the user will want you to know next time — a "
            "stakeholder's preferences, a product decision with its rationale, "
            "a key metric target, a team process quirk, or a reference to "
            f"where info lives. Types: {_TYPES_HELP}. "
            "Do NOT save ephemeral chat state or things you can derive from "
            "the conversation."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "type": {
                    "type": "string",
                    "enum": sorted(ALLOWED_TYPES),
                    "description": "Memory category. Pick the one that best fits.",
                },
                "title": {
                    "type": "string",
                    "description": "Short, specific name. E.g., 'Sarah (VP Engineering)' or 'Q2 2026 retention goal'.",
                },
                "summary": {
                    "type": "string",
                    "description": "One-line summary shown in the memory index. Keep it under ~120 chars.",
                },
                "content": {
                    "type": "string",
                    "description": "The full memory body in markdown. Structure with headings if useful.",
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional tags for later filtering (e.g., 'engineering', 'exec', 'q2').",
                },
            },
            "required": ["type", "title", "content"],
            "additionalProperties": False,
        },
        handler=_save_memory,
        is_read_only=False,
        is_externally_visible=False,
        category="memory",
    )
)


async def _search_memories(input_data: dict) -> str:
    query = (input_data.get("query") or "").strip()
    if not query:
        return "Error: 'query' is required."
    limit = int(input_data.get("limit", 10))
    limit = max(1, min(limit, 25))

    ctx = get_context()
    stmt = (
        select(MemoryRecord)
        .where(
            MemoryRecord.project_id == ctx.project_id,
            MemoryRecord.search_text.ilike(f"%{query}%"),
        )
        .order_by(MemoryRecord.updated_at.desc())
        .limit(limit)
    )
    records = list((await ctx.db.scalars(stmt)).all())
    if not records:
        return f"No memories matched '{query}'."

    lines = [f"Full-text matches for '{query}' ({len(records)} hit{'s' if len(records) != 1 else ''}):", ""]
    q_lower = query.lower()
    for r in records:
        lines.append(f"### [{r.type}] {r.title}")
        if r.summary:
            lines.append(f"_Summary:_ {r.summary}")
        snippet = _snippet_around(r.search_text or "", q_lower, pad=80)
        if snippet:
            lines.append(f"_Match context:_ …{snippet}…")
        lines.append("")
    lines.append("Call RecallMemory with {type, query} to load full body for any of these.")
    return "\n".join(lines)


def _snippet_around(text: str, needle: str, pad: int = 80) -> str:
    if not text:
        return ""
    lower = text.lower()
    idx = lower.find(needle)
    if idx < 0:
        return text[:pad]
    start = max(0, idx - pad)
    end = min(len(text), idx + len(needle) + pad)
    return text[start:end].replace("\n", " ")


SearchMemories = register(
    Tool(
        name="SearchMemories",
        description=(
            "Full-text search across all saved memories (case-insensitive "
            "substring match on title, summary, tags, and body). Faster "
            "than RecallMemory when you want to find any memory that "
            "mentions a specific word or phrase. Returns matching memory "
            "titles with a short snippet of the match; follow up with "
            "RecallMemory to load full content."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Case-insensitive substring to search for.",
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 25,
                    "description": "Max results (default 10).",
                },
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        handler=_search_memories,
        is_read_only=True,
        is_externally_visible=False,
        category="memory",
    )
)


RecallMemory = register(
    Tool(
        name="RecallMemory",
        description=(
            "Look up saved memories for this project. Optionally filter by type "
            "('stakeholder', 'decision', 'product', 'team', 'lessons', 'reference') "
            "and/or a free-text query (matched against title/summary/tags). "
            "Call this early in any conversation where the user references a "
            "person, a past decision, or a goal — memory lets you answer without "
            "guessing. Returns full body content for the top 6 matches."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "type": {
                    "type": "string",
                    "enum": sorted(ALLOWED_TYPES),
                    "description": "Optional: restrict to one memory type.",
                },
                "query": {
                    "type": "string",
                    "description": "Optional: free-text filter on title/summary/tags (case-insensitive substring).",
                },
            },
            "additionalProperties": False,
        },
        handler=_recall_memory,
        is_read_only=True,
        is_externally_visible=False,
        category="memory",
    )
)
