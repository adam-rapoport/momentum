"""Tavily search provider — the original WebSearch backend, lifted out of
research.py into the provider abstraction. Snippets come pre-cleaned for LLM
use, so no HTML stripping is needed."""
from __future__ import annotations

from tavily import AsyncTavilyClient

from app.core.search.base import SearchResultItem


class TavilyProvider:
    name = "tavily"

    def __init__(self, api_key: str) -> None:
        self._client = AsyncTavilyClient(api_key=api_key)

    async def search(self, query: str, max_results: int) -> list[SearchResultItem]:
        resp = await self._client.search(
            query=query, max_results=max_results, search_depth="basic"
        )
        results = resp.get("results", []) if isinstance(resp, dict) else []
        return [
            SearchResultItem(
                title=r.get("title", "(no title)"),
                url=r.get("url", ""),
                snippet=(r.get("content") or "").strip(),
            )
            for r in results
        ]
