"""Token usage → USD cost calculation.

Prices are per 1 million tokens. Groq rates:
  https://console.groq.com/settings/billing
Google AI Studio rates:
  https://ai.google.dev/gemini-api/docs/pricing
Confirm current rates in those dashboards before trusting production invoices.

Every model in app.core.model_registry MUST have an entry here (enforced by
tests/test_cost_tracker.py). Extra entries are fine — they cover retired
registry models still named in old sessions and raw env-override ids.
"""
import logging
from decimal import Decimal

logger = logging.getLogger(__name__)


class ModelPricing:
    def __init__(self, input_per_mtok: str, output_per_mtok: str) -> None:
        self.input = Decimal(input_per_mtok)
        self.output = Decimal(output_per_mtok)


# Named GROQ_PRICING for historical reasons; now covers every provider
# we route to. Keyed by the same model ID the LLM client sends on the wire.
GROQ_PRICING: dict[str, ModelPricing] = {
    # --- Groq-hosted ---
    "llama-3.3-70b-versatile": ModelPricing("0.59", "0.79"),
    "llama-3.1-70b-versatile": ModelPricing("0.59", "0.79"),
    "llama-3.1-8b-instant": ModelPricing("0.05", "0.08"),
    # Llama 4 Scout is our Sprint 2 default after the model hedge.
    "meta-llama/llama-4-scout-17b-16e-instruct": ModelPricing("0.11", "0.34"),
    # Retired upstream (gone from Groq /v1/models by 2026-07-24); kept so old
    # sessions still display a cost.
    "qwen/qwen3-32b": ModelPricing("0.29", "0.59"),
    # Rates below per groq.com/pricing, 2026-07-24.
    "qwen/qwen3.6-27b": ModelPricing("0.60", "3.00"),
    "openai/gpt-oss-120b": ModelPricing("0.15", "0.60"),
    "openai/gpt-oss-20b": ModelPricing("0.075", "0.30"),

    # --- Google AI Studio ---
    # Sprint 4 "heavy" model. Free-tier is $0/$0; paid is $0.50/$3.00.
    "gemini-3-flash-preview": ModelPricing("0.50", "3.00"),
    # Gemma 4 — open-weights, free-tier only (no paid tier), so $0/$0.
    "gemma-4-31b-it": ModelPricing("0", "0"),
    "gemma-4-26b-a4b-it": ModelPricing("0", "0"),
    # Other plausible heavy-slot alternates; pricing is the paid-tier rate,
    # free-tier usage simply evaluates to $0 per the Google docs.
    # Base ≤200k-token rate; >200k-token turns bill tiered $4.00/$18.00.
    "gemini-3.1-pro-preview": ModelPricing("2.00", "12.00"),
    "gemini-3.1-pro-preview-customtools": ModelPricing("2.00", "12.00"),
    # Current Gemini 3.x flash tier (paid rates; free-tier usage is $0), per
    # ai.google.dev/gemini-api/docs/pricing 2026-07-24 — the June values were
    # estimates recorded before Google published real 3.5/3.1-lite rates.
    "gemini-3.5-flash": ModelPricing("1.50", "9.00"),
    # Gemini 3.6 Flash per ai.google.dev/gemini-api/docs/pricing (2026-07-24);
    # free-tier usage is $0.
    "gemini-3.6-flash": ModelPricing("1.50", "7.50"),
    "gemini-3.1-flash-lite": ModelPricing("0.25", "1.50"),
    "gemini-2.5-pro": ModelPricing("2.50", "15.00"),
    "gemini-2.5-flash": ModelPricing("0.30", "2.50"),
    "gemini-2.5-flash-lite": ModelPricing("0.10", "0.40"),

    # --- OpenAI (paid) ---
    # GPT-5 family per OpenAI's published pricing; ids verified against a live
    # key (2026-06-21). gpt-5-pro is the premium reasoning tier.
    "gpt-5": ModelPricing("1.25", "10.00"),
    "gpt-5-mini": ModelPricing("0.25", "2.00"),
    "gpt-5-nano": ModelPricing("0.05", "0.40"),
    "gpt-5-pro": ModelPricing("15.00", "120.00"),
    # GPT-5.4/5.5/5.6 generations per developers.openai.com/api/docs/pricing
    # (2026-07-29) — standard-tier, short-context (<=272k) rates; longer
    # inputs bill a higher tier we don't model. NOTE: OpenRouter's catalog
    # shows batch/flex rates for some 5.6 tiers — these are the native
    # standard rates, deliberately different from what OpenRouter displays.
    "gpt-5.4": ModelPricing("2.50", "15.00"),
    "gpt-5.4-mini": ModelPricing("0.75", "4.50"),
    "gpt-5.4-nano": ModelPricing("0.20", "1.25"),
    "gpt-5.5": ModelPricing("5.00", "30.00"),
    "gpt-5.6-luna": ModelPricing("1.00", "6.00"),
    "gpt-5.6-terra": ModelPricing("2.50", "15.00"),
    "gpt-5.6-sol": ModelPricing("5.00", "30.00"),
    # Legacy (kept so old sessions still display a cost):
    "gpt-4o": ModelPricing("2.50", "10.00"),
    "gpt-4o-mini": ModelPricing("0.15", "0.60"),

    # --- Anthropic (paid) ---
    # Per platform.claude.com pricing, 2026-06.
    "claude-haiku-4-5": ModelPricing("1.00", "5.00"),
    # Standard sticker price ($2/$10 intro discount runs through 2026-08-31).
    "claude-sonnet-5": ModelPricing("3.00", "15.00"),
    # Retired from the picker (superseded by Sonnet 5) but kept so older
    # sessions that used it still display a cost.
    "claude-sonnet-4-6": ModelPricing("3.00", "15.00"),
    "claude-opus-4-8": ModelPricing("5.00", "25.00"),
    # Opus 5 launched at the same rates as Opus 4.8 (platform.claude.com).
    "claude-opus-5": ModelPricing("5.00", "25.00"),
    # Fable 5 — Anthropic's premium tier above Opus (platform.claude.com,
    # 2026-07-29).
    "claude-fable-5": ModelPricing("10.00", "50.00"),

    # --- OpenRouter (mirrors the underlying labs' rates; OpenRouter adds a
    # small fee on credits, not per-token — close enough for display) ---
    # Rates re-verified against openrouter.ai/api/v1/models, 2026-07-24.
    "openai/gpt-5-mini": ModelPricing("0.25", "2.00"),
    "anthropic/claude-haiku-4.5": ModelPricing("1.00", "5.00"),
    "google/gemini-3.5-flash": ModelPricing("1.50", "9.00"),
    "google/gemini-3.6-flash": ModelPricing("1.50", "7.50"),
    "anthropic/claude-opus-5": ModelPricing("5.00", "25.00"),
    "anthropic/claude-fable-5": ModelPricing("10.00", "50.00"),
    # Kimi K3 per the openrouter.ai catalog, 2026-07-29.
    "moonshotai/kimi-k3": ModelPricing("3.00", "15.00"),
    # Sticker price — OpenRouter currently passes through Anthropic's $2/$10
    # intro discount (through 2026-08-31); recorded at sticker to match the
    # native claude-sonnet-5 entry above.
    "anthropic/claude-sonnet-5": ModelPricing("3.00", "15.00"),
    # Retired from the picker (superseded by Sonnet 5) but kept for old sessions.
    "anthropic/claude-sonnet-4.6": ModelPricing("3.00", "15.00"),
    "openai/gpt-5": ModelPricing("1.25", "10.00"),
    "deepseek/deepseek-chat-v3.1": ModelPricing("0.25", "0.95"),
    "deepseek/deepseek-r1": ModelPricing("0.70", "2.50"),
    "deepseek/deepseek-v4-flash": ModelPricing("0.094", "0.188"),
    "meta-llama/llama-3.3-70b-instruct": ModelPricing("0.13", "0.40"),
    # Z.ai GLM + MiniMax via OpenRouter (rates per the openrouter.ai catalog,
    # 2026-07-24). MiniMax M3's $0.30/$1.20 is a promotional rate (regular
    # $0.60/$2.40); free-tier-style discounts just display a lower cost.
    "z-ai/glm-5.2": ModelPricing("0.77", "2.41"),
    "z-ai/glm-5": ModelPricing("0.95", "2.55"),
    "minimax/minimax-m3": ModelPricing("0.30", "1.20"),

    # --- Mistral (per mistral.ai/pricing/api, 2026-07-24 — free tier is $0.
    # Large 3 really is priced below Medium 3.5 now: Medium 3.5 is Mistral's
    # newer, stronger flagship) ---
    "mistral-small-latest": ModelPricing("0.15", "0.60"),
    "mistral-medium-latest": ModelPricing("1.50", "7.50"),
    "mistral-large-latest": ModelPricing("0.50", "1.50"),
}

_MILLION = Decimal("1000000")

# Models we've already complained about — log once per process, not per turn
# (finding A21: unknown models used to be a SILENT $0).
_warned_unknown_models: set[str] = set()


def calculate_cost_usd(
    model: str, input_tokens: int, output_tokens: int
) -> Decimal:
    # Local Ollama models are free — and dynamic, so they can never have a
    # pricing entry; skip the unknown-model warning for them.
    if model.startswith("ollama:"):
        return Decimal("0")
    pricing = GROQ_PRICING.get(model)
    if pricing is None:
        if model not in _warned_unknown_models:
            _warned_unknown_models.add(model)
            logger.warning(
                "no pricing entry for model %s — its usage will be recorded "
                "as $0; add it to cost_tracker.GROQ_PRICING", model,
            )
        return Decimal("0")
    return (
        pricing.input * Decimal(input_tokens) / _MILLION
        + pricing.output * Decimal(output_tokens) / _MILLION
    ).quantize(Decimal("0.000001"))
