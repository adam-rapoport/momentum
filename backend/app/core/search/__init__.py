"""Search provider selection.

Resolves which provider the WebSearch tool should use for a given user:
their `users.preferences.search_provider` pick (default "tavily"), with the
key resolved via app.core.credentials (stored key → env fallback).
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import credentials
from app.core.search.base import SearchProvider, SearchResultItem
from app.core.search.perplexity_provider import PerplexityProvider
from app.core.search.tavily_provider import TavilyProvider
from app.models import User

DEFAULT_PROVIDER = "tavily"
VALID_PROVIDERS = ("tavily", "perplexity")

_CRED = {"tavily": "search:tavily", "perplexity": "search:perplexity"}
_IMPL = {"tavily": TavilyProvider, "perplexity": PerplexityProvider}


def _build(name: str, key: str) -> SearchProvider:
    return _IMPL[name](key)


async def get_active_search_provider(
    db: AsyncSession, user_id: UUID
) -> SearchProvider | None:
    """Return the user's selected search provider with a usable key, or None
    if no provider is configured."""
    user = await db.scalar(select(User).where(User.id == user_id))
    pref = (user.preferences or {}).get("search_provider") if user else None
    name = pref if pref in VALID_PROVIDERS else DEFAULT_PROVIDER

    key = await credentials.resolve_api_key(db, user_id, _CRED[name])
    if key:
        return _build(name, key)

    # Selected provider has no key — fall back to the other one if it does.
    other = "perplexity" if name == "tavily" else "tavily"
    other_key = await credentials.resolve_api_key(db, user_id, _CRED[other])
    if other_key:
        return _build(other, other_key)
    return None


__all__ = [
    "SearchProvider",
    "SearchResultItem",
    "TavilyProvider",
    "PerplexityProvider",
    "get_active_search_provider",
    "DEFAULT_PROVIDER",
    "VALID_PROVIDERS",
]
