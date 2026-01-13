from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse, urlunparse
from urllib.robotparser import RobotFileParser

import httpx


@dataclass(frozen=True, slots=True)
class RobotsCheck:
    url: str
    robots_url: str | None
    allowed: bool
    status: int | None


def check_robots(
    url: str,
    *,
    user_agent: str | None,
    timeout: float,
    proxy: str | None,
) -> RobotsCheck:
    robots_url = _robots_url(url)
    if not robots_url:
        return RobotsCheck(url=url, robots_url=None, allowed=True, status=None)

    headers = {
        "user-agent": user_agent or "*",
        "accept": "text/plain,*/*",
    }
    client_args: dict[str, object] = {
        "timeout": httpx.Timeout(timeout=timeout),
        "follow_redirects": True,
    }
    if proxy:
        client_args["proxy"] = proxy

    try:
        with httpx.Client(**client_args) as client:
            resp = client.get(robots_url, headers=headers)
    except Exception:
        return RobotsCheck(url=url, robots_url=robots_url, allowed=True, status=None)

    status = int(resp.status_code)
    if status != 200:
        return RobotsCheck(url=url, robots_url=robots_url, allowed=True, status=status)

    parser = RobotFileParser()
    parser.parse(resp.text.splitlines())
    allowed = parser.can_fetch(user_agent or "*", url)
    return RobotsCheck(url=url, robots_url=robots_url, allowed=allowed, status=status)


def _robots_url(url: str) -> str | None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return None
    if not parsed.netloc:
        return None
    return urlunparse((parsed.scheme, parsed.netloc, "/robots.txt", "", "", ""))
