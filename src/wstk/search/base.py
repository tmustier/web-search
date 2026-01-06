from __future__ import annotations

from abc import ABC, abstractmethod

from wstk.search.types import SearchQuery, SearchResultItem


class SearchProvider(ABC):
    id: str

    @abstractmethod
    def is_enabled(self) -> tuple[bool, str | None]:
        """Return (enabled, reason_if_disabled)."""

    @abstractmethod
    def search(self, query: SearchQuery, *, include_raw: bool) -> list[SearchResultItem]:
        raise NotImplementedError
