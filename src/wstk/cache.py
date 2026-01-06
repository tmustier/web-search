from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class CacheSettings:
    cache_dir: Path
    ttl: timedelta
    max_mb: int
    enabled: bool = True
    fresh: bool = False


@dataclass(frozen=True, slots=True)
class CacheHit:
    key: str
    meta: dict[str, Any]
    body_path: Path


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def make_cache_key(url: str, headers: dict[str, str] | None = None) -> str:
    header_items = ""
    if headers:
        header_items = "\n".join(f"{k.lower()}:{v}" for k, v in sorted(headers.items()))
    return _sha256(f"url:{url}\n{header_items}")


class Cache:
    def __init__(self, settings: CacheSettings) -> None:
        self._settings = settings
        self._items_dir = settings.cache_dir / "items"
        self._items_dir.mkdir(parents=True, exist_ok=True)

    def get(self, *, key: str) -> CacheHit | None:
        if not self._settings.enabled or self._settings.fresh:
            return None

        meta_path = self._items_dir / f"{key}.json"
        body_path = self._items_dir / f"{key}.body"
        if not meta_path.exists() or not body_path.exists():
            return None

        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            self._safe_unlink(meta_path)
            self._safe_unlink(body_path)
            return None

        created_at = meta.get("created_at")
        if not isinstance(created_at, (int, float)):
            self._safe_unlink(meta_path)
            self._safe_unlink(body_path)
            return None

        if (time.time() - float(created_at)) > self._settings.ttl.total_seconds():
            self._safe_unlink(meta_path)
            self._safe_unlink(body_path)
            return None

        # touch files for LRU-ish eviction
        now = time.time()
        try:
            meta["last_accessed"] = now
            meta_path.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
            body_path.touch()
        except Exception:
            pass

        return CacheHit(key=key, meta=meta, body_path=body_path)

    def put(self, *, key: str, meta: dict[str, Any], body: bytes) -> Path:
        if not self._settings.enabled:
            return self._write_ephemeral(key=key, meta=meta, body=body)

        now = time.time()
        meta = {**meta, "created_at": now, "last_accessed": now}

        meta_path = self._items_dir / f"{key}.json"
        body_path = self._items_dir / f"{key}.body"

        body_path.write_bytes(body)
        meta_path.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")

        self.prune()
        return body_path

    def prune(self) -> None:
        if not self._settings.enabled:
            return

        ttl_seconds = self._settings.ttl.total_seconds()
        now = time.time()

        candidates: list[tuple[float, int, Path, Path]] = []
        total_bytes = 0

        for meta_path in self._items_dir.glob("*.json"):
            body_path = meta_path.with_suffix(".body")
            if not body_path.exists():
                self._safe_unlink(meta_path)
                continue

            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except Exception:
                self._safe_unlink(meta_path)
                self._safe_unlink(body_path)
                continue

            created_at = meta.get("created_at")
            last_accessed = meta.get("last_accessed", created_at)
            if not isinstance(created_at, (int, float)) or not isinstance(
                last_accessed, (int, float)
            ):
                self._safe_unlink(meta_path)
                self._safe_unlink(body_path)
                continue

            if (now - float(created_at)) > ttl_seconds:
                self._safe_unlink(meta_path)
                self._safe_unlink(body_path)
                continue

            size = meta_path.stat().st_size + body_path.stat().st_size
            total_bytes += size
            candidates.append((float(last_accessed), size, meta_path, body_path))

        max_bytes = int(self._settings.max_mb * 1024 * 1024)
        if total_bytes <= max_bytes:
            return

        # Evict least-recently-accessed until we are under budget.
        candidates.sort(key=lambda t: t[0])  # oldest first
        for _last_accessed, size, meta_path, body_path in candidates:
            self._safe_unlink(meta_path)
            self._safe_unlink(body_path)
            total_bytes -= size
            if total_bytes <= max_bytes:
                break

    def _write_ephemeral(self, *, key: str, meta: dict[str, Any], body: bytes) -> Path:
        tmp_dir = self._settings.cache_dir / "tmp"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        body_path = tmp_dir / f"{key}.{int(time.time())}.body"
        meta_path = tmp_dir / f"{key}.{int(time.time())}.json"
        body_path.write_bytes(body)
        meta_path.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
        return body_path

    @staticmethod
    def _safe_unlink(path: Path) -> None:
        try:
            path.unlink()
        except FileNotFoundError:
            return
        except Exception:
            return
