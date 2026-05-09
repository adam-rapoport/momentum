"""Per-turn model selection.

Picks which model handles this turn. Drafting-heavy turns (PRDs,
stakeholder updates, meeting prep, any active skill) route to a stronger
long-form model; casual chat and short tool-heavy turns stay on the
light default, which is faster, cheaper, and reliable on our prompt.

Resolution order for the chosen model ID:
    1. User preference (from `users.preferences.{light_model,heavy_model}`),
       if set AND still in the registry AND its provider is configured.
    2. Env-var default (`GROQ_MODEL` / `GROQ_HEAVY_MODEL`).

Whether a turn is "heavy" is decided by:
    1. Known heavy-drafting slash command at the start of the message.
    2. A skill is already active in session metadata.
    3. Otherwise it's a light turn.
"""
from __future__ import annotations

import re

from app.config import settings
from app.core.model_registry import is_model_available

HEAVY_SLASH_COMMANDS = {
    "write-prd",
    "stakeholder-update",
    "meeting-prep",
    "sprint-review",
    "feedback-synthesis",
    "release-notes",
    "competitive-analysis",
    "user-story",
    "decision-log",
    "quarterly-review",
}
_SLASH_RE = re.compile(r"^/([a-z][a-z0-9-]*)", re.IGNORECASE)


def _resolve_light(prefs: dict | None) -> str:
    pref = (prefs or {}).get("light_model")
    if isinstance(pref, str) and pref and is_model_available(pref, role="light"):
        return pref
    return settings.groq_model


def _resolve_heavy(prefs: dict | None) -> str:
    pref = (prefs or {}).get("heavy_model")
    if isinstance(pref, str) and pref and is_model_available(pref, role="heavy"):
        return pref
    return settings.groq_heavy_model


def select_model(
    user_text: str,
    session_metadata: dict | None,
    user_preferences: dict | None = None,
) -> str:
    """Return the model ID for this turn.

    `user_preferences` is the JSONB blob from `users.preferences`.
    Defaults to None for backward compat with callers that don't yet pass
    it; tests + older callers continue to fall back to env-var defaults.
    """
    slug_match = _SLASH_RE.match((user_text or "").strip())
    if slug_match and slug_match.group(1).lower() in HEAVY_SLASH_COMMANDS:
        return _resolve_heavy(user_preferences)

    if (session_metadata or {}).get("active_skill"):
        return _resolve_heavy(user_preferences)

    return _resolve_light(user_preferences)
