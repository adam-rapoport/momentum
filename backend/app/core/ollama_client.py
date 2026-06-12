"""Thin configuration shim pointing the shared OpenAI-compat streaming
implementation (app.core.openai_compat) at a local Ollama server.

Ollama serves the OpenAI Chat Completions API at {base_url}/v1 with no
authentication. The "credential" resolved by app.core.credentials for
"llm:ollama" IS the base URL (e.g. http://localhost:11434), so it arrives
here through the same `api_key` parameter every other client uses.

Model ids carry an "ollama:" prefix app-side (e.g. "ollama:llama3.1:8b") so
provider resolution works without a network call; the prefix is stripped
before the wire call.
"""
from collections.abc import AsyncIterator

from openai import AsyncOpenAI

from app.config import settings
from app.core.llm_types import StreamChunk, StreamResult
from app.core.openai_compat import stream_chat

MODEL_PREFIX = "ollama:"

# Cached per base URL — same convention as the per-key caches elsewhere.
_clients: dict[str, AsyncOpenAI] = {}


def strip_prefix(model: str) -> str:
    return model[len(MODEL_PREFIX):] if model.startswith(MODEL_PREFIX) else model


def get_client(base_url: str | None = None) -> AsyncOpenAI:
    base = base_url or settings.ollama_base_url
    if not base:
        raise RuntimeError(
            "Ollama is not connected — add your Ollama server URL in "
            "Settings → Models (or set OLLAMA_BASE_URL) to use local models."
        )
    base = base.rstrip("/")
    client = _clients.get(base)
    if client is None:
        # Ollama ignores the API key but the SDK requires a non-empty one.
        client = AsyncOpenAI(api_key="ollama", base_url=f"{base}/v1")
        _clients[base] = client
    return client


async def stream_message(
    messages: list[dict],
    model: str,
    tools: list[dict] | None = None,
    api_key: str | None = None,
) -> AsyncIterator[StreamChunk | StreamResult]:
    """Stream a chat completion from Ollama. `api_key` carries the resolved
    base URL (see module docstring). Same contract as the other clients."""
    async for event in stream_chat(
        get_client(api_key), messages, model=strip_prefix(model), tools=tools
    ):
        yield event
