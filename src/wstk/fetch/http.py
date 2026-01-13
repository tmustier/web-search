from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import httpx

from wstk.cache import Cache, CacheHit, make_cache_key
from wstk.errors import ExitCode, WstkError
from wstk.models import ArtifactInfo, Document, HttpInfo

_BLOCK_PATTERNS = [
    re.compile(r"checking your browser", re.IGNORECASE),
    re.compile(r"verify you are human", re.IGNORECASE),
    re.compile(r"enable javascript", re.IGNORECASE),
    re.compile(r"access denied", re.IGNORECASE),
    re.compile(r"unusual traffic", re.IGNORECASE),
]

_NEEDS_RENDER_PATTERNS = [
    re.compile(r"you need to enable javascript", re.IGNORECASE),
    re.compile(r"requires javascript", re.IGNORECASE),
    re.compile(r"<noscript", re.IGNORECASE),
]


def _find_pattern(patterns: list[re.Pattern[str]], text: str) -> str | None:
    for pattern in patterns:
        if pattern.search(text):
            return pattern.pattern
    return None


def _normalize_content_type(content_type: str | None) -> str | None:
    if not content_type:
        return None
    value = content_type.split(";", 1)[0].strip().lower()
    return value or None


def _sniff_content_type(body: bytes) -> str | None:
    if not body:
        return None
    sample = body[:2048].lstrip()
    if not sample:
        return None
    if sample.startswith(b"%PDF"):
        return "application/pdf"
    lowered = sample.lower()
    if lowered.startswith(b"<!doctype html") or b"<html" in lowered:
        return "text/html"
    if lowered.startswith(b"{") or lowered.startswith(b"["):
        return "application/json"
    if b"\x00" not in sample:
        try:
            sample.decode("utf-8")
            return "text/plain"
        except UnicodeDecodeError:
            return None
    return None


def _detect_content_type(body: bytes, header_type: str | None) -> str | None:
    normalized = _normalize_content_type(header_type)
    if normalized and normalized not in {"application/octet-stream", "binary/octet-stream"}:
        return normalized
    sniffed = _sniff_content_type(body)
    return sniffed or normalized


def _blocked_next_steps(url: str) -> list[str]:
    return [
        f"Try `wstk render {url}` or `wstk extract --method browser {url}`.",
        "If this site requires a session, use `wstk render --profile <path>` or `--use-system-profile`.",
        "Consider an alternate source or cached mirror if available.",
    ]


def _needs_render_next_steps(url: str) -> list[str]:
    return [
        f"Try `wstk render {url}` or `wstk extract --method browser {url}`.",
        "If a login is required, use `--profile` or `--use-system-profile`.",
    ]


def _blocked_details(
    *, url: str, final_url: str, status: int, reason: str, pattern: str | None = None
) -> dict[str, Any]:
    details: dict[str, Any] = {
        "url": url,
        "final_url": final_url,
        "status": status,
        "blocked": True,
        "reason": reason,
        "next_steps": _blocked_next_steps(final_url),
    }
    if pattern:
        details["pattern"] = pattern
    return details


def _needs_render_details(
    *, url: str, final_url: str, status: int, reason: str, pattern: str | None = None
) -> dict[str, Any]:
    details: dict[str, Any] = {
        "url": url,
        "final_url": final_url,
        "status": status,
        "needs_render": True,
        "reason": reason,
        "next_steps": _needs_render_next_steps(final_url),
    }
    if pattern:
        details["pattern"] = pattern
    return details


@dataclass(frozen=True, slots=True)
class FetchSettings:
    timeout: float
    proxy: str | None
    headers: dict[str, str]
    max_bytes: int
    follow_redirects: bool
    detect_blocks: bool
    cache: Cache


@dataclass(frozen=True, slots=True)
class FetchResult:
    document: Document
    body: bytes
    cache_hit: CacheHit | None


def fetch_url(url: str, *, settings: FetchSettings) -> FetchResult:
    cache_key = make_cache_key(url, settings.headers)
    hit = settings.cache.get(key=cache_key)
    if hit is not None:
        body = hit.body_path.read_bytes()
        doc = _document_from_cache(url=url, hit=hit)
        return FetchResult(document=doc, body=body, cache_hit=hit)

    timeout = httpx.Timeout(timeout=settings.timeout)
    client_args: dict[str, Any] = {
        "timeout": timeout,
        "follow_redirects": settings.follow_redirects,
    }
    if settings.proxy:
        client_args["proxy"] = settings.proxy

    with httpx.Client(**client_args) as client:
        resp = client.get(url, headers=settings.headers)

    status = resp.status_code
    final_url = str(resp.url)

    if status == 404:
        raise WstkError(
            code="not_found",
            message="URL returned 404 (not found)",
            exit_code=ExitCode.NOT_FOUND,
            details={"url": url, "final_url": final_url},
        )
    if status in {401, 403, 429}:
        raise WstkError(
            code="blocked",
            message=f"URL blocked or access denied (HTTP {status})",
            exit_code=ExitCode.BLOCKED,
            details=_blocked_details(
                url=url,
                final_url=final_url,
                status=status,
                reason="http_status",
            ),
        )

    body = resp.content
    if settings.max_bytes and len(body) > settings.max_bytes:
        raise WstkError(
            code="too_large",
            message=f"response exceeded --max-bytes ({settings.max_bytes})",
            exit_code=ExitCode.RUNTIME_ERROR,
            details={"url": url, "bytes": len(body), "max_bytes": settings.max_bytes},
        )

    content_type = _detect_content_type(body, resp.headers.get("content-type"))
    text_preview = ""
    is_textual = content_type is None or content_type.startswith("text/") or content_type in {
        "application/xhtml+xml",
        "application/xml",
        "application/json",
    }
    if settings.detect_blocks and is_textual:
        try:
            text_preview = body[:200_000].decode("utf-8", errors="ignore")
        except Exception:
            text_preview = ""

    if settings.detect_blocks and text_preview:
        needs_render_pattern = _find_pattern(_NEEDS_RENDER_PATTERNS, text_preview)
        if needs_render_pattern:
            raise WstkError(
                code="needs_render",
                message="page appears to require JavaScript rendering",
                exit_code=ExitCode.NEEDS_RENDER,
                details=_needs_render_details(
                    url=url,
                    final_url=final_url,
                    status=status,
                    reason="javascript_required",
                    pattern=needs_render_pattern,
                ),
            )
        blocked_pattern = _find_pattern(_BLOCK_PATTERNS, text_preview)
        if blocked_pattern:
            raise WstkError(
                code="blocked",
                message="blocked/bot wall detected in HTML",
                exit_code=ExitCode.BLOCKED,
                details=_blocked_details(
                    url=url,
                    final_url=final_url,
                    status=status,
                    reason="bot_wall",
                    pattern=blocked_pattern,
                ),
            )

    headers_subset = {}
    for k in ["content-type", "content-language", "last-modified", "etag"]:
        if k in resp.headers:
            headers_subset[k] = resp.headers[k]

    meta = {
        "status": status,
        "final_url": final_url,
        "headers": headers_subset,
        "content_type": content_type,
        "bytes": len(body),
        "fetched_at": resp.headers.get("date"),
    }
    body_path = settings.cache.put(key=cache_key, meta=meta, body=body)

    doc = Document.new(url=final_url, fetch_method="http")
    doc = Document(
        url=doc.url,
        fetched_at=doc.fetched_at,
        fetch_method=doc.fetch_method,
        http=HttpInfo(status=status, final_url=final_url, headers=headers_subset),
        artifact=ArtifactInfo(
            body_path=str(body_path),
            content_type=content_type,
            bytes=len(body),
        ),
        extracted=None,
    )
    return FetchResult(document=doc, body=body, cache_hit=None)


def _document_from_cache(*, url: str, hit: CacheHit) -> Document:
    meta = hit.meta
    status = int(meta.get("status", 0) or 0)
    final_url = str(meta.get("final_url") or url)
    headers = meta.get("headers")
    if not isinstance(headers, dict):
        headers = {}
    headers_subset: dict[str, str] = {str(k): str(v) for k, v in headers.items()}

    content_type = meta.get("content_type")
    if content_type is not None:
        content_type = str(content_type)

    bytes_ = meta.get("bytes")
    bytes_int: int | None = None
    if isinstance(bytes_, int):
        bytes_int = bytes_

    doc = Document.new(url=final_url, fetch_method="http")
    return Document(
        url=doc.url,
        fetched_at=doc.fetched_at,
        fetch_method=doc.fetch_method,
        http=HttpInfo(status=status, final_url=final_url, headers=headers_subset),
        artifact=ArtifactInfo(
            body_path=str(hit.body_path),
            content_type=content_type,
            bytes=bytes_int,
        ),
        extracted=None,
    )
