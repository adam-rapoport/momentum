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
    "qwen/qwen3-32b": ModelPricing("0.29", "0.59"),
    "qwen/qwen3.6-27b": ModelPricing("0.29", "0.59"),
    "openai/gpt-oss-120b": ModelPricing("0.15", "0.75"),
    "openai/gpt-oss-20b": ModelPricing("0.10", "0.50"),

    # --- Google AI Studio ---
    # Sprint 4 "heavy" model. Free-tier is $0/$0; paid is $0.50/$3.00.
    "gemini-3-flash-preview": ModelPricing("0.50", "3.00"),
    # Gemma 4 — open-weights, free-tier only (no paid tier), so $0/$0.
    "gemma-4-31b-it": ModelPricing("0", "0"),
    "gemma-4-26b-a4b-it": ModelPricing("0", "0"),
    # Other plausible heavy-slot alternates; pricing is the paid-tier rate,
    # free-tier usage simply evaluates to $0 per the Google docs.
    "gemini-3.1-pro-preview": ModelPricing("4.00", "18.00"),
    "gemini-3.1-pro-preview-customtools": ModelPricing("4.00", "18.00"),
    # Current Gemini 3.x flash tier (paid rates; free-tier usage is $0). The
    # exact 3.5/3.1-lite rates weren't published at time of writing, so these
    # mirror the equivalent 2.5 flash tiers as a close estimate for display.
    "gemini-3.5-flash": ModelPricing("0.30", "2.50"),
    "gemini-3.1-flash-lite": ModelPricing("0.10", "0.40"),
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
    # Legacy (kept so old sessions still display a cost):
    "gpt-4o": ModelPricing("2.50", "10.00"),
    "gpt-4o-mini": ModelPricing("0.15", "0.60"),

    # --- Anthropic (paid) ---
    # Per platform.claude.com pricing, 2026-06.
    "claude-haiku-4-5": ModelPricing("1.00", "5.00"),
    "claude-sonnet-4-6": ModelPricing("3.00", "15.00"),
    "claude-opus-4-8": ModelPricing("5.00", "25.00"),

    # --- OpenRouter (mirrors the underlying labs' rates; OpenRouter adds a
    # small fee on credits, not per-token — close enough for display) ---
    "openai/gpt-5-mini": ModelPricing("0.25", "2.00"),
    "anthropic/claude-haiku-4.5": ModelPricing("1.00", "5.00"),
    "google/gemini-3.5-flash": ModelPricing("0.30", "2.50"),
    "anthropic/claude-sonnet-4.6": ModelPricing("3.00", "15.00"),
    "openai/gpt-5": ModelPricing("1.25", "10.00"),
    "deepseek/deepseek-chat-v3.1": ModelPricing("0.21", "0.79"),
    "deepseek/deepseek-r1": ModelPricing("0.70", "2.50"),
    "meta-llama/llama-3.3-70b-instruct": ModelPricing("0.10", "0.32"),

    # --- Mistral (per mistral.ai pricing; estimates — free tier is $0) ---
    "mistral-small-latest": ModelPricing("0.10", "0.30"),
    "mistral-medium-latest": ModelPricing("0.40", "2.00"),
    "mistral-large-latest": ModelPricing("2.00", "6.00"),
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
