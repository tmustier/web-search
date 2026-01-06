from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class CacheMeta:
    hit: bool
    key: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"hit": self.hit, "key": self.key}


@dataclass(frozen=True, slots=True)
class EnvelopeMeta:
    duration_ms: int
    cache: CacheMeta | None = None
    providers: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "duration_ms": self.duration_ms,
            "cache": None if self.cache is None else self.cache.to_dict(),
            "providers": self.providers,
        }


def make_envelope(
    *,
    ok: bool,
    command: str,
    version: str,
    data: Any,
    warnings: list[str],
    error: dict[str, Any] | None,
    meta: EnvelopeMeta,
) -> dict[str, Any]:
    return {
        "ok": ok,
        "command": command,
        "version": version,
        "data": data,
        "warnings": warnings,
        "error": error,
        "meta": meta.to_dict(),
    }


def print_json(payload: dict[str, Any], *, pretty: bool) -> None:
    if pretty:
        json.dump(payload, sys.stdout, ensure_ascii=False, indent=2, sort_keys=False)
        sys.stdout.write("\n")
        return
    json.dump(payload, sys.stdout, ensure_ascii=False, separators=(",", ":"), sort_keys=False)
    sys.stdout.write("\n")
