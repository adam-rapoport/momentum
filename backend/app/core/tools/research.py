"""Research tools: WebSearch (via Tavily) and WebFetch (httpx + trafilatura).

Tavily is used instead of Brave because its snippets are already cleaned
for LLM consumption — we don't have to strip HTML ourselves for each
result. Free tier allows 1000 queries/month which is plenty for dev.

WebFetch uses trafilatura to extract the main article content from a
URL's HTML, dropping nav/footer/ads — gives the model a much cleaner
text block than raw HTML and saves a ton of input tokens.
"""
from __future__ import annotations

import asyncio
import logging

import httpx
import trafilatura

from app.config import settings
from app.core.search import get_active_search_provider
from app.core.search.base import SearchProvider, SearchResultItem
from app.core.search.tavily_provider import TavilyProvider
from app.core.tools import Tool, get_context, register

logger = logging.getLogger(__name__)

MAX_FETCH_BYTES = 2_000_000  # 2 MB — refuse pages larger than this
MAX_OUTPUT_CHARS = 20_000  # ~5k tokens of cleaned text per fetch


async def _resolve_search_provider() -> SearchProvider | None:
    """Pick the user's configured provider when running inside a turn; fall
    back to an env-keyed Tavily client for context-free callers (scripts)."""
    try:
        ctx = get_context()
    except RuntimeError:
        ctx = None
    if ctx is not None:
        provider = await get_active_search_provider(ctx.db, ctx.user_id)
        if provider is not None:
            return provider
    if settings.tavily_api_key:
        return TavilyProvider(settings.tavily_api_key)
    return None


async def _web_search(input_data: dict) -> str:
    query = (input_data.get("query") or "").strip()
    if not query:
        return "Error: 'query' is required."

    max_results = int(input_data.get("max_results", 5))
    max_results = max(1, min(max_results, 10))

    provider = await _resolve_search_provider()
    if provider is None:
        return (
            "Error: No web search provider is configured. Add a Tavily or "
            "Perplexity key under Settings → Integrations → Web Search."
        )

    try:
        results: list[SearchResultItem] = await provider.search(query, max_results)
    except Exception as e:  # noqa: BLE001
        logger.exception("%s search failed", provider.name)
        return f"Error: {provider.name} search failed: {e}"

    if not results:
        return f"No results found for: {query}"

    lines = [f"Search results for: {query} (via {provider.name})", ""]
    for i, r in enumerate(results, 1):
        lines.append(f"[{i}] {r.title}")
        if r.url:
            lines.append(f"    {r.url}")
        if r.snippet:
            lines.append(f"    {r.snippet}")
        lines.append("")
    return "\n".join(lines).strip()


async def _web_fetch(input_data: dict) -> str:
    url = (input_data.get("url") or "").strip()
    if not url:
        return "Error: 'url' is required."
    if not (url.startswith("http://") or url.startswith("https://")):
        return f"Error: url must start with http:// or https:// (got: {url!r})"

    try:
        async with httpx.AsyncClient(
            timeout=20.0,
            follow_redirects=True,
            headers={"User-Agent": "pMomentum/0.1 (+https://local.dev)"},
        ) as client:
            resp = await client.get(url)
    except httpx.HTTPError as e:
        return f"Error fetching {url}: {e}"

    if resp.status_code >= 400:
        return f"Error: {url} returned HTTP {resp.status_code}"

    body_bytes = resp.content[:MAX_FETCH_BYTES]
    content_type = resp.headers.get("content-type", "").lower()

    if "html" not in content_type and "xml" not in content_type:
        # Non-HTML: hand back decoded text directly, truncated.
        try:
            text = body_bytes.decode(resp.encoding or "utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            text = body_bytes.decode("utf-8", errors="replace")
        text = text[:MAX_OUTPUT_CHARS]
        return f"Fetched: {url}\nContent-Type: {content_type or 'unknown'}\n\n{text}"

    # trafilatura is CPU-bound; offload to a worker thread so we don't
    # stall the event loop on a big page.
    cleaned = await asyncio.to_thread(
        trafilatura.extract,
        body_bytes,
        include_comments=False,
        include_tables=True,
        favor_precision=True,
    )
    if not cleaned:
        return (
            f"Fetched {url} but could not extract readable content. "
            "The page may be JavaScript-heavy or empty."
        )
    cleaned = cleaned[:MAX_OUTPUT_CHARS]
    return f"Fetched: {url}\n\n{cleaned}"


WebSearch = register(
    Tool(
        name="WebSearch",
        description=(
            "Search the web via Tavily. Use for finding current information, "
            "competitive intel, industry data, or answers your training data "
            "may not cover. Returns a ranked list of results with title, URL, "
            "and a cleaned snippet. Prefer this over guessing from memory."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query. Be specific — include product names, years, or qualifiers.",
                },
                "max_results": {
                    "type": "integer",
                    "description": "How many results to return (1-10). Default 5.",
                    "minimum": 1,
                    "maximum": 10,
                },
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        handler=_web_search,
        is_read_only=True,
        is_externally_visible=False,
        category="research",
    )
)


WebFetch = register(
    Tool(
        name="WebFetch",
        description=(
            "Fetch a web page by URL and return its main readable text "
            "(navigation, ads, and boilerplate stripped out). Use this "
            "after WebSearch to read a specific result in depth, or when "
            "the user pastes a URL they want summarized."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "Absolute URL (must start with http:// or https://).",
                },
            },
            "required": ["url"],
            "additionalProperties": False,
        },
        handler=_web_fetch,
        is_read_only=True,
        is_externally_visible=False,
        category="research",
    )
)
