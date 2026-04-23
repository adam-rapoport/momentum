"""Document tools: ReadDocument, WriteDocument, EditDocument, ListDocuments,
and the pause sentinel AwaitReview.

Chunk A ships these against the local-filesystem document store. Chunk D
will swap the storage adapter (Google Docs) behind the same tools without
changing any of the tool signatures or session_engine code.

AwaitReview is registered here because it's part of the deliverable flow
— it's how a skill signals it has produced its final output and is ready
for the user to approve/revise/restart. Chunk A's handler is a simple echo;
Chunk C wires the session engine to detect calls to this tool and switch
the session to `awaiting_review` status.
"""
from __future__ import annotations

import logging

from app.core.documents import router as docs_router
from app.core.integrations.google_docs import GoogleDocsError, GoogleDocsNotConnected
from app.core.integrations.google_oauth import OAuthFlowError
from app.core.memory.store import get_project
from app.core.tools import Tool, get_context, register

logger = logging.getLogger(__name__)

_READ_BODY_CHAR_CAP = 8000  # truncate long documents in tool output


async def _read_document(input_data: dict) -> str:
    document_id = (input_data.get("document_id") or "").strip()
    if not document_id:
        return "Error: 'document_id' is required. Call ListDocuments to see available document IDs."

    ctx = get_context()
    project = await get_project(ctx.db, ctx.project_id)
    try:
        fm, body, backend = await docs_router.read_document(
            ctx.db, ctx.user_id, project, document_id
        )
    except FileNotFoundError as e:
        return f"Error: {e}. Call ListDocuments to see available document IDs."
    except GoogleDocsNotConnected as e:
        return f"Error: {e}"
    except (GoogleDocsError, OAuthFlowError) as e:
        return f"Error: Google Docs is having trouble: {e}"

    title = fm.get("title") or document_id
    updated = fm.get("updated_at") or "unknown"
    truncated = ""
    if len(body) > _READ_BODY_CHAR_CAP:
        body = body[:_READ_BODY_CHAR_CAP].rstrip()
        truncated = "\n\n…[truncated]"

    location_line = ""
    if backend == "google_docs" and fm.get("url"):
        location_line = f"\n_Google Docs URL: {fm['url']}_"
    return (
        f"# {title}\n"
        f"_Document ID: `{document_id}` — Updated: {updated} — Backend: {backend}_"
        f"{location_line}\n\n"
        f"{body.strip()}{truncated}"
    )


async def _write_document(input_data: dict) -> str:
    title = (input_data.get("title") or "").strip()
    content_markdown = input_data.get("content_markdown") or ""
    document_id_raw = input_data.get("document_id")
    document_id = (document_id_raw or "").strip() or None

    if not title:
        return "Error: 'title' is required."
    if not content_markdown.strip():
        return "Error: 'content_markdown' is required (the document body)."

    ctx = get_context()
    project = await get_project(ctx.db, ctx.project_id)
    try:
        info = await docs_router.write_document(
            db=ctx.db,
            user_id=ctx.user_id,
            project=project,
            title=title,
            content_markdown=content_markdown,
            document_id=document_id,
        )
    except (GoogleDocsError, OAuthFlowError) as e:
        return f"Error: Google Docs is having trouble: {e}"

    location = info.get("url") or info.get("file_path")
    backend = info.get("backend", "local")
    return (
        f"Wrote document '{info['title']}' (id: `{info['document_id']}`, "
        f"{info['char_count']} chars, backend: {backend}).\n"
        f"{'URL' if backend == 'google_docs' else 'File'}: {location}\n"
        "Use ReadDocument with this document_id to view or EditDocument to change it."
    )


async def _edit_document(input_data: dict) -> str:
    document_id = (input_data.get("document_id") or "").strip()
    old_string = input_data.get("old_string") or ""
    new_string = input_data.get("new_string") or ""
    expected = input_data.get("expected_occurrences", 1)
    try:
        expected = int(expected)
    except (TypeError, ValueError):
        return "Error: 'expected_occurrences' must be an integer."
    if expected < 1:
        return "Error: 'expected_occurrences' must be at least 1."

    if not document_id:
        return "Error: 'document_id' is required."
    if not old_string:
        return "Error: 'old_string' is required (the exact text to replace)."
    if old_string == new_string:
        return "Error: 'new_string' is identical to 'old_string' — nothing to change."

    ctx = get_context()
    project = await get_project(ctx.db, ctx.project_id)
    try:
        info = await docs_router.edit_document(
            db=ctx.db,
            user_id=ctx.user_id,
            project=project,
            document_id=document_id,
            old_string=old_string,
            new_string=new_string,
            expected_occurrences=expected,
        )
    except FileNotFoundError as e:
        return f"Error: {e}. Call ListDocuments to see available document IDs."
    except ValueError as e:
        return f"Error: {e}"
    except (GoogleDocsError, OAuthFlowError) as e:
        return f"Error: Google Docs is having trouble: {e}"

    backend = info.get("backend", "local")
    return (
        f"Edited '{info['title']}' (id: `{info['document_id']}`, backend: {backend}). "
        f"Now {info['char_count']} chars. Call ReadDocument to see the updated content."
    )


async def _list_documents(input_data: dict) -> str:  # noqa: ARG001 — no args
    ctx = get_context()
    project = await get_project(ctx.db, ctx.project_id)
    try:
        docs = await docs_router.list_documents(ctx.db, ctx.user_id, project)
    except (GoogleDocsError, OAuthFlowError) as e:
        return f"Error: Google Docs is having trouble: {e}"
    if not docs:
        return "No documents in this project yet. Use WriteDocument to create one."
    lines = [f"{len(docs)} document(s) in project '{project.slug}':", ""]
    for d in docs:
        backend = d.get("backend", "local")
        if backend == "google_docs" and d.get("url"):
            loc = f" ([open]({d['url']}))"
        else:
            loc = ""
        lines.append(
            f"- **{d['title']}** — id: `{d['document_id']}`, "
            f"backend: {backend}, {d['char_count']} chars{loc}"
        )
    return "\n".join(lines)


async def _await_review(input_data: dict) -> str:
    """Sentinel: signals that a skill has produced its final deliverable.

    Chunk A: this handler is a simple pass-through — it just confirms the
    call and returns a deterministic string. Chunk C wires the session
    engine to intercept invocations and transition the session into
    `awaiting_review` status, blocking further model turns until the user
    responds.
    """
    deliverable_kind = (input_data.get("deliverable_kind") or "").strip()
    document_id = (input_data.get("document_id") or "").strip() or None
    summary = (input_data.get("summary_for_user") or "").strip()

    if not deliverable_kind:
        return "Error: 'deliverable_kind' is required (e.g. 'prd', 'stakeholder_update', 'meeting_agenda')."
    if not summary:
        return "Error: 'summary_for_user' is required — a one-line description of what you just produced."

    doc_part = f" (document: `{document_id}`)" if document_id else ""
    return (
        f"[AwaitReview — {deliverable_kind}{doc_part}]\n"
        f"{summary}\n\n"
        "(Pause-and-review wiring lands in Chunk C. For now, the agent should stop here; "
        "the user will reply to confirm, revise, or restart.)"
    )


ReadDocument = register(
    Tool(
        name="ReadDocument",
        description=(
            "Read a document you previously created for this project. "
            "Returns the full markdown body. Use this before EditDocument "
            "to see current content, or whenever the user asks about a "
            "document they've saved. Call ListDocuments first if you don't "
            "remember the exact document_id."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "document_id": {
                    "type": "string",
                    "description": "The document's slug (e.g. 'q2-roadmap-prd'). Get from ListDocuments or WriteDocument output.",
                },
            },
            "required": ["document_id"],
            "additionalProperties": False,
        },
        handler=_read_document,
        is_read_only=True,
        is_externally_visible=False,
        category="documents",
    )
)


WriteDocument = register(
    Tool(
        name="WriteDocument",
        description=(
            "Create or overwrite a markdown document in this project's local "
            "document store. Use for PRDs, meeting agendas, competitive briefs, "
            "or any PM deliverable the user wants as a persistent artifact. "
            "The document persists across sessions and can be re-opened with "
            "ReadDocument. For small tweaks to an existing document, prefer "
            "EditDocument over rewriting the whole thing."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Human-readable title. Becomes part of the filename (slugified).",
                },
                "content_markdown": {
                    "type": "string",
                    "description": "Full document body in markdown. Use headings, bullets, tables.",
                },
                "document_id": {
                    "type": "string",
                    "description": "Optional explicit slug. If omitted, derived from title.",
                },
            },
            "required": ["title", "content_markdown"],
            "additionalProperties": False,
        },
        handler=_write_document,
        is_read_only=False,
        is_externally_visible=True,
        category="documents",
    )
)


EditDocument = register(
    Tool(
        name="EditDocument",
        description=(
            "Make a precise edit to an existing document by replacing an "
            "exact string. Use for small changes — adding a section, fixing "
            "a typo, updating a date. For large rewrites, call WriteDocument "
            "to overwrite the whole document instead. The replacement must "
            "match 'expected_occurrences' times exactly — if it doesn't, the "
            "edit is refused. Call ReadDocument first if unsure what exactly "
            "is in the file."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "document_id": {
                    "type": "string",
                    "description": "The document's slug.",
                },
                "old_string": {
                    "type": "string",
                    "description": "Exact text to find and replace. Must match the current document content byte-for-byte.",
                },
                "new_string": {
                    "type": "string",
                    "description": "Replacement text. Can be empty to delete.",
                },
                "expected_occurrences": {
                    "type": "integer",
                    "minimum": 1,
                    "description": "How many times 'old_string' should appear in the body. Default 1.",
                },
            },
            "required": ["document_id", "old_string", "new_string"],
            "additionalProperties": False,
        },
        handler=_edit_document,
        is_read_only=False,
        is_externally_visible=True,
        category="documents",
    )
)


ListDocuments = register(
    Tool(
        name="ListDocuments",
        description=(
            "List every document saved in this project, most-recently-updated "
            "first. Returns title, document_id, and char count for each. Cheap "
            "— call it whenever you need to find an existing document or show "
            "the user what's available."
        ),
        input_schema={
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
        handler=_list_documents,
        is_read_only=True,
        is_externally_visible=False,
        category="documents",
    )
)


AwaitReview = register(
    Tool(
        name="AwaitReview",
        description=(
            "Signal that you've completed a skill's final deliverable and are "
            "stopping so the user can approve, request revisions, or restart. "
            "ONLY call this at the end of a skill workflow (PRD drafted, "
            "stakeholder update written, meeting agenda ready), never during "
            "casual chat or document edits. After calling this, do NOT produce "
            "any more text in the same turn — the system takes over and pauses "
            "the session until the user responds."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "deliverable_kind": {
                    "type": "string",
                    "description": "What you just produced: 'prd', 'stakeholder_update', 'meeting_agenda', or another short label.",
                },
                "document_id": {
                    "type": "string",
                    "description": "Slug of the document the user should review (if any).",
                },
                "summary_for_user": {
                    "type": "string",
                    "description": "One line describing what you produced and where to find it.",
                },
            },
            "required": ["deliverable_kind", "summary_for_user"],
            "additionalProperties": False,
        },
        handler=_await_review,
        is_read_only=True,
        is_externally_visible=True,
        category="workflow",
    )
)
