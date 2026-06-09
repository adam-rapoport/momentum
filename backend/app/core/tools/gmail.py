"""Gmail tools: ListEmails, ReadEmail, DraftEmail, SendEmail.

Chunk B ships all four tool *signatures* so the model has a stable API.
Chunk E will swap `SendEmail`'s handler to stage a pending-action that
pauses the session until the user approves in the UI. Until then,
`SendEmail` creates a draft and tells the user to review in Gmail —
nothing ever leaves the outbox without a human click.
"""
from __future__ import annotations

import logging
from typing import Any

from app.core.integrations.gmail import (
    GmailError,
    GmailNotConnected,
    create_draft,
    list_recent_messages,
    read_message,
)
from app.core.integrations.google_oauth import OAuthFlowError
from app.core.pending_actions import stage_action
from app.core.tools import Tool, get_context, register

logger = logging.getLogger(__name__)


def _normalize_recipient_list(value: Any, field: str) -> list[str] | str:
    """Accept either a list of strings or a single comma-separated string.
    Returns the cleaned list, or an error string the caller should return."""
    if value is None:
        return []
    if isinstance(value, str):
        parts = [p.strip() for p in value.split(",") if p.strip()]
        return parts
    if isinstance(value, list):
        cleaned = [str(p).strip() for p in value if str(p).strip()]
        return cleaned
    return f"Error: '{field}' must be a list of email addresses."


def _format_handling_error(e: Exception, action: str) -> str:
    if isinstance(e, GmailNotConnected):
        return f"Error: {e}"
    if isinstance(e, OAuthFlowError):
        return f"Error: Google authentication expired — reconnect in Settings. ({e})"
    if isinstance(e, GmailError):
        return f"Error: Gmail {action} failed: {e}"
    if isinstance(e, FileNotFoundError):
        return f"Error: {e}"
    return f"Error: Gmail {action} failed: {e}"


async def _list_emails(input_data: dict) -> str:
    query = (input_data.get("query") or "").strip() or None
    label = (input_data.get("label") or "").strip() or None
    max_results_raw = input_data.get("max_results", 10)
    try:
        max_results = int(max_results_raw)
    except (TypeError, ValueError):
        return "Error: 'max_results' must be an integer (1-25)."

    ctx = get_context()
    try:
        messages = await list_recent_messages(
            ctx.db,
            ctx.user_id,
            query=query,
            max_results=max_results,
            label=label,
        )
    except (GmailNotConnected, GmailError, OAuthFlowError) as e:
        return _format_handling_error(e, "list")

    if not messages:
        filter_desc = []
        if query:
            filter_desc.append(f"query='{query}'")
        if label:
            filter_desc.append(f"label='{label}'")
        hint = f" ({', '.join(filter_desc)})" if filter_desc else ""
        return f"No messages found{hint}."

    lines = [f"{len(messages)} message(s):", ""]
    for m in messages:
        unread = "● " if m["unread"] else "  "
        snippet = (m["snippet"] or "").strip().replace("\n", " ")
        if len(snippet) > 120:
            snippet = snippet[:117] + "..."
        lines.append(
            f"{unread}**{m['subject']}** — from {m['from']}\n"
            f"   id: `{m['id']}`  ·  {m['date']}\n"
            f"   {snippet}"
        )
    lines.append("")
    lines.append("Call ReadEmail with an id to see the full body.")
    return "\n".join(lines)


async def _read_email(input_data: dict) -> str:
    message_id = (input_data.get("message_id") or "").strip()
    if not message_id:
        return "Error: 'message_id' is required. Call ListEmails first."

    ctx = get_context()
    try:
        msg = await read_message(ctx.db, ctx.user_id, message_id)
    except (GmailNotConnected, GmailError, OAuthFlowError, FileNotFoundError) as e:
        return _format_handling_error(e, "read")

    truncated_note = "\n\n…[truncated]" if msg["truncated"] else ""
    cc_line = f"Cc: {msg['cc']}\n" if msg.get("cc") else ""
    return (
        f"# {msg['subject']}\n"
        f"From: {msg['from']}\n"
        f"To: {msg['to']}\n"
        f"{cc_line}"
        f"Date: {msg['date']}\n"
        f"Gmail URL: {msg['url']}\n"
        f"_message_id: `{msg['id']}` · thread: `{msg['thread_id']}`_\n\n"
        f"{msg['body_text']}{truncated_note}"
    )


async def _draft_email(input_data: dict) -> str:
    to_parsed = _normalize_recipient_list(input_data.get("to"), "to")
    if isinstance(to_parsed, str):
        return to_parsed
    if not to_parsed:
        return "Error: 'to' is required — at least one recipient email address."

    cc_parsed = _normalize_recipient_list(input_data.get("cc"), "cc")
    if isinstance(cc_parsed, str):
        return cc_parsed

    subject = (input_data.get("subject") or "").strip()
    if not subject:
        return "Error: 'subject' is required."

    body = input_data.get("body_markdown") or ""
    if not body.strip():
        return "Error: 'body_markdown' is required — the email body."

    reply_to = (input_data.get("reply_to_message_id") or "").strip() or None

    ctx = get_context()
    try:
        draft = await create_draft(
            ctx.db,
            ctx.user_id,
            to=to_parsed,
            cc=cc_parsed,
            subject=subject,
            body_markdown=body,
            reply_to_message_id=reply_to,
        )
    except (GmailNotConnected, GmailError, OAuthFlowError) as e:
        return _format_handling_error(e, "draft")

    recipients = ", ".join(draft["to"])
    cc_line = f" (cc: {', '.join(draft['cc'])})" if draft["cc"] else ""
    return (
        f"Draft created: '{draft['subject']}' to {recipients}{cc_line}.\n"
        f"Review and send from Gmail: {draft['url']}\n"
        f"_draft_id: `{draft['draft_id']}`_"
    )


async def _send_email(input_data: dict) -> str:
    """Stage the send for user approval. Chunk E: this stores the
    payload as `pending_action` on the session, the engine pauses, and
    the user clicks Approve in the UI before anything actually leaves
    the outbox."""
    to_parsed = _normalize_recipient_list(input_data.get("to"), "to")
    if isinstance(to_parsed, str):
        return to_parsed
    if not to_parsed:
        return "Error: 'to' is required."

    cc_parsed = _normalize_recipient_list(input_data.get("cc"), "cc")
    if isinstance(cc_parsed, str):
        return cc_parsed

    subject = (input_data.get("subject") or "").strip()
    if not subject:
        return "Error: 'subject' is required."

    body = input_data.get("body_markdown") or ""
    if not body.strip():
        return "Error: 'body_markdown' is required."

    reply_to = (input_data.get("reply_to_message_id") or "").strip() or None

    body_snippet = body if len(body) <= 400 else body[:400].rstrip() + "…"

    ctx = get_context()
    try:
        await stage_action(
            ctx.db,
            ctx.session_id,
            kind="send_email",
            tool_name="SendEmail",
            params={
                "to": to_parsed,
                "cc": cc_parsed,
                "subject": subject,
                "body_markdown": body,
                "reply_to_message_id": reply_to,
            },
            preview={
                "to": to_parsed,
                "cc": cc_parsed,
                "subject": subject,
                "body_snippet": body_snippet,
            },
            call_id=ctx.current_call_id,
        )
    except ValueError as e:
        return f"Error: {e}"

    recipients = ", ".join(to_parsed)
    return (
        f"[Pending approval] Email staged: '{subject}' to {recipients}. "
        f"SESSION PAUSING NOW. Stop your turn here — emit no more text and "
        f"call no more tools. The user will click Approve, Make changes, or "
        f"Cancel in the UI; the next turn will start with a system note "
        f"telling you the final outcome. Calling SendEmail again in this "
        f"turn would create a duplicate."
    )


ListEmails = register(
    Tool(
        name="ListEmails",
        description=(
            "List recent Gmail messages. Returns subject, sender, date, a short "
            "snippet, and the message_id for each. Use 'query' for Gmail search "
            "syntax (e.g. 'from:alice is:unread', 'newer_than:3d', "
            "'subject:launch'). Cheap — call whenever the user asks about their "
            "inbox. Default returns the 10 most recent across all mail; cap 25."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Gmail search operators. Examples: 'from:@company.com', 'is:unread newer_than:7d', 'subject:roadmap'.",
                },
                "max_results": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 25,
                    "description": "Max messages to return. Default 10, max 25.",
                },
                "label": {
                    "type": "string",
                    "description": "Optional label ID (e.g. 'INBOX', 'STARRED', 'SENT'). Omit for all mail.",
                },
            },
            "additionalProperties": False,
        },
        handler=_list_emails,
        is_read_only=True,
        is_externally_visible=False,
        category="gmail",
    )
)


ReadEmail = register(
    Tool(
        name="ReadEmail",
        description=(
            "Read the full body of a Gmail message by its message_id. Call "
            "ListEmails first to get the ID. Returns headers plus a "
            "plain-text body (HTML mail gets stripped to readable text). "
            "Long bodies are truncated at 8000 chars."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "message_id": {
                    "type": "string",
                    "description": "Gmail message_id from ListEmails.",
                },
            },
            "required": ["message_id"],
            "additionalProperties": False,
        },
        handler=_read_email,
        is_read_only=True,
        is_externally_visible=False,
        category="gmail",
    )
)


DraftEmail = register(
    Tool(
        name="DraftEmail",
        description=(
            "Create a Gmail draft — NOT sent, just saved to the user's drafts "
            "folder so they can review and send from Gmail's UI. Use this "
            "whenever the user asks to 'write' or 'draft' an email. Supply "
            "recipients as a list of addresses. If replying to an existing "
            "message, pass 'reply_to_message_id' so Gmail threads it and the "
            "subject auto-prefixes 'Re: '."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "to": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 1,
                    "description": "Recipient email addresses.",
                },
                "cc": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional CC recipients.",
                },
                "subject": {
                    "type": "string",
                    "description": "Email subject line. Auto-prefixed with 'Re: ' if reply_to_message_id is set.",
                },
                "body_markdown": {
                    "type": "string",
                    "description": "Email body. Plain text or lightweight markdown — markdown is sent as-is (most clients render it readably).",
                },
                "reply_to_message_id": {
                    "type": "string",
                    "description": "Optional: message_id of the email being replied to. Enables threading.",
                },
            },
            "required": ["to", "subject", "body_markdown"],
            "additionalProperties": False,
        },
        handler=_draft_email,
        is_read_only=False,
        is_externally_visible=False,
        category="gmail",
    )
)


SendEmail = register(
    Tool(
        name="SendEmail",
        description=(
            "Send an email on the user's behalf. Call this only when the user "
            "explicitly asks to send (not 'draft' / 'write'). The email is "
            "STAGED for approval — the user sees a preview in the approval "
            "bar and clicks Approve before anything leaves the outbox. If "
            "the user requests revisions, call SendEmail again with the "
            "updated parameters."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "to": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 1,
                    "description": "Recipient email addresses.",
                },
                "cc": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional CC recipients.",
                },
                "subject": {
                    "type": "string",
                    "description": "Email subject line.",
                },
                "body_markdown": {
                    "type": "string",
                    "description": "Email body in plain text or lightweight markdown.",
                },
                "reply_to_message_id": {
                    "type": "string",
                    "description": "Optional: message_id being replied to (enables threading).",
                },
            },
            "required": ["to", "subject", "body_markdown"],
            "additionalProperties": False,
        },
        handler=_send_email,
        is_read_only=False,
        is_externally_visible=True,
        category="gmail",
    )
)
