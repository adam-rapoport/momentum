"""Search provider abstraction (C8 / Sprint 7).

The WebSearch tool can run against more than one backend. Each provider
returns a normalized list of SearchResultItem so the tool's formatting and
the rest of the system don't care which engine answered.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass
class SearchResultItem:
    title: str
    url: str
    snippet: str


@runtime_checkable
class SearchProvider(Protocol):
    name: str

    async def search(self, query: str, max_results: int) -> list[SearchResultItem]:
        ...
