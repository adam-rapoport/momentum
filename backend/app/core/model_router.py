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
from app.core.model_registry import (
    get_available_models,
    infer_provider,
    is_model_available,
    provider_available,
)
from app.core.skills import load_skills


class NoProviderConfiguredError(RuntimeError):
    """No LLM provider has a usable API key (neither stored nor env), so no
    model can serve this turn. The websocket layer maps this to a
    NO_PROVIDER_CONFIGURED error frame pointing the user at Settings.
    """


# Every skill is a heavy-drafting workflow, so its slash command routes the
# turn to the heavy model. Derived from the skills registry (finding A19) —
# this used to be a hardcoded copy that could silently drift from
# app/skills/*/SKILL.md.
HEAVY_SLASH_COMMANDS = frozenset(
    skill.slash_command for skill in load_skills().values()
)
_SLASH_RE = re.compile(r"^/([a-z][a-z0-9-]*)", re.IGNORECASE)

# `/deep` is an escape hatch: prefixing a message with it forces that one turn
# to the heavy model, overriding the routing heuristics. It must be followed by
# whitespace (or be the whole message) so `/deepdive` doesn't trigger it.
_DEEP_RE = re.compile(r"^/deep(?:\s+(.*))?$", re.IGNORECASE | re.DOTALL)


def parse_deep_flag(user_text: str | None) -> tuple[bool, str]:
    """Detect a leading `/deep` flag and strip it.

    Returns `(is_deep, cleaned_text)`. When the flag is present the caller
    should persist + send the cleaned text (flag removed) and route the turn
    to the heavy model. When absent, the original text is returned unchanged.
    """
    if not user_text:
        return False, user_text or ""
    match = _DEEP_RE.match(user_text.strip())
    if not match:
        return False, user_text
    return True, (match.group(1) or "").strip()


def _fallback_model(role: str, configured: set[str] | None) -> str:
    """The model for a slot when the user has no (usable) preference.

    The env-var default wins when its provider has a key — the original
    behavior. When it doesn't (e.g. an OpenAI-only or Google-only setup,
    finding A16/C6), fall back to any AVAILABLE registry model — preferring
    ones suited to the role — instead of hard-failing the turn with
    "GROQ_API_KEY is not configured". With no provider configured at all,
    raise loudly so the websocket layer can point the user at Settings.
    """
    env_default = settings.groq_model if role == "light" else settings.groq_heavy_model
    if provider_available(infer_provider(env_default), configured):
        return env_default
    candidates = get_available_models(role=role, configured_providers=configured)
    if not candidates:
        # No role-appropriate model — any configured model beats an error.
        candidates = get_available_models(configured_providers=configured)
    if candidates:
        return candidates[0].id
    raise NoProviderConfiguredError(
        "No LLM provider is configured — Momentum has no API key to run a "
        "model with. Open Settings → Connections and connect Groq, Google "
        "AI, or OpenAI (or set an API key in .env)."
    )


# Any available model can fill either slot — role no longer gates the pick, so
# we validate only that the model exists and its provider is configured.
def _resolve_light(prefs: dict | None, configured: set[str] | None) -> str:
    pref = (prefs or {}).get("light_model")
    if (
        isinstance(pref, str)
        and pref
        and is_model_available(pref, configured_providers=configured)
    ):
        return pref
    return _fallback_model("light", configured)


def _resolve_heavy(prefs: dict | None, configured: set[str] | None) -> str:
    pref = (prefs or {}).get("heavy_model")
    if (
        isinstance(pref, str)
        and pref
        and is_model_available(pref, configured_providers=configured)
    ):
        return pref
    return _fallback_model("heavy", configured)


def select_model(
    user_text: str,
    session_metadata: dict | None,
    user_preferences: dict | None = None,
    configured_providers: set[str] | None = None,
    force_heavy: bool = False,
) -> str:
    """Return the model ID for this turn.

    `user_preferences` is the JSONB blob from `users.preferences`.
    `configured_providers`, when given, is the per-user set of providers with
    a usable key (stored or env), so a model the user picked but only has a
    *stored* (non-env) key for is still honored. Both default to None for
    backward compat with callers that don't pass them; tests + older callers
    continue to fall back to env-var defaults.

    `force_heavy` is the `/deep` escape hatch — when True the turn routes to
    the heavy model regardless of the slash-command / active-skill heuristics.
    """
    if force_heavy or parse_deep_flag(user_text)[0]:
        return _resolve_heavy(user_preferences, configured_providers)

    slug_match = _SLASH_RE.match((user_text or "").strip())
    if slug_match and slug_match.group(1).lower() in HEAVY_SLASH_COMMANDS:
        return _resolve_heavy(user_preferences, configured_providers)

    if (session_metadata or {}).get("active_skill"):
        return _resolve_heavy(user_preferences, configured_providers)

    return _resolve_light(user_preferences, configured_providers)
