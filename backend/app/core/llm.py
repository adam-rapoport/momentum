"""Provider dispatch for chat-completion streaming.

Routing is driven by the model registry (app.core.model_registry):
  - provider "google" + client "genai_sdk" -> native google-genai SDK
  - provider "google" (default client)      -> Google OpenAI-compat endpoint
  - provider "openai"                        -> OpenAI (api.openai.com)
  - provider "groq"                          -> Groq (our default provider)

When a model isn't in the registry (e.g. a raw env-var override), the
registry's name-prefix heuristics decide (`model_registry.infer_provider`):
`gemini-*`/`gemma-*` -> Google OpenAI-compat, `gpt-*`/`o1-*`/... -> OpenAI,
everything else -> Groq.

Session engine imports `stream_message` from here instead of from any
specific provider module, so routing decisions stay in one place.

Phase 1 (finding A15): `stream_message` also retries transient provider
failures (429 / 5xx / connection errors) with a short backoff — but ONLY
when the stream hasn't yielded anything yet. A partial stream cannot be
retried safely: the caller has already surfaced text to the user and
re-running the request would duplicate it.
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator

import openai

from app.core import (
    google_client,
    google_genai_client,
    groq_client,
    model_registry,
    openai_client,
)
from app.core.llm_types import StreamChunk, StreamResult

try:  # google-genai is in the default install, but stay import-safe anyway
    from google.genai import errors as genai_errors
except ImportError:  # pragma: no cover
    genai_errors = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

# Backoff schedule for transient failures: two retries, ~1s then ~3s.
# Module-level so tests can shrink it.
RETRY_DELAYS: tuple[float, ...] = (1.0, 3.0)


def _is_transient_error(e: BaseException) -> bool:
    """Worth a retry? 429s, 5xx, and connection-level failures — across the
    OpenAI SDK (serves Groq, OpenAI, and Google's compat endpoint) and the
    native google-genai SDK. Auth and 4xx request errors are NOT transient."""
    if isinstance(e, (openai.APIConnectionError, openai.RateLimitError)):
        return True
    if isinstance(e, openai.APIStatusError) and e.status_code >= 500:
        return True
    if genai_errors is not None and isinstance(e, genai_errors.APIError):
        code = e.code or 0
        return code == 429 or code >= 500
    return False


async def _dispatch(
    messages: list[dict],
    model: str,
    tools: list[dict] | None = None,
    api_key: str | None = None,
) -> AsyncIterator[StreamChunk | StreamResult]:
    """Route to the right provider client. `api_key`, when provided, is the
    user's stored key for that provider (resolved by app.core.credentials);
    None means use the env-var default."""
    entry = model_registry.get_model(model)
    if entry is not None and entry.provider == "google" and entry.client == "genai_sdk":
        client = google_genai_client
    else:
        # Registry entry first; prefix heuristics only for unknown
        # (env-override) ids — see model_registry.infer_provider.
        provider = entry.provider if entry is not None else model_registry.infer_provider(model)
        client = {
            "google": google_client,
            "openai": openai_client,
        }.get(provider, groq_client)
    async for event in client.stream_message(
        messages, model=model, tools=tools, api_key=api_key
    ):
        yield event


async def stream_message(
    messages: list[dict],
    model: str,
    tools: list[dict] | None = None,
    api_key: str | None = None,
) -> AsyncIterator[StreamChunk | StreamResult]:
    """Dispatch with bounded retry on transient errors (see module docstring
    for why a stream that already yielded is never retried)."""
    attempt = 0
    while True:
        yielded_any = False
        stream = _dispatch(messages, model=model, tools=tools, api_key=api_key)
        try:
            async for event in stream:
                yielded_any = True
                yield event
            return
        except Exception as e:
            if (
                yielded_any
                or attempt >= len(RETRY_DELAYS)
                or not _is_transient_error(e)
            ):
                raise
            delay = RETRY_DELAYS[attempt]
            attempt += 1
            logger.warning(
                "transient LLM error for model %s (%s); retry %d/%d in %.1fs",
                model, e, attempt, len(RETRY_DELAYS), delay,
            )
            await asyncio.sleep(delay)
        finally:
            await stream.aclose()
