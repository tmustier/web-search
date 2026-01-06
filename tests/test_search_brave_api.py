from __future__ import annotations

import respx
from httpx import Response

from wstk.search.brave_api_provider import BraveApiSearchProvider
from wstk.search.types import SearchQuery


def test_brave_api_search(monkeypatch) -> None:
    monkeypatch.setenv("BRAVE_API_KEY", "test-key")

    provider = BraveApiSearchProvider(timeout=5.0, proxy=None)
    enabled, reason = provider.is_enabled()
    assert enabled is True
    assert reason is None

    query = SearchQuery(query="test", max_results=2, region=None, safe_search=None, time_range=None)

    payload = {
        "web": {
            "results": [
                {"title": "Result 1", "url": "https://example.com/1", "description": "One"},
                {"title": "Result 2", "url": "https://example.com/2", "description": "Two"},
            ]
        }
    }

    with respx.mock:
        respx.get(url__startswith="https://api.search.brave.com/res/v1/web/search").mock(
            return_value=Response(200, json=payload)
        )
        results = provider.search(query, include_raw=False)

    assert [r.url for r in results] == ["https://example.com/1", "https://example.com/2"]
