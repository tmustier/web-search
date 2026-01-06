from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import ParseResult, urlparse, urlunparse

from wstk.search.types import SearchResultItem
from wstk.urlutil import get_host, host_matches_domain


def normalize_url_for_match(url: str) -> str:
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    path = parsed.path or ""
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    normalized = ParseResult(
        scheme=scheme,
        netloc=netloc,
        path=path,
        params=parsed.params,
        query="",
        fragment="",
    )
    return urlunparse(normalized)


@dataclass(frozen=True, slots=True)
class SearchEvalScore:
    k: int
    domain_hit: bool
    domain_first_hit_rank: int | None
    domain_mrr: float
    matched_domains: list[str]
    url_hit: bool
    url_first_hit_rank: int | None
    url_mrr: float
    matched_urls: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "k": self.k,
            "domain_hit": self.domain_hit,
            "domain_first_hit_rank": self.domain_first_hit_rank,
            "domain_mrr": self.domain_mrr,
            "matched_domains": self.matched_domains,
            "url_hit": self.url_hit,
            "url_first_hit_rank": self.url_first_hit_rank,
            "url_mrr": self.url_mrr,
            "matched_urls": self.matched_urls,
        }


def score_search_results(
    results: list[SearchResultItem],
    *,
    expected_domains: tuple[str, ...],
    expected_urls: tuple[str, ...],
    k: int,
) -> SearchEvalScore:
    top = results[:k]

    matched_domains: list[str] = []
    domain_first_hit_rank: int | None = None
    if expected_domains:
        for idx, r in enumerate(top, start=1):
            host = get_host(r.url) or ""
            if any(host_matches_domain(host, d) for d in expected_domains):
                domain_first_hit_rank = idx
                break

        for d in expected_domains:
            if any(host_matches_domain((get_host(r.url) or ""), d) for r in top):
                matched_domains.append(d)

    domain_mrr = 0.0 if domain_first_hit_rank is None else 1.0 / float(domain_first_hit_rank)

    expected_url_set = {normalize_url_for_match(u) for u in expected_urls}
    top_url_set = {normalize_url_for_match(r.url) for r in top}

    matched_urls: list[str] = []
    url_first_hit_rank: int | None = None
    if expected_url_set:
        for idx, r in enumerate(top, start=1):
            if normalize_url_for_match(r.url) in expected_url_set:
                url_first_hit_rank = idx
                break

        for u in expected_urls:
            if normalize_url_for_match(u) in top_url_set:
                matched_urls.append(u)

    url_mrr = 0.0 if url_first_hit_rank is None else 1.0 / float(url_first_hit_rank)

    return SearchEvalScore(
        k=k,
        domain_hit=domain_first_hit_rank is not None,
        domain_first_hit_rank=domain_first_hit_rank,
        domain_mrr=domain_mrr,
        matched_domains=matched_domains,
        url_hit=url_first_hit_rank is not None,
        url_first_hit_rank=url_first_hit_rank,
        url_mrr=url_mrr,
        matched_urls=matched_urls,
    )

