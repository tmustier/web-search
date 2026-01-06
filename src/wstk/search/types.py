from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SearchQuery:
    query: str
    max_results: int
    region: str | None
    safe_search: str | None
    time_range: str | None


@dataclass(frozen=True, slots=True)
class SearchResultItem:
    title: str
    url: str
    snippet: str | None
    published_at: str | None
    source_provider: str
    score: float | None = None
    raw: dict | None = None

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "published_at": self.published_at,
            "source_provider": self.source_provider,
            "score": self.score,
            "raw": self.raw,
        }
