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
    provider: str         # "groq" | "google" | "openai" | "anthropic" | "openrouter" | "mistral" | "ollama".
    display_name: str     # Shown in the Settings dropdown.
    role: str             # "light" | "heavy" | "either".
    notes: str = ""       # One-line note shown under the dropdown.
    # Which client library serves this model. "openai_compat" goes through an
    # OpenAI-compatible endpoint (the default for every provider);
    # "genai_sdk" goes through Google's native SDK (app.core.
    # google_genai_client), required for Gemini 3.x; "anthropic_sdk" goes
    # through the official anthropic SDK (app.core.anthropic_client).
    client: str = "openai_compat"
    # Max context size in tokens, per the provider's model docs. Used by the
    # session engine's history sliding window (Phase 1 item 10). The default
    # matches the 128k that every current entry meets or exceeds; set the
    # real value when adding a model.
    context_window: int = 128_000


# Model IDs below were verified against each provider's live model-list API in
# June 2026 (Groq /v1/models, Google /v1beta/models). When refreshing, re-check
# those endpoints rather than trusting docs — providers retire IDs on their own
# schedule. Gemini 2.5 was dropped here because Google has it scheduled for
# shutdown in Oct 2026.
REGISTRY: tuple[ModelEntry, ...] = (
    # --- Groq (free tier) ---
    ModelEntry(
        id="meta-llama/llama-4-scout-17b-16e-instruct",
        context_window=131_072,
        provider="groq",
        display_name="Llama 4 Scout (Groq)",
        # "either" so Groq can be picked for the heavy slot too — it's fast and
        # free, though weaker than Gemma/Gemini for long-form drafting.
        role="either",
        notes="Default light model. Fast, cheap, reliable for chat and tool-heavy turns. Usable as a fast (lower-quality) heavy model too.",
    ),
    ModelEntry(
        id="llama-3.1-8b-instant",
        context_window=131_072,
        provider="groq",
        display_name="Llama 3.1 8B Instant (Groq)",
        role="light",
        notes="Smaller alternative — even faster, slightly weaker on multi-turn tool use.",
    ),
    ModelEntry(
        id="openai/gpt-oss-20b",
        context_window=131_072,
        provider="groq",
        display_name="GPT-OSS 20B (Groq)",
        role="light",
        notes="Very fast open model served on Groq's production tier. A stable light pick.",
    ),
    ModelEntry(
        id="llama-3.3-70b-versatile",
        context_window=131_072,
        provider="groq",
        display_name="Llama 3.3 70B (Groq)",
        role="either",
        notes="Larger Llama — stronger for drafting, still fast and free on Groq.",
    ),
    ModelEntry(
        id="openai/gpt-oss-120b",
        context_window=131_072,
        provider="groq",
        display_name="GPT-OSS 120B (Groq)",
        role="heavy",
        notes="Largest open model on Groq — strong reasoning/drafting, still free.",
    ),
    # --- Google: Gemma (open model, free tier) ---
    ModelEntry(
        id="gemma-4-31b-it",
        context_window=128_000,
        provider="google",
        display_name="Gemma 4 31B (Google)",
        role="heavy",
        notes="Strong drafting quality. Emits chain-of-thought blocks that pMomentum strips automatically.",
    ),
    # --- Google: Gemini 3.x via the native google-genai SDK (F5) ---
    # Gemini 3.x models go through the native SDK: the OpenAI-compat endpoint
    # can't carry the `thought_signature` they require on tool-call history,
    # which breaks multi-step skill flows.
    ModelEntry(
        id="gemini-3.1-flash-lite",
        context_window=1_048_576,
        provider="google",
        display_name="Gemini 3.1 Flash Lite (Google, native SDK)",
        role="light",
        notes="Fastest, cheapest current Gemini. Runs on Google's native SDK.",
        client="genai_sdk",
    ),
    ModelEntry(
        id="gemini-3.5-flash",
        context_window=1_048_576,
        provider="google",
        display_name="Gemini 3.5 Flash (Google, native SDK)",
        role="either",
        notes="Fast, current all-rounder Gemini. Runs on Google's native SDK.",
        client="genai_sdk",
    ),
    ModelEntry(
        id="gemini-3.1-pro-preview",
        context_window=1_048_576,
        provider="google",
        display_name="Gemini 3 Pro (Google, native SDK)",
        role="heavy",
        notes="Strongest current Gemini for drafting. Runs on Google's native SDK.",
        client="genai_sdk",
    ),
    # --- OpenAI (paid) ---
    # IDs checked against developers.openai.com/api/docs/models (2026-06-11).
    # The gpt-4o generation is deprecated upstream and was removed here.
    ModelEntry(
        id="gpt-5.5",
        context_window=1_000_000,
        provider="openai",
        display_name="GPT-5.5 (OpenAI)",
        role="either",
        notes="OpenAI's current flagship. Paid — needs billing on your OpenAI key.",
    ),
    ModelEntry(
        id="gpt-5.4",
        context_window=400_000,
        provider="openai",
        display_name="GPT-5.4 (OpenAI)",
        role="either",
        notes="More affordable previous flagship. Paid — needs billing.",
    ),
    ModelEntry(
        id="gpt-5.4-mini",
        context_window=400_000,
        provider="openai",
        display_name="GPT-5.4 mini (OpenAI)",
        role="light",
        notes="Fast, cheap OpenAI mini model — a solid light pick. Paid.",
    ),
    # --- Anthropic (paid) — official anthropic SDK ---
    # IDs/pricing per platform.claude.com (2026-06). Claude models go through
    # the native SDK (app.core.anthropic_client), not an OpenAI-compat shim.
    ModelEntry(
        id="claude-haiku-4-5",
        context_window=200_000,
        provider="anthropic",
        display_name="Claude Haiku 4.5 (Anthropic)",
        role="light",
        notes="Anthropic's fastest, cheapest model — a strong light pick. Paid.",
        client="anthropic_sdk",
    ),
    ModelEntry(
        id="claude-sonnet-4-6",
        context_window=1_000_000,
        provider="anthropic",
        display_name="Claude Sonnet 4.6 (Anthropic)",
        role="either",
        notes="Anthropic's best speed/quality balance — the recommended heavy pick. Paid.",
        client="anthropic_sdk",
    ),
    ModelEntry(
        id="claude-opus-4-8",
        context_window=1_000_000,
        provider="anthropic",
        display_name="Claude Opus 4.8 (Anthropic)",
        role="heavy",
        notes="Anthropic's most capable model for hard drafting/reasoning. Paid, pricier.",
        client="anthropic_sdk",
    ),
    # --- OpenRouter (pay-as-you-go aggregator) ---
    # One key unlocks models from many labs; ids are vendor/model. Curated
    # picks below — re-check openrouter.ai/models when refreshing.
    ModelEntry(
        id="openai/gpt-5.4-mini",
        context_window=400_000,
        provider="openrouter",
        display_name="GPT-5.4 mini (OpenRouter)",
        role="light",
        notes="Cheap, fast light pick via OpenRouter.",
    ),
    ModelEntry(
        id="google/gemini-3.5-flash",
        context_window=1_000_000,
        provider="openrouter",
        display_name="Gemini 3.5 Flash (OpenRouter)",
        role="either",
        notes="Fast all-rounder via OpenRouter.",
    ),
    ModelEntry(
        id="anthropic/claude-sonnet-4.6",
        context_window=1_000_000,
        provider="openrouter",
        display_name="Claude Sonnet 4.6 (OpenRouter)",
        role="either",
        notes="Claude Sonnet served via OpenRouter — good heavy pick.",
    ),
    ModelEntry(
        id="openai/gpt-5.5",
        context_window=1_000_000,
        provider="openrouter",
        display_name="GPT-5.5 (OpenRouter)",
        role="heavy",
        notes="OpenAI's flagship via OpenRouter.",
    ),
    # --- Mistral ---
    # The -latest aliases track Mistral's current generation automatically.
    ModelEntry(
        id="mistral-small-latest",
        context_window=128_000,
        provider="mistral",
        display_name="Mistral Small (Mistral)",
        role="light",
        notes="Fast, cheap Mistral — has a free tier.",
    ),
    ModelEntry(
        id="mistral-medium-latest",
        context_window=128_000,
        provider="mistral",
        display_name="Mistral Medium (Mistral)",
        role="either",
        notes="Mid-tier Mistral — balanced speed and quality.",
    ),
    ModelEntry(
        id="mistral-large-latest",
        context_window=128_000,
        provider="mistral",
        display_name="Mistral Large (Mistral)",
        role="heavy",
        notes="Strongest Mistral for drafting and reasoning.",
    ),
)


# Name-prefix heuristics for models that are NOT in the registry (raw env-var
# overrides). The registry entry is always consulted first — these exist only
# so a user pointing GROQ_MODEL/GROQ_HEAVY_MODEL at an unregistered ID still
# gets a sensible provider (findings A17/C6).
_GOOGLE_PREFIXES = ("gemini-", "gemma-")
_OPENAI_PREFIXES = ("gpt-", "o1-", "o3-", "o4-", "chatgpt-")
_ANTHROPIC_PREFIXES = ("claude-",)
_MISTRAL_PREFIXES = ("mistral-", "magistral-", "ministral-", "codestral-")


def infer_provider(model_id: str) -> str:
    """Provider name ("groq", "google", "openai", ...) for `model_id`.

    Single source of provider truth: the registry entry decides when one
    exists; unknown (env-override) ids fall back to the name-prefix
    heuristics, defaulting to groq — the original behavior. The bare-"/"
    rule (vendor/model -> openrouter) runs LAST and only for unregistered
    ids, so the slash-bearing Groq registry ids keep resolving to groq;
    caveat: an unregistered slash-id env override now infers openrouter.
    """
    entry = get_model(model_id)
    if entry is not None:
        return entry.provider
    if model_id.startswith("ollama:"):
        return "ollama"
    if model_id.startswith(_GOOGLE_PREFIXES):
        return "google"
    if model_id.startswith(_OPENAI_PREFIXES):
        return "openai"
    if model_id.startswith(_ANTHROPIC_PREFIXES):
        return "anthropic"
    if model_id.startswith(_MISTRAL_PREFIXES):
        return "mistral"
    if "/" in model_id:
        return "openrouter"
    return "groq"


def provider_available(
    provider: str, configured_providers: set[str] | None = None
) -> bool:
    """Public availability check for a provider name: the per-user set when
    given, the env vars otherwise (single-arg call so monkeypatched stand-ins
    in tests keep working — same convention as get_available_models)."""
    if configured_providers is not None:
        return provider in configured_providers
    return _provider_available(provider)


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
    if provider == "anthropic":
        return bool(settings.anthropic_api_key)
    if provider == "openrouter":
        return bool(settings.openrouter_api_key)
    if provider == "mistral":
        return bool(settings.mistral_api_key)
    if provider == "ollama":
        return bool(settings.ollama_base_url)
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
    and (optionally) can serve the requested role.

    Ollama models are dynamic (whatever the user has pulled locally, ids
    "ollama:<name>") and never appear in the static registry — any ollama:
    id is available whenever the Ollama connection is configured. Role
    doesn't gate them: a local model may serve either slot."""
    if model_id.startswith("ollama:"):
        return provider_available("ollama", configured_providers)
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
