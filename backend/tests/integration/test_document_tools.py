"""Document tools round trip (ports scripts/try_documents.py).

Drives the registered ReadDocument/WriteDocument/EditDocument/ListDocuments
tools through execute_tool with a real ToolContext against the local
filesystem backend (tmp_path), plus the AwaitReview argument contract.
"""
from __future__ import annotations

import pytest

from app.config import settings
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
    """Documents derive their root from memory_root's parent — point both at
    a throwaway dir."""
    monkeypatch.setattr(settings, "memory_root", str(tmp_path / "memory"))


@pytest.fixture
def tool_context(db, seeded):
    token = set_context(
        ToolContext(
            db=db,
            session_id=seeded["user"].id,  # unused by document tools
            project_id=seeded["project"].id,
            user_id=seeded["user"].id,
        )
    )
    yield
    reset_context(token)


_PRD_BODY = (
    "# Test PRD\n\n"
    "## Problem\nUsers have no way to test the doc tools.\n\n"
    "## Scope\nOne round-trip smoke test.\n"
)


async def test_document_write_read_edit_list_round_trip(db, seeded, tool_context):
    # Empty store to start.
    out = await execute_tool("ListDocuments", {})
    assert "No documents" in out

    # Write.
    out = await execute_tool(
        "WriteDocument",
        {"title": "Test PRD", "content_markdown": _PRD_BODY, "document_id": "first-prd"},
    )
    assert not out.startswith("Error")
    assert "first-prd" in out

    # List now shows it.
    out = await execute_tool("ListDocuments", {})
    assert "Test PRD" in out and "first-prd" in out

    # Read returns the body.
    out = await execute_tool("ReadDocument", {"document_id": "first-prd"})
    assert "## Problem" in out
    assert "One round-trip smoke test." in out

    # Edit lands.
    out = await execute_tool(
        "EditDocument",
        {
            "document_id": "first-prd",
            "old_string": "## Scope\nOne round-trip smoke test.",
            "new_string": (
                "## Scope\nOne round-trip smoke test.\n\n"
                "## Open Questions\n- Did the edit land?"
            ),
        },
    )
    assert not out.startswith("Error")
    out = await execute_tool("ReadDocument", {"document_id": "first-prd"})
    assert "## Open Questions" in out

    # Edit with a non-matching old_string is refused.
    out = await execute_tool(
        "EditDocument",
        {"document_id": "first-prd", "old_string": "nope-not-here", "new_string": "x"},
    )
    assert out.startswith("Error")


async def test_read_unknown_document_errors(db, seeded, tool_context):
    out = await execute_tool("ReadDocument", {"document_id": "ghost"})
    assert out.startswith("Error")
    assert "ListDocuments" in out  # actionable hint for the model


async def test_write_document_requires_title_and_body(db, seeded, tool_context):
    assert (await execute_tool("WriteDocument", {"content_markdown": "x"})).startswith("Error")
    assert (await execute_tool("WriteDocument", {"title": "t"})).startswith("Error")


async def test_await_review_argument_contract(db, seeded, tool_context):
    # Valid call → non-error sentinel echo the engine intercepts.
    out = await execute_tool(
        "AwaitReview",
        {
            "deliverable_kind": "prd",
            "document_id": "first-prd",
            "summary_for_user": "Drafted the smoke-test PRD.",
        },
    )
    assert not out.startswith("Error")
    assert "Drafted the smoke-test PRD." in out

    # Missing required args → error string.
    assert (await execute_tool("AwaitReview", {})).startswith("Error")
    assert (
        await execute_tool("AwaitReview", {"deliverable_kind": "prd"})
    ).startswith("Error")
