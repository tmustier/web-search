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


def _looks_blocked(text: str) -> bool:
    return any(p.search(text) for p in _BLOCK_PATTERNS)


def _looks_needs_render(text: str) -> bool:
    return any(p.search(text) for p in _NEEDS_RENDER_PATTERNS)


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
            details={"url": url, "final_url": final_url, "status": status},
        )

    body = resp.content
    if settings.max_bytes and len(body) > settings.max_bytes:
        raise WstkError(
            code="too_large",
            message=f"response exceeded --max-bytes ({settings.max_bytes})",
            exit_code=ExitCode.RUNTIME_ERROR,
            details={"url": url, "bytes": len(body), "max_bytes": settings.max_bytes},
        )

    content_type = resp.headers.get("content-type")
    text_preview = ""
    if settings.detect_blocks:
        try:
            text_preview = body[:200_000].decode("utf-8", errors="ignore")
        except Exception:
            text_preview = ""

    if settings.detect_blocks and text_preview:
        if _looks_blocked(text_preview):
            raise WstkError(
                code="blocked",
                message="blocked/bot wall detected in HTML",
                exit_code=ExitCode.BLOCKED,
                details={"url": url, "final_url": final_url, "status": status},
            )
        if _looks_needs_render(text_preview):
            raise WstkError(
                code="needs_render",
                message="page appears to require JavaScript rendering",
                exit_code=ExitCode.NEEDS_RENDER,
                details={"url": url, "final_url": final_url, "status": status},
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
