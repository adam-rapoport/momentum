"""Registry of LLM models that pMomentum can route turns to.

Chunk C of Sprint 6 makes the per-turn model selection user-controllable
via a Settings UI. The registry is the single source of truth for which
models exist, which provider serves them, whether they belong in the
"light" or "heavy" slot (or either), and what to display in the picker.

Filtering:
    `get_available_models()` removes entries whose required env vars are
    not set, so the Settings UI only ever shows models the user can
    actually run. Groq models need GROQ_API_KEY; Google models need
    GOOGLE_AI_API_KEY.

Adding a model:
    Append a new ModelEntry below. The frontend reads this same list via
    the /preferences/models endpoint, so backend and UI can't drift.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.config import settings


@dataclass(frozen=True)
class ModelEntry:
    id: str               # Model ID passed to the LLM client.
    provider: str         # "groq" | "google".
    display_name: str     # Shown in the Settings dropdown.
    role: str             # "light" | "heavy" | "either".
    notes: str = ""       # One-line note shown under the dropdown.


REGISTRY: tuple[ModelEntry, ...] = (
    ModelEntry(
        id="meta-llama/llama-4-scout-17b-16e-instruct",
        provider="groq",
        display_name="Llama 4 Scout (Groq)",
        role="light",
        notes="Default light model. Fast, cheap, reliable for chat and tool-heavy turns.",
    ),
    ModelEntry(
        id="llama-3.1-8b-instant",
        provider="groq",
        display_name="Llama 3.1 8B Instant (Groq)",
        role="light",
        notes="Smaller alternative — even faster, slightly weaker on multi-turn tool use.",
    ),
    ModelEntry(
        id="gemma-4-31b-it",
        provider="google",
        display_name="Gemma 4 31B (Google)",
        role="heavy",
        notes="Strong drafting quality. Emits chain-of-thought blocks that pMomentum strips automatically.",
    ),
    ModelEntry(
        id="gemini-2.5-flash",
        provider="google",
        display_name="Gemini 2.5 Flash (Google)",
        role="either",
        notes="Fast Gemini variant on the free tier. Works as either light or heavy.",
    ),
    ModelEntry(
        id="gemini-2.5-pro",
        provider="google",
        display_name="Gemini 2.5 Pro (Google)",
        role="heavy",
        notes="Strongest free-tier Gemini for drafting. Slower than Flash.",
    ),
)


def _provider_available(
    provider: str, configured_providers: set[str] | None = None
) -> bool:
    # When the caller passes a per-user set of configured providers (computed
    # from stored keys OR env by app.core.credentials), honor it. Otherwise
    # fall back to the global env check — the original behavior, which keeps
    # tests and env-only deployments working unchanged.
    if configured_providers is not None:
        return provider in configured_providers
    if provider == "groq":
        return bool(settings.groq_api_key)
    if provider == "google":
        return bool(settings.google_ai_api_key)
    return False


def get_available_models(
    role: str | None = None, configured_providers: set[str] | None = None
) -> list[ModelEntry]:
    """Return registry entries whose provider is configured.

    If `role` is provided ("light" or "heavy"), filter to entries that
    can serve that role (including those marked "either"). If
    `configured_providers` is provided, availability is judged against that
    per-user set instead of the global env vars.
    """
    if configured_providers is None:
        # Default (env-based) path — call with one arg so monkeypatched
        # single-arg stand-ins in tests keep working.
        entries = [m for m in REGISTRY if _provider_available(m.provider)]
    else:
        entries = [
            m
            for m in REGISTRY
            if _provider_available(m.provider, configured_providers)
        ]
    if role in ("light", "heavy"):
        entries = [m for m in entries if m.role == role or m.role == "either"]
    return entries


def is_model_available(
    model_id: str,
    role: str | None = None,
    configured_providers: set[str] | None = None,
) -> bool:
    """Whether `model_id` is in the registry, has its provider configured,
    and (optionally) can serve the requested role."""
    return any(
        m.id == model_id
        for m in get_available_models(
            role=role, configured_providers=configured_providers
        )
    )


def get_model(model_id: str) -> ModelEntry | None:
    """Look up a registry entry by model ID, regardless of availability."""
    for m in REGISTRY:
        if m.id == model_id:
            return m
    return None
