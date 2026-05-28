"""Perplexity search provider (new, additive).

Perplexity's Sonar models answer a query AND return the sources they used.
We surface the synthesized answer as the first result, then each cited source
as its own result, normalized to SearchResultItem. Uses the OpenAI-compatible
endpoint, so no new SDK dependency.
"""
from __future__ import annotations

import logging

from openai import AsyncOpenAI

from app.core.search.base import SearchResultItem

logger = logging.getLogger(__name__)

PERPLEXITY_BASE_URL = "https://api.perplexity.ai"


class PerplexityProvider:
    name = "perplexity"

    def __init__(self, api_key: str) -> None:
        self._client = AsyncOpenAI(api_key=api_key, base_url=PERPLEXITY_BASE_URL)

    async def search(self, query: str, max_results: int) -> list[SearchResultItem]:
        resp = await self._client.chat.completions.create(
            model="sonar",
            messages=[{"role": "user", "content": query}],
        )
        message = resp.choices[0].message if resp.choices else None
        answer = (message.content if message else "") or ""

        items: list[SearchResultItem] = []
        if answer.strip():
            items.append(
                SearchResultItem(
                    title="Perplexity answer", url="", snippet=answer.strip()
                )
            )

        # Citations live in a non-standard top-level field; the OpenAI SDK keeps
        # unknown fields in model_extra. Handle both shapes defensively.
        citations = getattr(resp, "citations", None)
        if citations is None:
            extra = getattr(resp, "model_extra", None) or {}
            citations = extra.get("citations") or extra.get("search_results") or []

        for c in (citations or [])[:max_results]:
            if isinstance(c, str):
                items.append(SearchResultItem(title=c, url=c, snippet=""))
            elif isinstance(c, dict):
                url = c.get("url", "")
                items.append(
                    SearchResultItem(
                        title=c.get("title") or url or "(source)",
                        url=url,
                        snippet=(c.get("snippet") or "").strip(),
                    )
                )
        return items
