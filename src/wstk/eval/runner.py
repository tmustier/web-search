from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, TypedDict
from urllib.parse import urlencode

from wstk.cache import Cache, make_cache_key
from wstk.errors import WstkError
from wstk.eval.scoring import normalize_url_for_match, score_search_results
from wstk.eval.suite import EvalSuite
from wstk.search.base import SearchProvider
from wstk.search.types import SearchQuery, SearchResultItem
from wstk.urlutil import DomainRules, is_allowed, redact_url


class ProviderSummary(TypedDict):
    provider: str
    cases_total: int
    criteria_cases: int
    hit_cases: int
    hit_rate: float
    mrr: float
    errors: int


class OverlapSummary(TypedDict):
    a: str
    b: str
    avg_jaccard: float
    cases: int


@dataclass(slots=True)
class ProviderStats:
    cases_total: int = 0
    criteria_cases: int = 0
    hit_cases: int = 0
    mrr_sum: float = 0.0
    errors: int = 0


@dataclass(frozen=True, slots=True)
class SearchEvalRunResult:
    report: dict[str, Any]
    any_error: bool
    any_miss: bool


def _criterion_for_case(case: object) -> str:
    expected_urls = getattr(case, "expected_urls", ())
    expected_domains = getattr(case, "expected_domains", ())
    if expected_urls:
        return "url"
    if expected_domains:
        return "domain"
    return "none"


def _search_item_from_dict(raw: object, *, fallback_provider: str) -> SearchResultItem | None:
    if not isinstance(raw, dict):
        return None
    title = raw.get("title")
    url = raw.get("url")
    if not isinstance(title, str) or not isinstance(url, str):
        return None
    if not title.strip() or not url.strip():
        return None

    snippet = raw.get("snippet")
    published_at = raw.get("published_at")
    source_provider = raw.get("source_provider")
    score = raw.get("score")
    raw_payload = raw.get("raw")

    return SearchResultItem(
        title=title.strip(),
        url=url.strip(),
        snippet=str(snippet) if isinstance(snippet, str) and snippet.strip() else None,
        published_at=str(published_at)
        if isinstance(published_at, str) and published_at.strip()
        else None,
        source_provider=str(source_provider)
        if isinstance(source_provider, str) and source_provider.strip()
        else fallback_provider,
        score=float(score) if isinstance(score, (int, float)) else None,
        raw=raw_payload if isinstance(raw_payload, dict) else None,
    )


def _load_cached_results(
    cache: Cache, *, key: str, provider_id: str
) -> list[SearchResultItem] | None:
    hit = cache.get(key=key)
    if hit is None:
        return None
    try:
        payload = json.loads(hit.body_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(payload, list):
        return None
    parsed: list[SearchResultItem] = []
    for item in payload:
        sr = _search_item_from_dict(item, fallback_provider=provider_id)
        if sr is not None:
            parsed.append(sr)
    return parsed


def run_search_eval(
    *,
    suite: EvalSuite,
    providers: list[tuple[str, SearchProvider]],
    cache: Cache,
    rules: DomainRules,
    k: int,
    redact: bool,
    include_results: bool,
) -> SearchEvalRunResult:
    provider_ids = [pid for pid, _p in providers]
    cache_reads = 0
    cache_hits = 0
    cache_writes = 0

    any_error = False
    any_miss = False

    per_provider = {pid: ProviderStats() for pid in provider_ids}
    url_sets: dict[tuple[str, str], set[str]] = {}
    cases_out: list[dict[str, Any]] = []

    for case in suite.cases:
        case_k = int(getattr(case, "k", None) or k)
        criterion = _criterion_for_case(case)
        case_by_provider: dict[str, Any] = {}
        case_entry: dict[str, Any] = {
            "id": case.id,
            "query": case.query,
            "expected_domains": list(case.expected_domains),
            "expected_urls": list(case.expected_urls),
            "k": case_k,
            "by_provider": case_by_provider,
        }

        for pid, provider in providers:
            stats = per_provider[pid]
            stats.cases_total += 1
            if criterion != "none":
                stats.criteria_cases += 1

            query = SearchQuery(
                query=case.query,
                max_results=case_k,
                region=None,
                safe_search=None,
                time_range=None,
            )
            key_url_params = {"q": query.query, "n": query.max_results}
            key_url = f"wstk://search/{pid}?{urlencode(key_url_params)}"
            key = make_cache_key(key_url)

            t0 = time.time()
            cache_reads += 1

            results = _load_cached_results(cache, key=key, provider_id=pid)
            if results is not None:
                cache_hits += 1
            else:
                try:
                    results = provider.search(query, include_raw=False)
                except WstkError as e:
                    any_error = True
                    stats.errors += 1
                    case_by_provider[pid] = {"error": e.to_error_dict()}
                    continue
                except Exception as e:  # pragma: no cover
                    any_error = True
                    stats.errors += 1
                    case_by_provider[pid] = {
                        "error": {"code": "unexpected_error", "message": str(e), "details": None}
                    }
                    continue

                cache.put(
                    key=key,
                    meta={"kind": "search", "provider": pid},
                    body=json.dumps([r.to_dict() for r in results], ensure_ascii=False).encode(
                        "utf-8"
                    ),
                )
                cache_writes += 1

            duration_ms = int((time.time() - t0) * 1000)

            filtered_results: list[SearchResultItem] = []
            for r in results:
                if (rules.allow or rules.block) and not is_allowed(r.url, rules):
                    continue
                url = redact_url(r.url) if redact else r.url
                if url == r.url:
                    filtered_results.append(r)
                else:
                    filtered_results.append(
                        SearchResultItem(
                            title=r.title,
                            url=url,
                            snippet=r.snippet,
                            published_at=r.published_at,
                            source_provider=r.source_provider,
                            score=r.score,
                            raw=r.raw,
                        )
                    )

            score = score_search_results(
                filtered_results,
                expected_domains=case.expected_domains,
                expected_urls=case.expected_urls,
                k=case_k,
            )

            passed = True
            if criterion == "url":
                passed = bool(score.url_hit)
            elif criterion == "domain":
                passed = bool(score.domain_hit)

            if criterion != "none":
                if passed:
                    stats.hit_cases += 1
                else:
                    any_miss = True
                rr = score.url_mrr if criterion == "url" else score.domain_mrr
                stats.mrr_sum += float(rr)

            url_sets[(case.id, pid)] = {
                normalize_url_for_match(r.url) for r in filtered_results[:case_k]
            }

            provider_entry: dict[str, Any] = {
                "criterion": criterion,
                "passed": passed,
                "duration_ms": duration_ms,
                "score": score.to_dict(),
            }
            if include_results:
                provider_entry["results"] = [r.to_dict() for r in filtered_results[:case_k]]
            case_by_provider[pid] = provider_entry

        cases_out.append(case_entry)

    summary_by_provider: list[ProviderSummary] = []
    for pid in provider_ids:
        stats = per_provider[pid]
        criteria_cases = stats.criteria_cases
        hit_cases = stats.hit_cases
        hit_rate = 0.0 if criteria_cases == 0 else hit_cases / float(criteria_cases)
        mrr = 0.0 if criteria_cases == 0 else stats.mrr_sum / float(criteria_cases)
        summary_by_provider.append(
            {
                "provider": pid,
                "cases_total": stats.cases_total,
                "criteria_cases": criteria_cases,
                "hit_cases": hit_cases,
                "hit_rate": hit_rate,
                "mrr": mrr,
                "errors": stats.errors,
            }
        )

    overlap: list[OverlapSummary] = []
    if len(provider_ids) >= 2:
        for i, a in enumerate(provider_ids):
            for b in provider_ids[i + 1 :]:
                values: list[float] = []
                for case in suite.cases:
                    a_set = url_sets.get((case.id, a), set())
                    b_set = url_sets.get((case.id, b), set())
                    union = a_set | b_set
                    if not union:
                        continue
                    values.append(len(a_set & b_set) / float(len(union)))
                overlap.append(
                    {
                        "a": a,
                        "b": b,
                        "avg_jaccard": 0.0 if not values else sum(values) / float(len(values)),
                        "cases": len(values),
                    }
                )

    report: dict[str, Any] = {
        "suite": {"path": suite.path, "case_count": len(suite.cases)},
        "settings": {"providers": provider_ids, "k": int(k)},
        "summary": {
            "by_provider": summary_by_provider,
            "overlap": overlap,
            "cache": {"reads": cache_reads, "hits": cache_hits, "writes": cache_writes},
        },
        "cases": cases_out,
    }

    return SearchEvalRunResult(report=report, any_error=any_error, any_miss=any_miss)
