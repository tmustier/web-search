from __future__ import annotations

import os
from urllib.parse import urlencode

import httpx

from wstk.errors import ExitCode, WstkError
from wstk.search.base import SearchProvider
from wstk.search.types import SearchQuery, SearchResultItem


def _parse_region(region: str) -> tuple[str | None, str | None]:
    # region examples: "us-en", "uk-en", "wt-wt"
    parts = region.split("-", 1)
    if len(parts) != 2:
        return None, None
    country = parts[0].upper()
    lang = parts[1].lower()
    if country == "WT":
        country = None
    if lang == "wt":
        lang = None
    return country, lang


def _map_time_range(time_range: str) -> str | None:
    mapping = {"d": "pd", "w": "pw", "m": "pm", "y": "py"}
    return mapping.get(time_range.lower())


class BraveApiSearchProvider(SearchProvider):
    id = "brave_api"

    def __init__(
        self, *, api_key: str | None = None, timeout: float = 15.0, proxy: str | None = None
    ) -> None:
        self._api_key = api_key or os.environ.get("BRAVE_API_KEY")
        self._timeout = timeout
        self._proxy = proxy

    def is_enabled(self) -> tuple[bool, str | None]:
        if not self._api_key:
            return False, "missing BRAVE_API_KEY"
        return True, None

    def search(self, query: SearchQuery, *, include_raw: bool) -> list[SearchResultItem]:
        enabled, reason = self.is_enabled()
        if not enabled:
            raise WstkError(
                code="provider_disabled",
                message=f"brave_api provider disabled: {reason}",
                exit_code=ExitCode.INVALID_USAGE,
            )

        params: dict[str, str] = {
            "q": query.query,
            "count": str(query.max_results),
        }

        if query.safe_search:
            params["safesearch"] = query.safe_search
        if query.region:
            country, lang = _parse_region(query.region)
            if country:
                params["country"] = country
            if lang:
                params["search_lang"] = lang
                params["ui_lang"] = lang
        if query.time_range:
            freshness = _map_time_range(query.time_range)
            if freshness:
                params["freshness"] = freshness

        url = f"https://api.search.brave.com/res/v1/web/search?{urlencode(params)}"
        headers = {
            "Accept": "application/json",
            "X-Subscription-Token": self._api_key or "",
        }

        with httpx.Client(timeout=httpx.Timeout(self._timeout), proxy=self._proxy) as client:
            resp = client.get(url, headers=headers)

        if resp.status_code == 401:
            raise WstkError(
                code="provider_auth",
                message="brave_api authentication failed (check BRAVE_API_KEY)",
                exit_code=ExitCode.RUNTIME_ERROR,
            )
        if resp.status_code != 200:
            raise WstkError(
                code="provider_error",
                message=f"brave_api returned HTTP {resp.status_code}",
                exit_code=ExitCode.RUNTIME_ERROR,
                details={"status": resp.status_code},
            )

        payload = resp.json()
        web = payload.get("web") or {}
        items = web.get("results") or []

        results: list[SearchResultItem] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "")
            url_val = str(item.get("url") or "")
            snippet = item.get("description")
            raw = item if include_raw else None

            if not title or not url_val:
                continue

            results.append(
                SearchResultItem(
                    title=title,
                    url=url_val,
                    snippet=str(snippet) if snippet else None,
                    published_at=None,
                    source_provider=self.id,
                    raw=raw,
                )
            )
            if len(results) >= query.max_results:
                break

        return results
