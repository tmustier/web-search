from __future__ import annotations

from pathlib import Path

from wstk.cache import Cache
from wstk.cli_support import cache_from_args, parse_headers
from wstk.fetch.http import FetchSettings
from wstk.render.browser import RenderSettings, resolve_evidence_dir


def fetch_settings_from_args(
    args,
    *,
    max_bytes: int | None = None,
    follow_redirects: bool | None = None,
    detect_blocks: bool | None = None,
    cache: Cache | None = None,
    headers: dict[str, str] | None = None,
) -> FetchSettings:
    resolved_headers = headers or parse_headers(args)
    resolved_cache = cache or cache_from_args(args)
    if max_bytes is None:
        max_bytes = int(getattr(args, "max_bytes", 5 * 1024 * 1024))
    if follow_redirects is None:
        follow_redirects = bool(getattr(args, "follow_redirects", True))
    if detect_blocks is None:
        detect_blocks = bool(getattr(args, "detect_blocks", True))

    return FetchSettings(
        timeout=float(args.timeout),
        proxy=args.proxy,
        headers=resolved_headers,
        max_bytes=int(max_bytes),
        follow_redirects=bool(follow_redirects),
        detect_blocks=bool(detect_blocks),
        cache=resolved_cache,
    )


def render_settings_from_args(
    args,
    *,
    evidence_dir: Path | None = None,
    wait_ms: int = 0,
    wait_for: str | None = None,
    headful: bool = False,
    screenshot: bool = False,
    profile_dir: Path | None = None,
    profile_label: str | None = None,
) -> RenderSettings:
    resolved_evidence_dir = evidence_dir or resolve_evidence_dir(
        evidence_dir=args.evidence_dir,
        cache_dir=args.cache_dir,
    )

    return RenderSettings(
        timeout=float(args.timeout),
        proxy=args.proxy,
        wait_ms=int(wait_ms),
        wait_for=wait_for,
        headful=bool(headful),
        screenshot=bool(screenshot),
        evidence_dir=resolved_evidence_dir,
        profile_dir=profile_dir,
        profile_label=profile_label,
    )
