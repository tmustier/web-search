from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path

from wstk.cache import Cache, CacheSettings


def test_cache_put_get(tmp_path: Path) -> None:
    cache = Cache(CacheSettings(cache_dir=tmp_path, ttl=timedelta(days=1), max_mb=10))
    body_path = cache.put(key="abc", meta={"status": 200}, body=b"hello")
    assert body_path.exists()

    hit = cache.get(key="abc")
    assert hit is not None
    assert hit.key == "abc"
    assert hit.body_path.read_bytes() == b"hello"

    # meta is stored as JSON
    meta_path = tmp_path / "items" / "abc.json"
    assert json.loads(meta_path.read_text(encoding="utf-8"))["status"] == 200
