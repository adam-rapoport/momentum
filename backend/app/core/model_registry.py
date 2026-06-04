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
    provider: str         # "groq" | "google" | "openai".
    display_name: str     # Shown in the Settings dropdown.
    role: str             # "light" | "heavy" | "either".
    notes: str = ""       # One-line note shown under the dropdown.
    # Which client library serves this model. Only consulted for Google
    # models: "openai_compat" goes through the OpenAI-compatible endpoint
    # (app.core.google_client); "genai_sdk" goes through Google's native
    # SDK (app.core.google_genai_client), which is required for Gemini 3.x.
    # Groq/OpenAI models ignore this field.
    client: str = "openai_compat"


REGISTRY: tuple[ModelEntry, ...] = (
    ModelEntry(
        id="meta-llama/llama-4-scout-17b-16e-instruct",
        provider="groq",
        display_name="Llama 4 Scout (Groq)",
        # "either" so Groq can be picked for the heavy slot too — it's fast and
        # free, though weaker than Gemma/Gemini for long-form drafting.
        role="either",
        notes="Default light model. Fast, cheap, reliable for chat and tool-heavy turns. Usable as a fast (lower-quality) heavy model too.",
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
    # --- Google via the native google-genai SDK (F5) ---
    # Gemini 3.x preview models only work through the native SDK: the
    # OpenAI-compat endpoint can't carry the `thought_signature` they
    # require on tool-call history, which breaks multi-step skill flows.
    ModelEntry(
        id="gemini-3.1-pro-preview",
        provider="google",
        display_name="Gemini 3 Pro (Google, native SDK)",
        role="heavy",
        notes="Newest Gemini for drafting. Runs on Google's native SDK.",
        client="genai_sdk",
    ),
    ModelEntry(
        id="gemini-3-flash-preview",
        provider="google",
        display_name="Gemini 3 Flash (Google, native SDK)",
        role="either",
        notes="Fast newest Gemini. Runs on Google's native SDK.",
        client="genai_sdk",
    ),
    # --- OpenAI (paid) ---
    ModelEntry(
        id="gpt-4o",
        provider="openai",
        display_name="GPT-4o (OpenAI)",
        role="either",
        notes="OpenAI's flagship. Paid — needs billing on your OpenAI key.",
    ),
    ModelEntry(
        id="gpt-4o-mini",
        provider="openai",
        display_name="GPT-4o mini (OpenAI)",
        role="light",
        notes="Cheaper, faster OpenAI model. Paid — needs billing.",
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
    if provider == "openai":
        return bool(settings.openai_api_key)
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
