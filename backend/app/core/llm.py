"""Provider dispatch for chat-completion streaming.

Picks the right client based on the model ID prefix:
  - `gemini-*` or `gemma-*` -> Google AI Studio (OpenAI-compat endpoint)
  - Everything else          -> Groq (our default provider)

Session engine imports `stream_message` from here instead of from any
specific provider module, so routing decisions stay in one place.
"""
from __future__ import annotations

from collections.abc import AsyncIterator

from app.core import google_client, groq_client
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
    if is_google_model(model):
        async for event in google_client.stream_message(
            messages, model=model, tools=tools, api_key=api_key
        ):
            yield event
        return
    async for event in groq_client.stream_message(
        messages, model=model, tools=tools, api_key=api_key
    ):
        yield event
