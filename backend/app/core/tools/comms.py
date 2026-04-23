"""Communication tools: DraftMessage.

DraftMessage formats a message and returns the draft text. It does NOT
send anything — actual delivery to email/Slack is a Sprint 4 concern
that will need real integrations, auth, and confirmation UI.

The tool result message becomes the persistent record of the draft; the
frontend can surface it as a review artifact.
"""
from __future__ import annotations

from app.core.tools import Tool, register

_ALLOWED_PLATFORMS = {"email", "slack"}


async def _draft_message(input_data: dict) -> str:
    platform = (input_data.get("platform") or "").strip().lower()
    recipient = (input_data.get("recipient") or "").strip()
    subject = (input_data.get("subject") or "").strip()
    body = (input_data.get("body") or "").strip()

    if platform not in _ALLOWED_PLATFORMS:
        return f"Error: 'platform' must be one of {sorted(_ALLOWED_PLATFORMS)}."
    if not recipient:
        return "Error: 'recipient' is required."
    if not body:
        return "Error: 'body' is required."
    if platform == "email" and not subject:
        return "Error: 'subject' is required for email drafts."

    if platform == "email":
        header = f"[DRAFT — EMAIL]\nTo: {recipient}\nSubject: {subject}\n"
    else:
        header = f"[DRAFT — SLACK]\nTo: {recipient}\n"

    return (
        f"{header}\n{body}\n\n"
        "--- end of draft ---\n"
        "This is a DRAFT only — nothing has been sent. "
        "The user must review and copy-paste to actually send."
    )


DraftMessage = register(
    Tool(
        name="DraftMessage",
        description=(
            "Format a draft email or Slack message for the user to review. "
            "Does NOT send — produces a formatted draft they can review and "
            "copy. Use this when the user asks you to draft, write, or "
            "compose a message to someone (a teammate, stakeholder, "
            "customer). Always match the recipient's known preferences "
            "(e.g., bullets if the stakeholder memory says they prefer bullets)."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "platform": {
                    "type": "string",
                    "enum": sorted(_ALLOWED_PLATFORMS),
                    "description": "Delivery channel: 'email' or 'slack'.",
                },
                "recipient": {
                    "type": "string",
                    "description": "Email address (for email) or name/handle (for slack).",
                },
                "subject": {
                    "type": "string",
                    "description": "Subject line (required for email, ignored for slack).",
                },
                "body": {
                    "type": "string",
                    "description": "The message body. Markdown is OK — consumers will render as plain text.",
                },
            },
            "required": ["platform", "recipient", "body"],
            "additionalProperties": False,
        },
        handler=_draft_message,
        is_read_only=True,
        is_externally_visible=True,
        category="communication",
    )
)
