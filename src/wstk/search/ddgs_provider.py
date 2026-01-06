from __future__ import annotations

from ddgs import DDGS

from wstk.search.base import SearchProvider
from wstk.search.types import SearchQuery, SearchResultItem


class DdgsSearchProvider(SearchProvider):
    id = "ddgs"

    def is_enabled(self) -> tuple[bool, str | None]:
        return True, None

    def search(self, query: SearchQuery, *, include_raw: bool) -> list[SearchResultItem]:
        results: list[SearchResultItem] = []

        kwargs: dict[str, object] = {"max_results": query.max_results}
        if query.region:
            kwargs["region"] = query.region
        if query.safe_search:
            kwargs["safesearch"] = query.safe_search
        if query.time_range:
            kwargs["timelimit"] = query.time_range

        with DDGS() as ddgs:
            for item in ddgs.text(query.query, **kwargs):  # type: ignore[arg-type]
                title = str(item.get("title") or "")
                url = str(item.get("href") or item.get("url") or "")
                snippet = item.get("body") or item.get("snippet")
                raw = item if include_raw else None

                if not title or not url:
                    continue

                results.append(
                    SearchResultItem(
                        title=title,
                        url=url,
                        snippet=str(snippet) if snippet else None,
                        published_at=None,
                        source_provider=self.id,
                        raw=raw,
                    )
                )
                if len(results) >= query.max_results:
                    break

        return results
