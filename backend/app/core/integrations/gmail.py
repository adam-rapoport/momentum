"""Gmail adapter — thin wrapper over the Gmail REST API.

Follows the same shape as `google_docs.py`: one `_get_integration` +
`_build_gmail` pair that reuses the unified Google OAuth credentials,
then a handful of async helpers the tools (`app/core/tools/gmail.py`)
call.

Design choices for MVP simplicity:
- Message bodies are always decoded to plain text. Multipart emails
  prefer `text/plain`, fall back to stripping tags from `text/html`.
  Bodies are capped at 8000 chars (same as Docs read) so one verbose
  marketing email can't swamp the model's context.
- Drafts are created via the Gmail API but NEVER auto-sent from this
  module. Actually sending a message is a separate call gated by the
  pause-and-review flow (Chunk E); until then `send_message` just
  creates a draft and tells the caller to send from Gmail's UI.
- Replies: pass `reply_to_message_id` — we look up the original's
  Message-ID + Subject + threadId and set `In-Reply-To`, `References`,
  and `threadId` so Gmail threads the conversation.
"""
from __future__ import annotations

import asyncio
import base64
import html
import logging
import re
from datetime import datetime, timezone
from email.message import EmailMessage
from typing import Any

from google.oauth2.credentials import Credentials as GoogleCredentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.integrations.google_oauth import (
    OAuthFlowError,
    PROVIDER,
    SCOPES,
    get_valid_access_token,
)
from app.models import Integration

logger = logging.getLogger(__name__)

BODY_CHAR_CAP = 8000
MAX_MESSAGES_PER_LIST = 25


class GmailNotConnected(RuntimeError):
    pass


class GmailError(RuntimeError):
    """Any Gmail API failure the user can act on — usually 'reconnect.'"""


class GmailApiNotEnabled(GmailError):
    """The Gmail API has not been enabled in the user's Google Cloud project.
    One-time admin step at console.developers.google.com — distinct enough
    from a transient API failure that it's worth its own subclass so the
    tool layer can surface a clear instruction."""


def _wrap_http_error(e: HttpError, action: str) -> GmailError:
    """Convert a Google HttpError into one of our typed errors with a
    user-actionable message — strips the giant URL/JSON dumps from the
    stock library exception."""
    status = getattr(getattr(e, "resp", None), "status", None)
    detail = ""
    try:
        # error_details is usually a list of dicts with 'message' / 'reason'
        details = getattr(e, "error_details", None) or []
        if details and isinstance(details, list):
            first = details[0]
            if isinstance(first, dict):
                reason = first.get("reason", "")
                detail = first.get("message", "") or ""
                if reason == "accessNotConfigured":
                    return GmailApiNotEnabled(
                        "Gmail API is not enabled for this Google Cloud "
                        "project. Open https://console.developers.google.com"
                        "/apis/api/gmail.googleapis.com/overview and click "
                        "Enable, then wait ~30 seconds and retry."
                    )
    except Exception:  # noqa: BLE001 — error-formatting fallback
        pass
    if status == 403:
        return GmailError(
            f"Gmail {action} denied (403). Either the Gmail API is disabled "
            f"in your Google Cloud project, or the granted scopes don't "
            f"cover this action. {detail}".strip()
        )
    if status == 401:
        return GmailError(
            f"Gmail {action} unauthorized (401). Reconnect Google in Settings."
        )
    if status == 404:
        return GmailError(f"Gmail {action} target not found (404). {detail}".strip())
    return GmailError(f"Gmail {action} failed ({status}). {detail}".strip())


async def _get_integration(db: AsyncSession, user_id) -> Integration:
    integration = await db.scalar(
        select(Integration).where(
            Integration.user_id == user_id, Integration.provider == PROVIDER
        )
    )
    if integration is None or integration.status != "connected":
        raise GmailNotConnected(
            "Google is not connected. Visit Settings to connect."
        )
    granted = set(integration.scopes or [])
    if "https://www.googleapis.com/auth/gmail.readonly" not in granted:
        raise GmailNotConnected(
            "Gmail permission not granted. Visit Settings and click Reconnect "
            "to grant access to Gmail."
        )
    return integration


async def _build_gmail(db: AsyncSession, integration: Integration):
    access_token = await get_valid_access_token(db, integration)
    creds = GoogleCredentials(token=access_token, scopes=SCOPES)
    return await asyncio.to_thread(
        build, "gmail", "v1", credentials=creds, cache_discovery=False
    )


# ---------- Body parsing ----------


_HTML_TAG_RE = re.compile(r"<[^>]+>")
# Include \xa0 (the char &nbsp; decodes to) so marketing HTML doesn't
# leave non-breaking spaces littering the plain-text output.
_WS_RE = re.compile(r"[ \t\xa0]+")
_BLANK_LINE_RE = re.compile(r"\n{3,}")


def _decode_part_body(part: dict) -> bytes:
    data = ((part.get("body") or {}).get("data")) or ""
    if not data:
        return b""
    # Gmail returns base64url-encoded data.
    return base64.urlsafe_b64decode(data.encode("ascii") + b"==")


def _strip_html(html_text: str) -> str:
    """Turn HTML into readable plain text: drop tags, unescape entities,
    collapse whitespace. Not perfect but keeps real inbox contents
    usable in the model's context without CSS/tracking-pixel noise."""
    # Zap style/script blocks entirely before stripping other tags.
    cleaned = re.sub(
        r"<(script|style)[^>]*>.*?</\1>", "", html_text, flags=re.DOTALL | re.IGNORECASE
    )
    # Treat <br> and block closers as newlines so paragraphs survive.
    cleaned = re.sub(r"<\s*br\s*/?\s*>", "\n", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(
        r"</\s*(p|div|li|h[1-6]|tr)\s*>", "\n", cleaned, flags=re.IGNORECASE
    )
    cleaned = _HTML_TAG_RE.sub("", cleaned)
    cleaned = html.unescape(cleaned)
    cleaned = _WS_RE.sub(" ", cleaned)
    cleaned = _BLANK_LINE_RE.sub("\n\n", cleaned)
    return cleaned.strip()


def _extract_plain_text_body(payload: dict | None) -> str:
    """Prefer the first text/plain part; fall back to stripping text/html."""
    if not payload:
        return ""

    # Flat payload (non-multipart)
    mime = payload.get("mimeType", "")
    if not payload.get("parts"):
        body = _decode_part_body(payload)
        if not body:
            return ""
        text = body.decode("utf-8", errors="replace")
        if mime == "text/html":
            return _strip_html(text)
        return text

    # Multipart: breadth-first search for text/plain, keep first text/html as fallback.
    queue: list[dict] = list(payload["parts"])
    html_fallback: str | None = None
    while queue:
        part = queue.pop(0)
        if part.get("parts"):
            queue.extend(part["parts"])
        part_mime = part.get("mimeType", "")
        if part_mime == "text/plain":
            body = _decode_part_body(part)
            if body:
                return body.decode("utf-8", errors="replace")
        elif part_mime == "text/html" and html_fallback is None:
            body = _decode_part_body(part)
            if body:
                html_fallback = _strip_html(body.decode("utf-8", errors="replace"))
    return html_fallback or ""


def _headers_to_dict(headers: list[dict] | None) -> dict[str, str]:
    """Flatten Gmail's [{name, value}, ...] into a lowercased-key dict."""
    return {h["name"].lower(): h.get("value", "") for h in (headers or [])}


def _truncate(text: str, limit: int = BODY_CHAR_CAP) -> tuple[str, bool]:
    if len(text) <= limit:
        return text, False
    return text[:limit].rstrip(), True


def _message_url(message_id: str) -> str:
    return f"https://mail.google.com/mail/u/0/#all/{message_id}"


# ---------- Public helpers ----------


async def list_recent_messages(
    db: AsyncSession,
    user_id,
    *,
    query: str | None = None,
    max_results: int = 10,
    label: str | None = None,
) -> list[dict[str, Any]]:
    """Return a compact list of recent messages. `query` is Gmail search
    syntax (`from:alice is:unread newer_than:7d`). `label` is an optional
    Gmail label name (INBOX, STARRED, SENT, or a custom one)."""
    integration = await _get_integration(db, user_id)
    gmail = await _build_gmail(db, integration)

    max_results = max(1, min(max_results, MAX_MESSAGES_PER_LIST))

    def _sync_list() -> list[dict[str, Any]]:
        list_kwargs: dict[str, Any] = {
            "userId": "me",
            "maxResults": max_results,
        }
        if query:
            list_kwargs["q"] = query
        if label:
            list_kwargs["labelIds"] = [label.upper() if label.upper() == label else label]
        resp = gmail.users().messages().list(**list_kwargs).execute()
        ids = [m["id"] for m in (resp.get("messages") or [])]
        out: list[dict[str, Any]] = []
        for mid in ids:
            try:
                msg = (
                    gmail.users()
                    .messages()
                    .get(
                        userId="me",
                        id=mid,
                        format="metadata",
                        metadataHeaders=["From", "To", "Subject", "Date"],
                    )
                    .execute()
                )
            except HttpError as e:
                logger.warning("gmail message metadata fetch failed for %s: %s", mid, e)
                continue
            headers = _headers_to_dict((msg.get("payload") or {}).get("headers"))
            labels = msg.get("labelIds") or []
            out.append(
                {
                    "id": mid,
                    "thread_id": msg.get("threadId"),
                    "from": headers.get("from", ""),
                    "to": headers.get("to", ""),
                    "subject": headers.get("subject", "(no subject)"),
                    "date": headers.get("date", ""),
                    "snippet": msg.get("snippet", ""),
                    "unread": "UNREAD" in labels,
                    "url": _message_url(mid),
                }
            )
        return out

    try:
        return await asyncio.to_thread(_sync_list)
    except HttpError as e:
        raise _wrap_http_error(e, "list") from e
    except OAuthFlowError:
        raise


async def read_message(
    db: AsyncSession, user_id, message_id: str
) -> dict[str, Any]:
    """Fetch a single message, returning headers + plain-text body."""
    integration = await _get_integration(db, user_id)
    gmail = await _build_gmail(db, integration)

    def _sync_read() -> dict[str, Any]:
        msg = (
            gmail.users()
            .messages()
            .get(userId="me", id=message_id, format="full")
            .execute()
        )
        payload = msg.get("payload") or {}
        headers = _headers_to_dict(payload.get("headers"))
        body = _extract_plain_text_body(payload).rstrip()
        body, truncated = _truncate(body)
        return {
            "id": message_id,
            "thread_id": msg.get("threadId"),
            "from": headers.get("from", ""),
            "to": headers.get("to", ""),
            "cc": headers.get("cc", ""),
            "subject": headers.get("subject", "(no subject)"),
            "date": headers.get("date", ""),
            "message_id_header": headers.get("message-id", ""),
            "references": headers.get("references", ""),
            "body_text": body,
            "truncated": truncated,
            "url": _message_url(message_id),
        }

    try:
        return await asyncio.to_thread(_sync_read)
    except HttpError as e:
        if e.resp.status == 404:
            raise FileNotFoundError(f"message '{message_id}' not found") from e
        raise _wrap_http_error(e, "read") from e


def _build_mime_message(
    *,
    to: list[str],
    cc: list[str] | None,
    subject: str,
    body_text: str,
    in_reply_to: str | None = None,
    references: str | None = None,
) -> str:
    """Compose an RFC 822 message, return the base64url-encoded raw bytes
    Gmail's `drafts.create` / `messages.send` expect."""
    msg = EmailMessage()
    msg["To"] = ", ".join(to)
    if cc:
        msg["Cc"] = ", ".join(cc)
    msg["Subject"] = subject
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
    if references:
        msg["References"] = references
    msg.set_content(body_text)
    return base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii")


async def _lookup_reply_context(
    gmail: Any, message_id: str
) -> tuple[str, str, str]:
    """For a reply target, return (thread_id, message_id_header, subject)
    so we can thread correctly and auto-prefix 'Re: '."""

    def _sync() -> tuple[str, str, str]:
        msg = (
            gmail.users()
            .messages()
            .get(
                userId="me",
                id=message_id,
                format="metadata",
                metadataHeaders=["Message-Id", "References", "Subject"],
            )
            .execute()
        )
        headers = _headers_to_dict((msg.get("payload") or {}).get("headers"))
        thread_id = msg.get("threadId") or ""
        return thread_id, headers.get("message-id", ""), headers.get("subject", "")

    return await asyncio.to_thread(_sync)


async def create_draft(
    db: AsyncSession,
    user_id,
    *,
    to: list[str],
    cc: list[str] | None,
    subject: str,
    body_markdown: str,
    reply_to_message_id: str | None = None,
) -> dict[str, Any]:
    integration = await _get_integration(db, user_id)
    granted = set(integration.scopes or [])
    if "https://www.googleapis.com/auth/gmail.compose" not in granted:
        raise GmailNotConnected(
            "Gmail compose permission missing — Reconnect in Settings."
        )
    gmail = await _build_gmail(db, integration)

    thread_id = None
    in_reply_to = None
    references = None
    subject_final = subject
    if reply_to_message_id:
        try:
            thread_id, orig_msg_id, orig_subject = await _lookup_reply_context(
                gmail, reply_to_message_id
            )
        except HttpError as e:
            raise GmailError(f"Couldn't find reply target: {e}") from e
        if orig_msg_id:
            in_reply_to = orig_msg_id
            references = orig_msg_id
        if orig_subject and not subject_final.lower().startswith("re:"):
            subject_final = f"Re: {orig_subject}" if orig_subject else subject_final

    raw = _build_mime_message(
        to=to,
        cc=cc,
        subject=subject_final,
        body_text=body_markdown,
        in_reply_to=in_reply_to,
        references=references,
    )

    draft_body: dict[str, Any] = {"message": {"raw": raw}}
    if thread_id:
        draft_body["message"]["threadId"] = thread_id

    def _sync_create() -> dict[str, Any]:
        return (
            gmail.users()
            .drafts()
            .create(userId="me", body=draft_body)
            .execute()
        )

    try:
        draft = await asyncio.to_thread(_sync_create)
    except HttpError as e:
        raise _wrap_http_error(e, "draft create") from e
    except OAuthFlowError:
        raise

    draft_id = draft.get("id") or ""
    message = draft.get("message") or {}
    message_id = message.get("id") or ""
    return {
        "draft_id": draft_id,
        "message_id": message_id,
        "thread_id": message.get("threadId") or thread_id,
        "subject": subject_final,
        "to": to,
        "cc": cc or [],
        # Gmail's drafts URL doesn't expose a deep-link to a specific draft,
        # but the drafts folder is one click away from anything.
        "url": "https://mail.google.com/mail/u/0/#drafts",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


async def send_draft(
    db: AsyncSession, user_id, draft_id: str
) -> dict[str, Any]:
    """Actually send a previously-created draft. Used by the pause-and-review
    flow in Chunk E: the tool stages a draft, the user approves, this fires."""
    integration = await _get_integration(db, user_id)
    granted = set(integration.scopes or [])
    if "https://www.googleapis.com/auth/gmail.send" not in granted:
        raise GmailNotConnected(
            "Gmail send permission missing — Reconnect in Settings."
        )
    gmail = await _build_gmail(db, integration)

    def _sync_send() -> dict[str, Any]:
        return (
            gmail.users()
            .drafts()
            .send(userId="me", body={"id": draft_id})
            .execute()
        )

    try:
        sent = await asyncio.to_thread(_sync_send)
    except HttpError as e:
        raise _wrap_http_error(e, "send") from e
    except OAuthFlowError:
        raise

    return {
        "message_id": sent.get("id", ""),
        "thread_id": sent.get("threadId", ""),
        "sent_at": datetime.now(timezone.utc).isoformat(),
    }


async def is_connected(db: AsyncSession, user_id) -> bool:
    try:
        await _get_integration(db, user_id)
        return True
    except GmailNotConnected:
        return False
