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
    # sessions still display a cost. Likewise the two Llamas above: Groq shut
    # them down 2026-08-16.
    "qwen/qwen3-32b": ModelPricing("0.29", "0.59"),
    # Retired from the picker 2026-09-18: Groq dropped qwen3.6-27b from
    # /v1/models and it now hard-fails "model_not_found". Kept so old sessions
    # still display a cost. Rates below re-confirmed 2026-09-25 against the
    # per-model `pricing` block Groq's own /v1/models response carries.
    "qwen/qwen3.6-27b": ModelPricing("0.60", "3.00"),
    "qwen/qwen3.8-27b": ModelPricing("0.80", "4.00"),
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
    # ai.google.dev/gemini-api/docs/pricing 2026-09-25.
    "gemini-3.5-flash": ModelPricing("1.50", "9.00"),
    # 3.6 + 3.7 + 3.8 Flash: $0.75/$3.75 is Google's introductory rate through
    # 2026-12-31; all three revert to $1.50/$7.50 on 2027-01-01 (bump then).
    "gemini-3.6-flash": ModelPricing("0.75", "3.75"),
    "gemini-3.7-flash": ModelPricing("0.75", "3.75"),
    "gemini-3.8-flash": ModelPricing("0.75", "3.75"),
    "gemini-3.5-flash-lite": ModelPricing("0.30", "2.50"),
    "gemini-3.1-flash-lite": ModelPricing("0.25", "1.50"),
    "gemini-2.5-pro": ModelPricing("2.50", "15.00"),
    "gemini-2.5-flash": ModelPricing("0.30", "2.50"),
    "gemini-2.5-flash-lite": ModelPricing("0.10", "0.40"),

    # --- OpenAI (paid) ---
    # Original GPT-5 family: retired from the registry Aug 2026 (OpenAI
    # shutdown 2026-12-11) — entries kept so old sessions display a cost.
    "gpt-5": ModelPricing("1.25", "10.00"),
    "gpt-5-mini": ModelPricing("0.25", "2.00"),
    "gpt-5-nano": ModelPricing("0.05", "0.40"),
    "gpt-5-pro": ModelPricing("15.00", "120.00"),
    # GPT-5.4/5.5/5.6 generations per developers.openai.com/api/docs/pricing
    # (2026-09-25) — standard-tier, short-context (<=272k) rates; longer
    # inputs bill a higher tier we don't model. NOTE: OpenRouter's catalog
    # shows batch/flex rates for some 5.6 tiers — these are the native
    # standard rates, deliberately different from what OpenRouter displays.
    # The whole 5.6 family was cut Jul/Aug 2026 (Luna -80%); Sol's $4/$20 is
    # labeled promotional "at least through 2026-11-21" — re-check after.
    "gpt-5.4": ModelPricing("2.50", "15.00"),
    "gpt-5.4-mini": ModelPricing("0.75", "4.50"),
    "gpt-5.4-nano": ModelPricing("0.20", "1.25"),
    "gpt-5.5": ModelPricing("5.00", "30.00"),
    "gpt-5.6-luna": ModelPricing("0.20", "1.20"),
    "gpt-5.6-terra": ModelPricing("2.00", "12.00"),
    "gpt-5.6-sol": ModelPricing("4.00", "20.00"),
    # GPT-6 Astra, added 2026-09-11 at the official standard short-context
    # rate (developers.openai.com/api/docs/pricing). Prompts over 272k bill a
    # higher $20/$75 tier we don't model. NOTE: OpenRouter's catalog shows
    # gpt-5.6-sol at $2/$10, half the official $4/$20 above — the usual
    # OpenRouter batch-rate gotcha; the native rates here come from OpenAI.
    "gpt-6-astra": ModelPricing("10.00", "50.00"),
    # The other two GPT-6 tiers, added 2026-09-25 at OpenAI's official standard
    # short-context rates. Long-context (>272k) tiers we don't model: Luna
    # $0.20/$0.75, Sol $4/$15. Both rates happen to match what OpenRouter
    # shows for the non-batch slug, but they were taken from OpenAI's page.
    "gpt-6-luna": ModelPricing("0.10", "0.50"),
    "gpt-6-sol": ModelPricing("2.00", "10.00"),
    # GPT-6.1 Sol (2026-09-29) at OpenAI's official standard short-context rate
    # — identical to GPT-6 Sol's, so 6.1 is a free upgrade. Long-context
    # (>272k) tier not modeled, same as its siblings.
    "gpt-6.1-sol": ModelPricing("2.00", "10.00"),
    # Legacy (kept so old sessions still display a cost):
    "gpt-4o": ModelPricing("2.50", "10.00"),
    "gpt-4o-mini": ModelPricing("0.15", "0.60"),

    # --- Anthropic (paid) ---
    # Per platform.claude.com pricing, re-confirmed 2026-09-25.
    "claude-haiku-4-5": ModelPricing("1.00", "5.00"),
    # $2/$10 launched as an intro price, made PERMANENT Aug 2026 (the planned
    # 2026-09-01 rise to $3/$15 was cancelled — platform.claude.com pricing).
    "claude-sonnet-5": ModelPricing("2.00", "10.00"),
    # Sonnet 5.5 (2026-09-28) launched at Sonnet 5's exact $2/$10 standard rate
    # (platform.claude.com, 2026-10-02) — it differs only in cache-read rate,
    # which this tracker doesn't model.
    "claude-sonnet-5-5": ModelPricing("2.00", "10.00"),
    # Retired from the picker (superseded by Sonnet 5) but kept so older
    # sessions that used it still display a cost.
    "claude-sonnet-4-6": ModelPricing("3.00", "15.00"),
    "claude-opus-4-8": ModelPricing("5.00", "25.00"),
    # Opus 5 launched at the same rates as Opus 4.8 (platform.claude.com).
    "claude-opus-5": ModelPricing("5.00", "25.00"),
    # Opus 5.5 (2026-09-21) is the first Opus to come in UNDER its predecessor:
    # $4/$20 standard, not promotional (platform.claude.com, 2026-09-25).
    "claude-opus-5-5": ModelPricing("4.00", "20.00"),
    # Fable 5 — Anthropic's premium tier above Opus (platform.claude.com,
    # 2026-07-29). Fable 5.1 launched at the same $10/$50 (2026-09-01); it
    # differs only in cache-read rate, which this tracker doesn't model.
    "claude-fable-5": ModelPricing("10.00", "50.00"),
    "claude-fable-5-1": ModelPricing("10.00", "50.00"),

    # --- OpenRouter (mirrors the underlying labs' rates; OpenRouter adds a
    # small fee on credits, not per-token — close enough for display) ---
    # Rates re-verified against openrouter.ai/api/v1/models, 2026-09-25.
    # NOTE for open models: OpenRouter lists many resellers per model at very
    # different rates, and the catalog's headline rate follows whichever
    # endpoint it currently defaults to — so these move between refreshes
    # without the lab changing anything. Recorded at the headline rate, which
    # is what a user routing through OpenRouter normally pays.
    "openai/gpt-5-mini": ModelPricing("0.25", "2.00"),
    "anthropic/claude-haiku-4.5": ModelPricing("1.00", "5.00"),
    "google/gemini-3.5-flash": ModelPricing("1.50", "9.00"),
    "google/gemini-3.6-flash": ModelPricing("0.75", "3.75"),
    # 3.7 + 3.8 Flash at Google's native standard rate — OpenRouter lists a
    # separate ":batch" slug at half these rates, the known OpenRouter gotcha.
    "google/gemini-3.7-flash": ModelPricing("0.75", "3.75"),
    "google/gemini-3.8-flash": ModelPricing("0.75", "3.75"),
    "anthropic/claude-opus-5": ModelPricing("5.00", "25.00"),
    # Opus 5.5 at Anthropic's official $4/$20 — OpenRouter's catalog agrees
    # here; its ":batch" slug is the half-price $2/$10 one.
    "anthropic/claude-opus-5.5": ModelPricing("4.00", "20.00"),
    "anthropic/claude-fable-5": ModelPricing("10.00", "50.00"),
    # Fable 5.1 at Anthropic's official $10/$50 (the ":batch" slug is $5/$25).
    "anthropic/claude-fable-5.1": ModelPricing("10.00", "50.00"),
    # GPT-6 Astra via OpenRouter — its catalog rate matches OpenAI's official
    # standard rate here, so no batch-rate discrepancy to correct. Same for
    # the Luna and Sol twins added 2026-09-25 (both taken from OpenAI's page;
    # their ":batch" slugs are the usual half-price ones).
    "openai/gpt-6-astra": ModelPricing("10.00", "50.00"),
    "openai/gpt-6-luna": ModelPricing("0.10", "0.50"),
    "openai/gpt-6-sol": ModelPricing("2.00", "10.00"),
    # GPT-6.1 Sol twin at OpenAI's official $2/$10 (OpenRouter's catalog agrees;
    # the ":batch" slug is the usual half-price one).
    "openai/gpt-6.1-sol": ModelPricing("2.00", "10.00"),
    # Kimi K3 keeps oscillating with OpenRouter's default endpoint ($3/$15 →
    # $2.34/$11.70 → $2.10/$10.95 → $3/$15 → now $2.70/$13.50, a 10% cut).
    "moonshotai/kimi-k3": ModelPricing("2.70", "13.50"),
    # $2/$10 made permanent Aug 2026 (matches the native entry above).
    "anthropic/claude-sonnet-5": ModelPricing("2.00", "10.00"),
    # Sonnet 5.5 twin at Anthropic's official $2/$10 (the ":batch" slug is $1/$5).
    "anthropic/claude-sonnet-5.5": ModelPricing("2.00", "10.00"),
    # Retired from the picker (superseded by Sonnet 5) but kept for old sessions.
    "anthropic/claude-sonnet-4.6": ModelPricing("3.00", "15.00"),
    "openai/gpt-5": ModelPricing("1.25", "10.00"),
    # DeepSeek V3.1/R1 + GLM 5 + the un-dated V4 Flash slug: retired from the
    # picker Aug 2026, kept for old sessions (rates as last seen).
    "deepseek/deepseek-chat-v3.1": ModelPricing("0.55", "1.65"),
    "deepseek/deepseek-r1": ModelPricing("0.70", "2.50"),
    "deepseek/deepseek-v4-flash": ModelPricing("0.06", "0.12"),
    "z-ai/glm-5": ModelPricing("0.60", "1.92"),
    # Llama 3.3 70B: the headline endpoint moved to a much cheaper reseller
    # between the Aug and Sep refreshes (was $0.71/$0.71).
    "meta-llama/llama-3.3-70b-instruct": ModelPricing("0.10", "0.32"),
    # Current open-model picks (rates per the openrouter.ai catalog,
    # 2026-09-25). MiniMax M3's $0.30/$1.20 is a promotional rate (regular
    # $0.60/$2.40); free-tier-style discounts just display a lower cost.
    # GLM 5.2's headline endpoint changed shape again (was $0.6496/$2.0416):
    # input down ~37%, output nearly doubled. Reseller churn, as above.
    "z-ai/glm-5.2": ModelPricing("0.41", "3.99"),
    "z-ai/glm-5.3": ModelPricing("1.40", "4.40"),
    # GLM 5.3 Flash's headline endpoint jumped back up to $0.15/$0.50 (was
    # $0.045/$0.14) — roughly where it sat before the September dip. Still the
    # cheapest capable pick on the OpenRouter list after GPT-6 Luna.
    "z-ai/glm-5.3-flash": ModelPricing("0.15", "0.50"),
    # V4 Flash's headline endpoint keeps diverging: input is now almost free at
    # $0.0077 (was $0.03) while output quadrupled to $1.28 (was $0.32). Cheap
    # for long-context reading, no longer cheap for long answers.
    "deepseek/deepseek-v4-flash-0731": ModelPricing("0.0077", "1.28"),
    # DeepSeek bills these two on a UTC clock: the rate below is the headline
    # (off-peak) one OpenRouter reports, and peak hours cost roughly double —
    # V4 Pro $1.32/$3.96 (00:00-14:00 UTC), V4.1 Flash $0.30/$1.20
    # (01:00-04:00 and 06:00-10:00 UTC, weekdays). Recorded at the headline
    # rate per the note above; a peak turn displays under its true cost.
    # V4 Pro's off-peak rate went back up to $0.66/$1.98 (was $0.3485/$1.0454),
    # and V4.1 Flash doubled to $0.30/$1.20 (was $0.15/$0.60).
    "deepseek/deepseek-v4-pro-0813": ModelPricing("0.66", "1.98"),
    "deepseek/deepseek-v4.1-flash": ModelPricing("0.30", "1.20"),
    "minimax/minimax-m3": ModelPricing("0.30", "1.20"),
    # Retired from the picker 2026-09-11 (OpenRouter de-listed the un-dated
    # slug); kept so old sessions still display a cost.
    "qwen/qwen3.8-max": ModelPricing("2.00", "6.00"),
    "qwen/qwen3.8-max-0902": ModelPricing("2.00", "6.00"),
    "qwen/qwen3.8-flash": ModelPricing("0.15", "0.47"),
    "x-ai/grok-4.6": ModelPricing("2.00", "6.00"),
    # Grok 4.7's 20% launch discount is over — OpenRouter now lists it at
    # $2/$6, level with Grok 4.6. Combined with its much larger hidden system
    # prompt (see the registry note), short turns now cost MORE than on 4.6.
    "x-ai/grok-4.7": ModelPricing("2.00", "6.00"),
    "meta/muse-spark-1.2": ModelPricing("1.25", "4.25"),

    # --- Mistral (per mistral.ai/pricing/api, 2026-09-25 — free tier is $0.
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
