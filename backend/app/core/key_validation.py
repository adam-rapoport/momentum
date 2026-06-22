"""Real ("ping") validation of provider API keys for the Connections UI (C8).

Each validator makes a tiny live call (~1s, 5s hard timeout, no retries) so a
user gets a ✓/✗ the moment they save a key, instead of discovering a typo on
their first chat. A 401 is a hard failure; a 429 means the key is valid but
currently rate-limited (treated as OK — the key itself is fine).

Used by the connections API both to validate-before-store and to power the
standalone `POST /connections/{provider}/validate` endpoint.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

import httpx
from openai import (
    AsyncOpenAI,
    APIStatusError,
    AuthenticationError,
    PermissionDeniedError,
    RateLimitError,
)
from tavily import AsyncTavilyClient

from app.config import settings
from app.core.google_client import GOOGLE_BASE_URL
from app.core.mistral_client import MISTRAL_BASE_URL
from app.core.openrouter_client import OPENROUTER_BASE_URL

logger = logging.getLogger(__name__)

_TIMEOUT = 5.0
PERPLEXITY_BASE_URL = "https://api.perplexity.ai"
OPENAI_BASE_URL = "https://api.openai.com/v1"
ANTHROPIC_MODELS_URL = "https://api.anthropic.com/v1/models"

# Cheapest/fastest model per OpenAI-compatible provider, used only for the
# validation ping. (OpenAI and OpenRouter are validated via free, model-less
# endpoints instead — see validate_key — so they're not listed here.)
_PING_MODEL = {
    "llm:groq": "llama-3.1-8b-instant",
    "llm:google_ai": "gemini-2.5-flash",
    "search:perplexity": "sonar",
}
_BASE_URL = {
    "llm:groq": settings.groq_base_url,
    "llm:google_ai": GOOGLE_BASE_URL,
    "search:perplexity": PERPLEXITY_BASE_URL,
}


@dataclass
class ValidationResult:
    ok: bool
    detail: str


async def _validate_openai_compatible(
    api_key: str, base_url: str, model: str
) -> ValidationResult:
    client = AsyncOpenAI(
        api_key=api_key, base_url=base_url, timeout=_TIMEOUT, max_retries=0
    )
    try:
        await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "ping"}],
            # >= 16: some providers (e.g. Perplexity) reject a smaller cap.
            max_tokens=16,
        )
        return ValidationResult(True, "Key works.")
    except (AuthenticationError, PermissionDeniedError):
        return ValidationResult(False, "Provider rejected this key (HTTP 401).")
    except RateLimitError:
        # Key authenticated fine; it's just throttled. Still a valid key.
        return ValidationResult(True, "Key is valid (currently rate-limited).")
    except APIStatusError as e:
        if e.status_code in (401, 403):
            return ValidationResult(False, "Provider rejected this key.")
        if e.status_code == 429:
            return ValidationResult(True, "Key is valid (currently rate-limited).")
        return ValidationResult(False, f"Provider returned HTTP {e.status_code}.")
    except Exception as e:  # noqa: BLE001 — network/timeout/etc.
        logger.warning("key validation error (%s): %s", base_url, e)
        return ValidationResult(False, f"Couldn't reach the provider: {e}")


async def _validate_anthropic(api_key: str) -> ValidationResult:
    """Anthropic: GET /v1/models is authenticated and free (no tokens spent)."""
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            res = await client.get(
                ANTHROPIC_MODELS_URL,
                headers={"x-api-key": api_key, "anthropic-version": "2023-06-01"},
            )
    except Exception as e:  # noqa: BLE001 — network/timeout/etc.
        logger.warning("anthropic key validation error: %s", e)
        return ValidationResult(False, f"Couldn't reach Anthropic: {e}")
    if res.status_code == 200:
        return ValidationResult(True, "Key works.")
    if res.status_code in (401, 403):
        return ValidationResult(False, "Anthropic rejected this key (HTTP 401).")
    if res.status_code == 429:
        return ValidationResult(True, "Key is valid (currently rate-limited).")
    return ValidationResult(False, f"Anthropic returned HTTP {res.status_code}.")


async def _validate_models_list(api_key: str, base_url: str) -> ValidationResult:
    """Bearer-auth GET /models — authenticated and free. Used for Mistral."""
    client = AsyncOpenAI(
        api_key=api_key, base_url=base_url, timeout=_TIMEOUT, max_retries=0
    )
    try:
        await client.models.list()
        return ValidationResult(True, "Key works.")
    except (AuthenticationError, PermissionDeniedError):
        return ValidationResult(False, "Provider rejected this key (HTTP 401).")
    except RateLimitError:
        return ValidationResult(True, "Key is valid (currently rate-limited).")
    except APIStatusError as e:
        if e.status_code in (401, 403):
            return ValidationResult(False, "Provider rejected this key.")
        if e.status_code == 429:
            return ValidationResult(True, "Key is valid (currently rate-limited).")
        return ValidationResult(False, f"Provider returned HTTP {e.status_code}.")
    except Exception as e:  # noqa: BLE001 — network/timeout/etc.
        logger.warning("key validation error (%s): %s", base_url, e)
        return ValidationResult(False, f"Couldn't reach the provider: {e}")


async def _validate_ollama(base_url: str) -> ValidationResult:
    """Ollama: the 'key' is the server's base URL; validate by listing its
    installed models (GET /api/tags — unauthenticated, local)."""
    base = base_url.strip().rstrip("/")
    if not base.startswith(("http://", "https://")):
        return ValidationResult(
            False, "That doesn't look like a URL — e.g. http://localhost:11434"
        )
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            res = await client.get(f"{base}/api/tags")
    except Exception as e:  # noqa: BLE001 — connect refused/timeout/etc.
        logger.warning("ollama validation error (%s): %s", base, e)
        return ValidationResult(
            False, f"Couldn't reach Ollama at {base} — is it running?"
        )
    if res.status_code != 200:
        return ValidationResult(
            False, f"Ollama at {base} returned HTTP {res.status_code}."
        )
    try:
        count = len(res.json().get("models") or [])
    except ValueError:
        return ValidationResult(False, f"{base} doesn't look like an Ollama server.")
    if count == 0:
        return ValidationResult(
            True,
            "Ollama is reachable, but no models are installed yet — run "
            "`ollama pull llama3.1:8b` in Terminal.",
        )
    return ValidationResult(
        True, f"Ollama is reachable ({count} model{'s' if count != 1 else ''} installed)."
    )


async def _validate_tavily(api_key: str) -> ValidationResult:
    client = AsyncTavilyClient(api_key=api_key)
    try:
        await asyncio.wait_for(
            client.search(query="ping", max_results=1), timeout=_TIMEOUT
        )
        return ValidationResult(True, "Key works.")
    except asyncio.TimeoutError:
        return ValidationResult(False, "Tavily timed out — check your connection.")
    except Exception as e:  # noqa: BLE001
        msg = str(e).lower()
        if "401" in msg or "unauthorized" in msg or "invalid api key" in msg:
            return ValidationResult(False, "Tavily rejected this key.")
        if "432" in msg or "usage limit" in msg or "429" in msg:
            return ValidationResult(True, "Key is valid (usage limit reached).")
        logger.warning("tavily key validation error: %s", e)
        return ValidationResult(False, f"Couldn't validate with Tavily: {e}")


async def _validate_openrouter(api_key: str) -> ValidationResult:
    """OpenRouter: GET /key is authenticated and free. (GET /models is public,
    so it can't tell a good key from a bad one — and a chat ping depends on a
    specific model id, which we'd rather not couple validation to.)"""
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            res = await client.get(
                f"{OPENROUTER_BASE_URL}/key",
                headers={"Authorization": f"Bearer {api_key}"},
            )
    except Exception as e:  # noqa: BLE001 — network/timeout/etc.
        logger.warning("openrouter key validation error: %s", e)
        return ValidationResult(False, f"Couldn't reach OpenRouter: {e}")
    if res.status_code == 200:
        return ValidationResult(True, "Key works.")
    if res.status_code in (401, 403):
        return ValidationResult(False, "OpenRouter rejected this key (HTTP 401).")
    if res.status_code == 429:
        return ValidationResult(True, "Key is valid (currently rate-limited).")
    return ValidationResult(False, f"OpenRouter returned HTTP {res.status_code}.")


async def validate_key(provider: str, key: str) -> ValidationResult:
    """Validate `key` against `provider` with a real call. Returns a
    ValidationResult; never raises for provider-side failures (only for an
    unknown provider string)."""
    key = (key or "").strip()
    if not key:
        return ValidationResult(False, "No key provided.")
    if provider == "search:tavily":
        return await _validate_tavily(key)
    if provider == "llm:ollama":
        return await _validate_ollama(key)
    if provider == "llm:anthropic":
        return await _validate_anthropic(key)
    if provider == "llm:mistral":
        return await _validate_models_list(key, MISTRAL_BASE_URL)
    if provider == "llm:openai":
        # Free, model-less auth check (GET /v1/models). Avoids the GPT-5
        # max_completion_tokens rename and the min-reply-length floor.
        return await _validate_models_list(key, OPENAI_BASE_URL)
    if provider == "llm:openrouter":
        return await _validate_openrouter(key)
    if provider in _PING_MODEL:
        return await _validate_openai_compatible(
            key, _BASE_URL[provider], _PING_MODEL[provider]
        )
    raise ValueError(f"unknown provider '{provider}'")
