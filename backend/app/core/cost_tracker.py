"""Token usage → USD cost calculation.

Prices are per 1 million tokens. Groq rates:
  https://console.groq.com/settings/billing
Google AI Studio rates:
  https://ai.google.dev/gemini-api/docs/pricing
Confirm current rates in those dashboards before trusting production invoices.
"""
from decimal import Decimal


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
    "gpt-4o": ModelPricing("2.50", "10.00"),
    "gpt-4o-mini": ModelPricing("0.15", "0.60"),
}

_MILLION = Decimal("1000000")


def calculate_cost_usd(
    model: str, input_tokens: int, output_tokens: int
) -> Decimal:
    pricing = GROQ_PRICING.get(model)
    if pricing is None:
        return Decimal("0")
    return (
        pricing.input * Decimal(input_tokens) / _MILLION
        + pricing.output * Decimal(output_tokens) / _MILLION
    ).quantize(Decimal("0.000001"))
