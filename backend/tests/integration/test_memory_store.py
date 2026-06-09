"""Memory store + memory tools tests (plan item 31; ports scripts/try_memory.py).

Covers the frontmatter render/parse round trip and slugify (pure), then
save_memory/list_memories/read_memory_file against the real DB with a
tmp_path memory root, and the SaveMemory/RecallMemory tools end-to-end via
execute_tool with a real ToolContext.
"""
from __future__ import annotations

import pytest

from app.config import settings
from app.core.memory.store import (
    _parse_frontmatter,
    project_memory_dir,
    read_memory_file,
    render_markdown,
    save_memory,
    list_memories,
    slugify,
)
from app.core.tools import (
    ToolContext,
    _load_builtin_tools,
    execute_tool,
    reset_context,
    set_context,
)

_load_builtin_tools()


@pytest.fixture(autouse=True)
def _tmp_memory_root(tmp_path, monkeypatch):
    """Write memory markdown to a throwaway dir, not the repo's data/memory."""
    monkeypatch.setattr(settings, "memory_root", str(tmp_path / "memory"))


@pytest.fixture
def tool_context(db, seeded):
    token = set_context(
        ToolContext(
            db=db,
            session_id=seeded["user"].id,  # unused by memory tools
            project_id=seeded["project"].id,
            user_id=seeded["user"].id,
        )
    )
    yield
    reset_context(token)


# ---------- slugify ----------


def test_slugify_basic_cases():
    assert slugify("Sarah (VP Engineering)") == "sarah-vp-engineering"
    assert slugify("  Q2 2026   retention_goal  ") == "q2-2026-retention-goal"
    assert slugify("!!!") == "untitled"
    assert slugify("") == "untitled"


def test_slugify_truncates_to_max_length():
    assert len(slugify("x " * 100)) <= 60


# ---------- frontmatter render/parse round trip ----------


def test_render_parse_round_trip():
    md = render_markdown(
        title="Sarah (VP Eng)",
        mem_type="stakeholder",
        slug="sarah-vp-eng",
        summary="Owns engineering",
        tags=["exec", "engineering"],
        content="## Role\nVP of Engineering.\n",
    )
    fm, body = _parse_frontmatter(md)
    assert fm["title"] == "Sarah (VP Eng)"
    assert fm["type"] == "stakeholder"
    assert fm["slug"] == "sarah-vp-eng"
    assert fm["summary"] == "Owns engineering"
    assert fm["tags"] == ["exec", "engineering"]
    assert fm["created_at"]  # stamped
    assert body.strip() == "## Role\nVP of Engineering."


def test_render_parse_empty_tags_and_summary():
    md = render_markdown(
        title="t", mem_type="decision", slug="t", summary=None, tags=[], content="c"
    )
    fm, body = _parse_frontmatter(md)
    assert fm["tags"] == []
    assert fm["summary"] == ""
    assert body.strip() == "c"


def test_parse_frontmatter_without_block_returns_whole_text():
    fm, body = _parse_frontmatter("just a plain document")
    assert fm == {}
    assert body == "just a plain document"


# ---------- save_memory / list_memories / read_memory_file ----------


async def test_save_memory_writes_file_row_and_index(db, seeded):
    project = seeded["project"]
    record = await save_memory(
        db=db,
        project=project,
        mem_type="stakeholder",
        title="Sarah (VP Engineering)",
        content="## Role\nVP of Engineering.",
        summary="Owns engineering",
        tags=["exec"],
    )
    await db.commit()

    # DB row
    assert record.slug == "sarah-vp-engineering"
    stored = await list_memories(db=db, project=project)
    assert [m.title for m in stored] == ["Sarah (VP Engineering)"]

    # Markdown file round-trips through read_memory_file.
    fm, body = read_memory_file(record)
    assert fm["title"] == "Sarah (VP Engineering)"
    assert "VP of Engineering" in body

    # MEMORY.md index regenerated with a link to the file.
    index = (project_memory_dir(project) / "MEMORY.md").read_text(encoding="utf-8")
    assert "## Stakeholder" in index
    assert "stakeholder_sarah-vp-engineering.md" in index


async def test_save_memory_same_slug_updates_in_place(db, seeded):
    project = seeded["project"]
    first = await save_memory(
        db=db, project=project, mem_type="decision",
        title="Q2 goal", content="old", summary="v1",
    )
    await db.commit()
    second = await save_memory(
        db=db, project=project, mem_type="decision",
        title="Q2 goal", content="new content", summary="v2",
    )
    await db.commit()

    assert second.id == first.id  # upsert, not a duplicate
    stored = await list_memories(db=db, project=project, mem_type="decision")
    assert len(stored) == 1
    assert stored[0].summary == "v2"
    _, body = read_memory_file(stored[0])
    assert "new content" in body


async def test_save_memory_rejects_invalid_type(db, seeded):
    with pytest.raises(ValueError):
        await save_memory(
            db=db, project=seeded["project"], mem_type="gossip",
            title="t", content="c",
        )


async def test_list_memories_filters_by_type(db, seeded):
    project = seeded["project"]
    await save_memory(db=db, project=project, mem_type="stakeholder", title="S", content="x")
    await save_memory(db=db, project=project, mem_type="decision", title="D", content="y")
    await db.commit()

    assert {m.type for m in await list_memories(db=db, project=project)} == {
        "stakeholder", "decision",
    }
    only = await list_memories(db=db, project=project, mem_type="decision")
    assert [m.title for m in only] == ["D"]


def test_read_memory_file_missing_file_is_graceful(tmp_path):
    from types import SimpleNamespace

    record = SimpleNamespace(file_path=str(tmp_path / "gone.md"))
    fm, body = read_memory_file(record)
    assert fm == {}
    assert "file missing" in body


# ---------- SaveMemory / RecallMemory tools (ported from try_memory) ----------


async def test_memory_tools_save_then_recall(db, seeded, tool_context):
    out = await execute_tool(
        "SaveMemory",
        {
            "type": "stakeholder",
            "title": "Sarah (VP Engineering)",
            "summary": "Prefers bullet-point weekly updates",
            "content": "## Role\nVP of Engineering at Acme.",
            "tags": ["engineering", "exec"],
        },
    )
    assert not out.startswith("Error")
    await db.commit()

    recall_all = await execute_tool("RecallMemory", {})
    assert "Sarah (VP Engineering)" in recall_all

    recall_typed = await execute_tool("RecallMemory", {"type": "stakeholder"})
    assert "Sarah (VP Engineering)" in recall_typed

    recall_query = await execute_tool("RecallMemory", {"query": "sarah"})
    assert "Sarah (VP Engineering)" in recall_query

    recall_miss = await execute_tool("RecallMemory", {"query": "zzz-no-match"})
    assert "Sarah" not in recall_miss
