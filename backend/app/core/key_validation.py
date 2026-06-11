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

logger = logging.getLogger(__name__)

_TIMEOUT = 5.0
PERPLEXITY_BASE_URL = "https://api.perplexity.ai"
OPENAI_BASE_URL = "https://api.openai.com/v1"

# Cheapest/fastest model per OpenAI-compatible provider, used only for the
# 1-token validation ping.
_PING_MODEL = {
    "llm:groq": "llama-3.1-8b-instant",
    "llm:google_ai": "gemini-2.5-flash",
    "llm:openai": "gpt-5.4-mini",
    "search:perplexity": "sonar",
}
_BASE_URL = {
    "llm:groq": settings.groq_base_url,
    "llm:google_ai": GOOGLE_BASE_URL,
    "llm:openai": OPENAI_BASE_URL,
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
            max_tokens=1,
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


async def validate_key(provider: str, key: str) -> ValidationResult:
    """Validate `key` against `provider` with a real call. Returns a
    ValidationResult; never raises for provider-side failures (only for an
    unknown provider string)."""
    key = (key or "").strip()
    if not key:
        return ValidationResult(False, "No key provided.")
    if provider == "search:tavily":
        return await _validate_tavily(key)
    if provider in _PING_MODEL:
        return await _validate_openai_compatible(
            key, _BASE_URL[provider], _PING_MODEL[provider]
        )
    raise ValueError(f"unknown provider '{provider}'")
