"""Provider dispatch for chat-completion streaming.

Routing is driven by the model registry (app.core.model_registry):
  - provider "google" + client "genai_sdk" -> native google-genai SDK
  - provider "google" (default client)      -> Google OpenAI-compat endpoint
  - provider "openai"                        -> OpenAI (api.openai.com)
  - provider "groq"                          -> Groq (our default provider)

When a model isn't in the registry (e.g. a raw env-var override), we fall
back to the original name-prefix rule: `gemini-*`/`gemma-*` -> Google
OpenAI-compat, everything else -> Groq.

Session engine imports `stream_message` from here instead of from any
specific provider module, so routing decisions stay in one place.
"""
from __future__ import annotations

from collections.abc import AsyncIterator

from app.core import (
    google_client,
    google_genai_client,
    groq_client,
    model_registry,
    openai_client,
)
from app.core.groq_client import StreamChunk, StreamResult

_GOOGLE_PREFIXES = ("gemini-", "gemma-")


def is_google_model(model: str) -> bool:
    return model.startswith(_GOOGLE_PREFIXES)


async def stream_message(
    messages: list[dict],
    model: str,
    tools: list[dict] | None = None,
    api_key: str | None = None,
) -> AsyncIterator[StreamChunk | StreamResult]:
    """Dispatch to the right provider client. `api_key`, when provided, is the
    user's stored key for that provider (resolved by app.core.credentials);
    None means use the env-var default."""
    entry = model_registry.get_model(model)
    if entry is not None:
        if entry.provider == "google":
            client = (
                google_genai_client
                if entry.client == "genai_sdk"
                else google_client
            )
        elif entry.provider == "openai":
            client = openai_client
        else:
            client = groq_client
        async for event in client.stream_message(
            messages, model=model, tools=tools, api_key=api_key
        ):
            yield event
        return

    # Unknown model (raw env override): fall back to the prefix rule.
    fallback = google_client if is_google_model(model) else groq_client
    async for event in fallback.stream_message(
        messages, model=model, tools=tools, api_key=api_key
    ):
        yield event
