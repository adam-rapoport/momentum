"""Per-turn model selection.

Picks which Groq model handles this turn. Drafting-heavy turns (PRDs,
stakeholder updates, meeting prep) route to a stronger long-form model;
casual chat and short tool-heavy turns stay on the default (Scout), which
is faster, cheaper, and reliable on our prompt.

V1 rules (first match wins):
    1. Known heavy-drafting slash command at the start of the message.
    2. A skill is already active in session metadata.
    3. Otherwise -> the default model (`settings.groq_model`).

Future heavy-slot candidates (each needs a new provider client, not yet
wired up): Gemini via Google AI Studio, Gemma 4 via Google AI Studio.
"""
from __future__ import annotations

import re

from app.config import settings

HEAVY_SLASH_COMMANDS = {"write-prd", "stakeholder-update", "meeting-prep"}
_SLASH_RE = re.compile(r"^/([a-z][a-z0-9-]*)", re.IGNORECASE)


def select_model(user_text: str, session_metadata: dict | None) -> str:
    slug_match = _SLASH_RE.match((user_text or "").strip())
    if slug_match and slug_match.group(1).lower() in HEAVY_SLASH_COMMANDS:
        return settings.groq_heavy_model

    if (session_metadata or {}).get("active_skill"):
        return settings.groq_heavy_model

    return settings.groq_model
