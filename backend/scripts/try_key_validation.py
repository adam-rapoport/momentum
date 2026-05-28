"""Smoke test: live API-key validation pings (C8 Connections).

For each provider that has a key in `.env`, validates the real key (expect ✓)
and a deliberately garbage key (expect ✗). Providers without a configured key
are skipped. Makes real network calls.

Usage:
  .venv/bin/python -m scripts.try_key_validation
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings
from app.core.key_validation import validate_key

CASES = [
    ("llm:groq", settings.groq_api_key, "gsk_garbage_key_definitely_invalid_000000000000"),
    ("llm:google_ai", settings.google_ai_api_key, "AIzaGARBAGE_invalid_key_0000000000000"),
    ("search:tavily", settings.tavily_api_key, "tvly-garbage-invalid-0000000000000000"),
    ("search:perplexity", settings.perplexity_api_key, "pplx-garbage-invalid-0000000000000000"),
]


async def main() -> None:
    for provider, real_key, bad_key in CASES:
        print(f"\n=== {provider} ===")
        if real_key:
            res = await validate_key(provider, real_key)
            flag = "✓" if res.ok else "✗"
            print(f"  real key:    {flag} {res.detail}")
        else:
            print("  real key:    (skipped — no key in .env)")
        bad = await validate_key(provider, bad_key)
        flag = "✓" if bad.ok else "✗"
        print(f"  garbage key: {flag} {bad.detail}")


if __name__ == "__main__":
    asyncio.run(main())
