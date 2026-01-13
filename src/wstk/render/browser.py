from __future__ import annotations

import hashlib
import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from wstk.errors import ExitCode, WstkError
from wstk.models import ArtifactInfo, Document, HttpInfo, RenderInfo

try:
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover
    class _PlaywrightStubError(Exception):
        pass

    PlaywrightError = _PlaywrightStubError
    PlaywrightTimeoutError = _PlaywrightStubError
    sync_playwright = None

_BLOCK_PATTERNS = [
    re.compile(r"checking your browser", re.IGNORECASE),
    re.compile(r"verify you are human", re.IGNORECASE),
    re.compile(r"enable javascript", re.IGNORECASE),
    re.compile(r"access denied", re.IGNORECASE),
    re.compile(r"unusual traffic", re.IGNORECASE),
]


@dataclass(frozen=True, slots=True)
class RenderSettings:
    timeout: float
    proxy: str | None
    wait_ms: int
    wait_for: str | None
    headful: bool
    screenshot: bool
    evidence_dir: Path
    profile_dir: Path | None
    profile_label: str | None


@dataclass(frozen=True, slots=True)
class RenderResult:
    document: Document
    html: str


def render_available() -> tuple[bool, str | None]:
    if sync_playwright is None:
        return False, "playwright is not installed"
    return True, None


def resolve_evidence_dir(*, evidence_dir: str | None, cache_dir: str) -> Path:
    if evidence_dir:
        path = Path(evidence_dir).expanduser()
    else:
        path = Path(cache_dir).expanduser() / "evidence"
    path.mkdir(parents=True, exist_ok=True)
    return path


def resolve_system_profile() -> Path:
    candidates: list[str] = []
    if sys.platform == "darwin":
        candidates = [
            "~/Library/Application Support/Google/Chrome",
            "~/Library/Application Support/Chromium",
            "~/Library/Application Support/Microsoft Edge",
        ]
    elif sys.platform.startswith("linux"):
        candidates = [
            "~/.config/google-chrome",
            "~/.config/chromium",
            "~/.config/microsoft-edge",
        ]
    elif sys.platform.startswith("win"):
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("USERPROFILE") or ""
        if base:
            candidates = [
                os.path.join(base, "Google/Chrome/User Data"),
                os.path.join(base, "Microsoft/Edge/User Data"),
            ]
    for candidate in candidates:
        path = Path(candidate).expanduser()
        if path.exists():
            return path
    raise WstkError(
        code="profile_not_found",
        message="system browser profile not found",
        exit_code=ExitCode.INVALID_USAGE,
        details={"searched": candidates},
    )


def render_url(url: str, *, settings: RenderSettings) -> RenderResult:
    available, reason = render_available()
    if not available:
        raise WstkError(
            code="missing_dependency",
            message="playwright is required for browser rendering",
            exit_code=ExitCode.RUNTIME_ERROR,
            details={
                "reason": reason,
                "install": "pip install playwright && playwright install chromium",
            },
        )

    dom_path, screenshot_path = _evidence_paths(url, settings.evidence_dir)
    timeout_ms = int(settings.timeout * 1000)

    html = ""
    final_url = url
    status = 0
    headers_subset: dict[str, str] = {}

    proxy = None
    if settings.proxy:
        proxy = {"server": settings.proxy}

    def run_session(browser_type) -> None:
        nonlocal html, final_url, status, headers_subset
        if settings.profile_dir is not None:
            settings.profile_dir.mkdir(parents=True, exist_ok=True)
            context = browser_type.launch_persistent_context(
                user_data_dir=str(settings.profile_dir),
                headless=not settings.headful,
                proxy=proxy,
                timeout=timeout_ms,
            )
            try:
                html, final_url, status, headers_subset = _render_page(
                    context, url, timeout_ms, settings, screenshot_path
                )
            finally:
                context.close()
            return

        browser = browser_type.launch(
            headless=not settings.headful,
            proxy=proxy,
            timeout=timeout_ms,
        )
        try:
            context = browser.new_context()
            try:
                html, final_url, status, headers_subset = _render_page(
                    context, url, timeout_ms, settings, screenshot_path
                )
            finally:
                context.close()
        finally:
            browser.close()

    try:
        assert sync_playwright is not None
        with sync_playwright() as playwright:
            run_session(playwright.chromium)
    except PlaywrightTimeoutError:
        raise WstkError(
            code="timeout",
            message="render timed out",
            exit_code=ExitCode.RUNTIME_ERROR,
            details={"url": url, "timeout": settings.timeout},
        )
    except PlaywrightError as exc:
        raise WstkError(
            code="render_failed",
            message="browser render failed",
            exit_code=ExitCode.RUNTIME_ERROR,
            details={"url": url, "error": str(exc)},
        )

    html_bytes = html.encode("utf-8")
    dom_path.write_bytes(html_bytes)

    if status == 404:
        raise WstkError(
            code="not_found",
            message="URL returned 404 (not found)",
            exit_code=ExitCode.NOT_FOUND,
            details={"url": url, "final_url": final_url, "dom_path": str(dom_path)},
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
                dom_path=str(dom_path),
            ),
        )

    blocked_pattern = _find_pattern(_BLOCK_PATTERNS, html)
    if blocked_pattern:
        raise WstkError(
            code="blocked",
            message="blocked/bot wall detected in rendered HTML",
            exit_code=ExitCode.BLOCKED,
            details=_blocked_details(
                url=url,
                final_url=final_url,
                status=status,
                reason="bot_wall",
                pattern=blocked_pattern,
                dom_path=str(dom_path),
            ),
        )

    screenshot_value = None
    if settings.screenshot:
        screenshot_value = str(screenshot_path)

    doc = Document.new(url=final_url, fetch_method="browser")
    doc = Document(
        url=doc.url,
        fetched_at=doc.fetched_at,
        fetch_method=doc.fetch_method,
        http=HttpInfo(status=status, final_url=final_url, headers=headers_subset),
        artifact=ArtifactInfo(
            body_path=str(dom_path),
            content_type=_normalize_content_type(headers_subset.get("content-type"))
            or "text/html",
            bytes=len(html_bytes),
        ),
        render=RenderInfo(
            engine="playwright",
            dom_path=str(dom_path),
            screenshot_path=screenshot_value,
            headful=settings.headful,
            profile=settings.profile_label,
        ),
        extracted=None,
    )
    return RenderResult(document=doc, html=html)


def _render_page(
    context: Any,
    url: str,
    timeout_ms: int,
    settings: RenderSettings,
    screenshot_path: Path,
) -> tuple[str, str, int, dict[str, str]]:
    page = context.new_page()
    response = page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)

    if settings.wait_for:
        if settings.wait_for == "network-idle":
            page.wait_for_load_state("networkidle", timeout=timeout_ms)
        else:
            page.wait_for_selector(settings.wait_for, timeout=timeout_ms)
    if settings.wait_ms > 0:
        page.wait_for_timeout(settings.wait_ms)

    if settings.screenshot:
        page.screenshot(path=str(screenshot_path), full_page=True)

    html = page.content()
    final_url = page.url
    status = response.status if response else 0
    headers_subset: dict[str, str] = {}
    if response:
        for key in ["content-type", "content-language", "last-modified", "etag"]:
            if key in response.headers:
                headers_subset[key] = response.headers[key]

    return html, final_url, status, headers_subset


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


def _blocked_next_steps(url: str) -> list[str]:
    return [
        "If this site requires a session, use `wstk render --profile <path>` or "
        "`--use-system-profile`.",
        "Consider an alternate source or cached mirror if available.",
    ]


def _blocked_details(
    *,
    url: str,
    final_url: str,
    status: int,
    reason: str,
    dom_path: str,
    pattern: str | None = None,
) -> dict[str, Any]:
    details: dict[str, Any] = {
        "url": url,
        "final_url": final_url,
        "status": status,
        "blocked": True,
        "reason": reason,
        "next_steps": _blocked_next_steps(final_url),
        "dom_path": dom_path,
    }
    if pattern:
        details["pattern"] = pattern
    return details


def _evidence_paths(url: str, evidence_dir: Path) -> tuple[Path, Path]:
    key = hashlib.sha256(url.encode("utf-8")).hexdigest()[:12]
    stamp = int(time.time() * 1000)
    base = f"render-{stamp}-{key}"
    return evidence_dir / f"{base}.html", evidence_dir / f"{base}.png"
