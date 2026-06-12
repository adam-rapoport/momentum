"""Thin configuration shim pointing the shared OpenAI-compat streaming
implementation (app.core.openai_compat) at Mistral.

Mistral serves the OpenAI Chat Completions API at https://api.mistral.ai/v1.
"""
from collections.abc import AsyncIterator

from openai import AsyncOpenAI

from app.config import settings
from app.core.llm_types import StreamChunk, StreamResult
from app.core.openai_compat import stream_chat

MISTRAL_BASE_URL = "https://api.mistral.ai/v1"

# Cached per key — same convention as the other provider shims.
_clients: dict[str, AsyncOpenAI] = {}


def get_client(api_key: str | None = None) -> AsyncOpenAI:
    key = api_key or settings.mistral_api_key
    if not key:
        raise RuntimeError(
            "MISTRAL_API_KEY is not configured — set it in .env or connect "
            "Mistral in Settings to route turns to Mistral models."
        )
    client = _clients.get(key)
    if client is None:
        client = AsyncOpenAI(api_key=key, base_url=MISTRAL_BASE_URL)
        _clients[key] = client
    return client


async def stream_message(
    messages: list[dict],
    model: str,
    tools: list[dict] | None = None,
    api_key: str | None = None,
) -> AsyncIterator[StreamChunk | StreamResult]:
    """Stream a chat completion from Mistral. Same contract as
    `groq_client.stream_message`."""
    async for event in stream_chat(
        get_client(api_key), messages, model=model, tools=tools
    ):
        yield event
