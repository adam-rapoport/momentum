"""Smoke test: web search provider abstraction (C8 / Sprint 7).

Exercises get_active_search_provider for the seeded user (defaults to Tavily),
and each provider directly if its key is in .env. Makes real network calls.

Usage:
  .venv/bin/python -m scripts.try_search [query]
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.config import settings
from app.core.search import get_active_search_provider
from app.core.search.perplexity_provider import PerplexityProvider
from app.core.search.tavily_provider import TavilyProvider
from app.dependencies import SessionLocal
from app.models import User

QUERY = sys.argv[1] if len(sys.argv) > 1 else "product management roadmap prioritization frameworks"


async def _run(label, provider) -> None:
    print(f"\n=== {label} ===")
    try:
        results = await provider.search(QUERY, 3)
    except Exception as e:  # noqa: BLE001
        print(f"  error: {e}")
        return
    if not results:
        print("  (no results)")
    for i, r in enumerate(results, 1):
        print(f"  [{i}] {r.title}")
        if r.url:
            print(f"      {r.url}")
        if r.snippet:
            print(f"      {r.snippet[:120]}…")


async def main() -> None:
    print(f"[try_search] query: {QUERY!r}")

    async with SessionLocal() as db:
        user = await db.scalar(select(User).order_by(User.created_at).limit(1))
        if user is None:
            print("No seeded user. Run: .venv/bin/python -m scripts.seed")
            return
        active = await get_active_search_provider(db, user.id)
        if active is None:
            print("\n[try_search] get_active_search_provider -> None (no key configured)")
        else:
            await _run(f"active provider ({active.name})", active)

    if settings.tavily_api_key:
        await _run("Tavily (direct)", TavilyProvider(settings.tavily_api_key))
    else:
        print("\n=== Tavily (direct) === (skipped — no TAVILY_API_KEY)")

    if settings.perplexity_api_key:
        await _run("Perplexity (direct)", PerplexityProvider(settings.perplexity_api_key))
    else:
        print("\n=== Perplexity (direct) === (skipped — no PERPLEXITY_API_KEY)")


if __name__ == "__main__":
    asyncio.run(main())
