"""Thin configuration shim pointing the shared OpenAI-compat streaming
implementation (app.core.openai_compat) at OpenAI itself.

Unlike `groq_client` and `google_client` (which aim the `openai` SDK at a
different provider's base URL), this talks to OpenAI's own API at
https://api.openai.com/v1 with the user's OpenAI key. Same streaming
contract as the other providers so `app.core.llm` can dispatch to it
transparently. Paid provider — the key needs billing enabled.
"""
from __future__ import annotations

from collections.abc import AsyncIterator

from openai import AsyncOpenAI

from app.config import settings
from app.core.llm_types import StreamChunk, StreamResult
from app.core.openai_compat import stream_chat

# Clients are cached by API key so per-user keys (from the Connections UI)
# each get their own reused client.
_clients: dict[str, AsyncOpenAI] = {}


def get_client(api_key: str | None = None) -> AsyncOpenAI:
    key = api_key or settings.openai_api_key
    if not key:
        raise RuntimeError(
            "OPENAI_API_KEY is not configured — set it in .env or connect "
            "OpenAI in Settings to route turns to OpenAI models."
        )
    client = _clients.get(key)
    if client is None:
        client = AsyncOpenAI(api_key=key)
        _clients[key] = client
    return client


async def stream_message(
    messages: list[dict],
    model: str,
    tools: list[dict] | None = None,
    api_key: str | None = None,
) -> AsyncIterator[StreamChunk | StreamResult]:
    """Stream a chat completion from OpenAI. Same contract as
    `groq_client.stream_message` — see openai_compat.stream_chat.
    """
    async for event in stream_chat(
        get_client(api_key), messages, model=model, tools=tools
    ):
        yield event
