from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest
import respx
from httpx import Response

from wstk.cache import Cache, CacheSettings
from wstk.errors import ExitCode, WstkError
from wstk.fetch.http import FetchSettings, fetch_url


def test_fetch_uses_cache(tmp_path: Path) -> None:
    cache = Cache(CacheSettings(cache_dir=tmp_path, ttl=timedelta(days=1), max_mb=10))

    settings = FetchSettings(
        timeout=5.0,
        proxy=None,
        headers={"user-agent": "wstk-test"},
        max_bytes=1024 * 1024,
        follow_redirects=True,
        detect_blocks=True,
        cache=cache,
    )

    url = "https://example.com/page"
    with respx.mock:
        respx.get(url).mock(return_value=Response(200, text="<html><body>ok</body></html>"))
        first = fetch_url(url, settings=settings)
        assert first.cache_hit is None

        # Second run should hit the cache and not require a respx route.
        second = fetch_url(url, settings=settings)
        assert second.cache_hit is not None
        assert second.body == first.body


def test_fetch_not_found(tmp_path: Path) -> None:
    cache = Cache(CacheSettings(cache_dir=tmp_path, ttl=timedelta(days=1), max_mb=10))
    settings = FetchSettings(
        timeout=5.0,
        proxy=None,
        headers={"user-agent": "wstk-test"},
        max_bytes=1024 * 1024,
        follow_redirects=True,
        detect_blocks=True,
        cache=cache,
    )

    url = "https://example.com/missing"
    with respx.mock:
        respx.get(url).mock(return_value=Response(404))
        with pytest.raises(WstkError) as exc:
            fetch_url(url, settings=settings)
        assert exc.value.code == "not_found"
        assert exc.value.exit_code == ExitCode.NOT_FOUND
