from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = Field(..., alias="DATABASE_URL")
    redis_url: str = Field(..., alias="REDIS_URL")

    groq_api_key: str = Field(..., alias="GROQ_API_KEY")
    groq_model: str = Field(
        "meta-llama/llama-4-scout-17b-16e-instruct", alias="GROQ_MODEL"
    )
    # "Heavy" model used for drafting turns (see app.core.model_router).
    # Name kept as `groq_heavy_model` for compatibility; the value can now
    # be ANY provider's model ID (Groq, Google, ...). Provider is inferred
    # from the model-name prefix by app.core.llm.
    # Sprint 4 sequence: Groq free-tier heavy models all hit per-model TPM
    # ceilings on our ~9k token drafting prompt. Gemini 3 Flash Preview
    # works for single turns but Gemini 3 preview models require a
    # `thought_signature` on tool-call history that the OpenAI-compat
    # endpoint doesn't surface — breaks on the second turn of any
    # tool-using skill workflow. Landed on gemini-2.5-flash: stable (not
    # preview), no thought_signature requirement, still a real quality
    # step up over Scout for drafting.
    # Upgrade path for later:
    # - gemini-2.5-pro (stable, stronger writing, free tier)
    # - gemini-3.x models (would need native Gen AI SDK, ~1 day of work
    #   to replace the OpenAI-compat client — see chunk writeup)
    # Env var alias stays GROQ_HEAVY_MODEL to avoid breaking existing .env
    # files; rename on next sprint if we keep accumulating providers.
    groq_heavy_model: str = Field(
        "gemma-4-31b-it", alias="GROQ_HEAVY_MODEL"
    )
    groq_base_url: str = Field("https://api.groq.com/openai/v1", alias="GROQ_BASE_URL")

    app_env: str = Field("development", alias="APP_ENV")
    frontend_origin: str = Field("http://localhost:3000", alias="FRONTEND_ORIGIN")

    user_timezone: str = Field("America/Los_Angeles", alias="USER_TIMEZONE")
    tavily_api_key: str | None = Field(None, alias="TAVILY_API_KEY")
    memory_root: str = Field("pmomentum/data/memory", alias="MEMORY_ROOT")

    # Google Docs integration (Sprint 3 Chunk D). All optional — if any of
    # these are missing, the `/integrations/google/connect` endpoint returns
    # a clear "not configured" error rather than crashing at startup.
    google_client_id: str | None = Field(None, alias="GOOGLE_CLIENT_ID")
    google_client_secret: str | None = Field(None, alias="GOOGLE_CLIENT_SECRET")
    google_redirect_uri: str = Field(
        "http://localhost:8000/api/v1/integrations/google/callback",
        alias="GOOGLE_REDIRECT_URI",
    )

    # Fernet key for encrypting OAuth tokens at rest. Must be a urlsafe
    # base64-encoded 32-byte key (generate with
    # `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`).
    # Optional at startup — only required when we actually encrypt/decrypt.
    credential_vault_key: str | None = Field(None, alias="CREDENTIAL_VAULT_KEY")

    # Google AI Studio (Gemini / Gemma) API key. Optional at startup — only
    # required if the model router sends a turn to a Google-hosted model.
    google_ai_api_key: str | None = Field(None, alias="GOOGLE_AI_API_KEY")

    # Perplexity API key for the WebSearch tool's Perplexity provider option
    # (alternative to Tavily). Optional — only required if the user picks
    # Perplexity as their search provider (see app.core.search).
    perplexity_api_key: str | None = Field(None, alias="PERPLEXITY_API_KEY")


settings = Settings()
