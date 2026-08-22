"""Registry of LLM models that Momentum can route turns to.

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


# Model IDs below were verified against each provider's live model-list API
# (Groq /v1/models, Google /v1beta/models, OpenAI /v1/models, Anthropic
# /v1/models, Mistral /v1/models — all re-checked 2026-08-22). When
# refreshing, re-check those endpoints rather than trusting docs — providers
# retire IDs on their own schedule. Removed June 2026: Gemini 2.5 (Google
# shutdown Oct 2026) and Llama 4 Scout. Removed Aug 2026: Groq's
# llama-3.1-8b-instant and llama-3.3-70b-versatile (Groq shut both down
# 2026-08-16; gpt-oss-* / qwen3.6-27b are its recommended replacements — and
# all three now WORK ON THE FREE TIER, 8k TPM). The default LIGHT model is
# gemini-3.5-flash-lite, not a Groq model: Groq's free-tier tokens/min cap is
# smaller than the app's per-turn context, so every Groq free turn 429s (see
# app.config.groq_model). Groq models remain here and stay user-selectable.
REGISTRY: tuple[ModelEntry, ...] = (
    # --- Groq (fast inference; free tier gated only by rate limits) ---
    ModelEntry(
        id="qwen/qwen3.6-27b",
        context_window=131_072,
        provider="groq",
        display_name="Qwen3.6 27B (Groq)",
        role="either",
        notes="Groq's recommended heavy-slot replacement for its retired Llamas. Free tier, but the ~8k tokens/min cap is tight for this app — best on a paid Groq tier.",
    ),
    ModelEntry(
        id="openai/gpt-oss-20b",
        context_window=131_072,
        provider="groq",
        display_name="GPT-OSS 20B (Groq)",
        role="either",
        notes="Fast open model — now on Groq's free tier too, though the ~8k tokens/min cap is tight for this app. Best on a paid Groq tier.",
    ),
    ModelEntry(
        id="openai/gpt-oss-120b",
        context_window=131_072,
        provider="groq",
        display_name="GPT-OSS 120B (Groq)",
        role="heavy",
        notes="Largest open model on Groq, strong reasoning — now on Groq's free tier too (tight ~8k tokens/min cap; best on a paid tier).",
    ),
    # --- Google: Gemma (open model, free tier) ---
    ModelEntry(
        id="gemma-4-31b-it",
        context_window=128_000,
        provider="google",
        display_name="Gemma 4 31B (Google)",
        role="heavy",
        notes="Strong drafting quality. Emits chain-of-thought blocks that Momentum strips automatically.",
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
        notes="Older Flash Lite — Google retires it May 2027; 3.5 Flash Lite is its successor. Runs on Google's native SDK.",
        client="genai_sdk",
    ),
    ModelEntry(
        id="gemini-3.5-flash-lite",
        context_window=1_048_576,
        provider="google",
        display_name="Gemini 3.5 Flash Lite (Google, native SDK)",
        role="light",
        notes="Fastest, cheapest current Gemini — the default light pick. Free tier. Runs on Google's native SDK.",
        client="genai_sdk",
    ),
    ModelEntry(
        id="gemini-3.5-flash",
        context_window=1_048_576,
        provider="google",
        display_name="Gemini 3.5 Flash (Google, native SDK)",
        role="either",
        notes="Fast all-rounder Gemini. Runs on Google's native SDK.",
        client="genai_sdk",
    ),
    ModelEntry(
        id="gemini-3.6-flash",
        context_window=1_048_576,
        provider="google",
        display_name="Gemini 3.6 Flash (Google, native SDK)",
        role="either",
        notes="Strong Flash with a free tier (3.7 Flash has since superseded it). Runs on Google's native SDK.",
        client="genai_sdk",
    ),
    ModelEntry(
        id="gemini-3.7-flash",
        context_window=1_048_576,
        provider="google",
        display_name="Gemini 3.7 Flash (Google, native SDK)",
        role="either",
        notes="Google's newest, strongest Flash — built for agents and tool use, free tier, half-price intro through Dec 2026. The default heavy pick.",
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
    # IDs verified live against the OpenAI API (2026-08-22).
    # The gpt-4o generation is deprecated upstream and was removed here.
    # Removed Aug 2026: the original gpt-5/-mini/-nano/-pro family — OpenAI
    # announced a hard shutdown for 2026-12-11 (replacements: the 5.4 and 5.6
    # generations below; 5.6 Luna is now cheaper than gpt-5-nano was).
    # GPT-5.4 / 5.5 / 5.6 generations — IDs verified live against the OpenAI
    # /v1/models API (2026-07-29). The 5.6 generation ships as three named
    # tiers (Luna = light, Terra = mid, Sol = flagship) instead of
    # nano/mini/full. The ultra-premium -pro tiers ($30/$180 per MTok) are
    # deliberately not listed. The big models advertise ~1.05M context;
    # recorded conservatively at 1M for the history window.
    ModelEntry(
        id="gpt-5.4",
        context_window=1_000_000,
        provider="openai",
        display_name="GPT-5.4 (OpenAI)",
        role="either",
        notes="Newer-generation flagship — 1M context, strong all-rounder. Paid.",
    ),
    ModelEntry(
        id="gpt-5.4-mini",
        context_window=400_000,
        provider="openai",
        display_name="GPT-5.4 mini (OpenAI)",
        role="either",
        notes="Faster, cheaper GPT-5.4 — a balanced everyday pick. Paid.",
    ),
    ModelEntry(
        id="gpt-5.4-nano",
        context_window=400_000,
        provider="openai",
        display_name="GPT-5.4 nano (OpenAI)",
        role="light",
        notes="Cheapest, fastest GPT-5.4 — a solid light pick. Paid.",
    ),
    ModelEntry(
        id="gpt-5.5",
        context_window=1_000_000,
        provider="openai",
        display_name="GPT-5.5 (OpenAI)",
        role="heavy",
        notes="Stronger than GPT-5.4 for hard drafting/reasoning — 1M context. Paid, pricier.",
    ),
    ModelEntry(
        id="gpt-5.6-luna",
        context_window=1_000_000,
        provider="openai",
        display_name="GPT-5.6 Luna (OpenAI)",
        role="light",
        notes="Newest generation's light tier — fast and cheap with 1M context. Paid.",
    ),
    ModelEntry(
        id="gpt-5.6-terra",
        context_window=1_000_000,
        provider="openai",
        display_name="GPT-5.6 Terra (OpenAI)",
        role="either",
        notes="Newest generation's balanced tier — 1M context all-rounder. Paid.",
    ),
    ModelEntry(
        id="gpt-5.6-sol",
        context_window=1_000_000,
        provider="openai",
        display_name="GPT-5.6 Sol (OpenAI)",
        role="heavy",
        notes="Newest generation's flagship — strongest for hard drafting/reasoning. Paid, pricier.",
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
        id="claude-sonnet-5",
        context_window=1_000_000,
        provider="anthropic",
        display_name="Claude Sonnet 5 (Anthropic)",
        role="either",
        notes="Anthropic's newest Sonnet — near-Opus quality for coding and reasoning at Sonnet pricing ($2/$10, made permanent Aug 2026). A strong heavy pick. Paid.",
        client="anthropic_sdk",
    ),
    ModelEntry(
        id="claude-opus-4-8",
        context_window=1_000_000,
        provider="anthropic",
        display_name="Claude Opus 4.8 (Anthropic)",
        role="heavy",
        notes="Previous-generation Opus — still excellent for hard drafting/reasoning. Paid, pricier.",
        client="anthropic_sdk",
    ),
    ModelEntry(
        id="claude-opus-5",
        context_window=1_000_000,
        provider="anthropic",
        display_name="Claude Opus 5 (Anthropic)",
        role="heavy",
        notes="Anthropic's most capable model for hard drafting/reasoning — same price as Opus 4.8. Paid, pricier.",
        client="anthropic_sdk",
    ),
    # Fable 5: thinking is always on and never configurable — our client
    # already sends no `thinking` config (required; sending one 400s) and the
    # 16k MAX_TOKENS budget covers thinking + response together.
    ModelEntry(
        id="claude-fable-5",
        context_window=1_000_000,
        provider="anthropic",
        display_name="Claude Fable 5 (Anthropic)",
        role="heavy",
        notes="Anthropic's top-tier model — strongest reasoning and long-horizon work, above Opus. Paid, premium pricing.",
        client="anthropic_sdk",
    ),
    # --- OpenRouter (pay-as-you-go aggregator) ---
    # One key unlocks models from many labs; ids are vendor/model. Curated
    # picks below — re-check openrouter.ai/models when refreshing.
    ModelEntry(
        id="anthropic/claude-haiku-4.5",
        context_window=200_000,
        provider="openrouter",
        display_name="Claude Haiku 4.5 (OpenRouter)",
        role="light",
        notes="Anthropic's fast, cheap model via OpenRouter — a strong light pick.",
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
        id="google/gemini-3.6-flash",
        context_window=1_048_576,
        provider="openrouter",
        display_name="Gemini 3.6 Flash (OpenRouter)",
        role="either",
        notes="Strong Google Flash via OpenRouter (3.7 Flash has since superseded it).",
    ),
    ModelEntry(
        id="google/gemini-3.7-flash",
        context_window=1_048_576,
        provider="openrouter",
        display_name="Gemini 3.7 Flash (OpenRouter)",
        role="either",
        notes="Google's newest, strongest Flash via OpenRouter — built for agents and tool use.",
    ),
    ModelEntry(
        id="anthropic/claude-opus-5",
        context_window=1_000_000,
        provider="openrouter",
        display_name="Claude Opus 5 (OpenRouter)",
        role="heavy",
        notes="Anthropic's most capable model via OpenRouter — for the hardest drafting/reasoning.",
    ),
    ModelEntry(
        id="anthropic/claude-fable-5",
        context_window=1_000_000,
        provider="openrouter",
        display_name="Claude Fable 5 (OpenRouter)",
        role="heavy",
        notes="Anthropic's top-tier model via OpenRouter — above Opus. Premium pricing.",
    ),
    ModelEntry(
        id="moonshotai/kimi-k3",
        context_window=1_048_576,
        provider="openrouter",
        display_name="Kimi K3 (OpenRouter)",
        role="either",
        notes="Moonshot's flagship — 1M context, strong reasoning and agentic tool use.",
    ),
    ModelEntry(
        id="anthropic/claude-sonnet-5",
        context_window=1_000_000,
        provider="openrouter",
        display_name="Claude Sonnet 5 (OpenRouter)",
        role="either",
        notes="Anthropic's newest Sonnet served via OpenRouter — a strong heavy pick.",
    ),
    # Popular open-model picks via OpenRouter (live-verified 2026-08-22).
    # Removed Aug 2026: DeepSeek V3.1 + R1 (line retired upstream — the V4
    # models below are the successors), GLM 5 (two generations behind), the
    # stale un-dated deepseek/deepseek-v4-flash slug (OpenRouter kept it
    # pinned to the old April build; -0731 below is the current one), and
    # OpenRouter's gpt-5/gpt-5-mini (OpenAI shutdown 2026-12-11).
    ModelEntry(
        id="meta-llama/llama-3.3-70b-instruct",
        context_window=131_072,
        provider="openrouter",
        display_name="Llama 3.3 70B (OpenRouter)",
        role="either",
        notes="Popular open Llama — solid, low-cost all-rounder.",
    ),
    # Z.ai GLM + newer open agentic models via OpenRouter (live-verified
    # 2026-08-22 against openrouter.ai/models).
    ModelEntry(
        id="z-ai/glm-5.2",
        context_window=1_048_576,
        provider="openrouter",
        display_name="GLM 5.2 (OpenRouter)",
        role="either",
        notes="Z.ai's GLM 5.2 — 1M context, strong at coding + agentic tool use. Cheap heavy pick.",
    ),
    ModelEntry(
        id="z-ai/glm-5.3",
        context_window=1_048_576,
        provider="openrouter",
        display_name="GLM 5.3 (OpenRouter)",
        role="either",
        notes="Z.ai's newest flagship — 1M context, stronger than 5.2 on complex coding and long-horizon agent work.",
    ),
    ModelEntry(
        id="deepseek/deepseek-v4-flash-0731",
        context_window=1_310_720,
        provider="openrouter",
        display_name="DeepSeek V4 Flash (OpenRouter)",
        role="either",
        notes="Very cheap, fast MoE — 1.3M context, refreshed July 2026 build with big agentic gains. Great low-cost workhorse.",
    ),
    ModelEntry(
        id="deepseek/deepseek-v4-pro-0813",
        context_window=1_048_576,
        provider="openrouter",
        display_name="DeepSeek V4 Pro (OpenRouter)",
        role="heavy",
        notes="DeepSeek's flagship — 1M context, agent-first with strong tool use. Low-cost heavy pick.",
    ),
    ModelEntry(
        id="minimax/minimax-m3",
        context_window=1_048_576,
        provider="openrouter",
        display_name="MiniMax M3 (OpenRouter)",
        role="either",
        notes="1M context, strong coding/agentic tool use — mid-priced all-rounder.",
    ),
    ModelEntry(
        id="qwen/qwen3.8-max",
        context_window=1_000_000,
        provider="openrouter",
        display_name="Qwen3.8 Max (OpenRouter)",
        role="heavy",
        notes="Alibaba's largest flagship — 1M context, multimodal, strong reasoning.",
    ),
    ModelEntry(
        id="x-ai/grok-4.6",
        context_window=500_000,
        provider="openrouter",
        display_name="Grok 4.6 (OpenRouter)",
        role="either",
        notes="xAI's frontier model — flagship-level benchmarks at half flagship price, tuned for long agent runs.",
    ),
    ModelEntry(
        id="meta/muse-spark-1.2",
        context_window=1_048_576,
        provider="openrouter",
        display_name="Muse Spark 1.2 (OpenRouter)",
        role="either",
        notes="Meta's new closed model line — agentic and coding focus, mid-priced. Needs a one-time 18+ confirmation in your OpenRouter account settings first.",
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
