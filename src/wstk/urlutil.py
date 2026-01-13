from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from urllib.parse import ParseResult, urlparse, urlunparse


@dataclass(frozen=True, slots=True)
class DomainRules:
    allow: tuple[str, ...] = ()
    block: tuple[str, ...] = ()


def normalize_host(host: str) -> str:
    return host.strip().strip(".").lower()


def normalize_domain_entry(value: str) -> str | None:
    candidate = value.strip()
    if not candidate:
        return None
    if "://" not in candidate:
        candidate = f"//{candidate}"
    host = urlparse(candidate).hostname
    if not host:
        return None
    return normalize_host(host)


def normalize_domains(values: Iterable[str]) -> tuple[str, ...]:
    domains: list[str] = []
    seen: set[str] = set()
    for entry in values:
        normalized_domain = normalize_domain_entry(str(entry))
        if not normalized_domain or normalized_domain in seen:
            continue
        seen.add(normalized_domain)
        domains.append(normalized_domain)
    return tuple(domains)


def get_host(url: str) -> str | None:
    parsed = urlparse(url)
    if not parsed.hostname:
        return None
    return normalize_host(parsed.hostname)


def host_matches_domain(host: str, domain: str) -> bool:
    domain_norm = normalize_host(domain)
    if not domain_norm:
        return False
    if host == domain_norm:
        return True
    return host.endswith(f".{domain_norm}")


def is_allowed(url: str, rules: DomainRules) -> bool:
    host = get_host(url)
    if host is None:
        return False

    if any(host_matches_domain(host, d) for d in rules.block):
        return False
    if rules.allow:
        return any(host_matches_domain(host, d) for d in rules.allow)
    return True


def filter_urls(urls: Iterable[str], rules: DomainRules) -> list[str]:
    return [u for u in urls if is_allowed(u, rules)]


def redact_url(url: str) -> str:
    parsed = urlparse(url)
    hostname = parsed.hostname or ""
    netloc = hostname
    if parsed.port:
        netloc = f"{hostname}:{parsed.port}"
    if not netloc:
        netloc = parsed.netloc
    redacted = ParseResult(
        scheme=parsed.scheme,
        netloc=netloc,
        path=parsed.path,
        params=parsed.params,
        query="",
        fragment="",
    )
    return urlunparse(redacted)
