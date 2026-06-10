"""Thin configuration shim pointing the shared OpenAI-compat streaming
implementation (app.core.openai_compat) at Groq.

Groq serves the OpenAI Chat Completions API at https://api.groq.com/openai/v1.
Using the official `openai` SDK with a custom `base_url` is the documented path.
The streaming dataclasses live in `app.core.llm_types`.
"""
from collections.abc import AsyncIterator

from openai import AsyncOpenAI

from app.config import settings
from app.core.llm_types import StreamChunk, StreamResult
from app.core.openai_compat import stream_chat

# Clients are cached by API key so that per-user keys (from the Connections
# UI / C8) each get their own reused client. When `api_key` is None we fall
# back to the env default — that path is byte-for-byte the old behavior.
_clients: dict[str, AsyncOpenAI] = {}


def get_client(api_key: str | None = None) -> AsyncOpenAI:
    key = api_key or settings.groq_api_key
    if not key:
        # Mirror openai_client / google_client: a clear, correct message instead
        # of AsyncOpenAI(api_key=None) raising about the wrong (OPENAI) env var.
        raise RuntimeError(
            "GROQ_API_KEY is not configured — set it in .env or connect "
            "Groq in Settings to route turns to Groq models."
        )
    client = _clients.get(key)
    if client is None:
        client = AsyncOpenAI(api_key=key, base_url=settings.groq_base_url)
        _clients[key] = client
    return client


async def stream_message(
    messages: list[dict],
    model: str | None = None,
    tools: list[dict] | None = None,
    api_key: str | None = None,
) -> AsyncIterator[StreamChunk | StreamResult]:
    """Stream a chat completion from Groq. Yields StreamChunks for each text
    delta, then a final StreamResult — see openai_compat.stream_chat.
    """
    model = model or settings.groq_model
    async for event in stream_chat(
        get_client(api_key), messages, model=model, tools=tools
    ):
        yield event
