from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from statistics import median
from typing import Any, TypedDict
from urllib.parse import urlencode

from wstk.cache import Cache, make_cache_key
from wstk.errors import WstkError
from wstk.eval.scoring import normalize_url_for_match, score_search_results
from wstk.eval.suite import EvalSuite
from wstk.extract.utils import choose_strategy, extract_html
from wstk.fetch.http import FetchSettings, fetch_url
from wstk.search.base import SearchProvider
from wstk.search.types import SearchQuery, SearchResultItem
from wstk.urlutil import DomainRules, get_host, host_matches_domain, is_allowed, redact_url


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


class FetchSummary(TypedDict):
    provider: str
    attempts: int
    success: int
    success_rate: float
    blocked: int
    needs_render: int
    not_found: int
    errors: int
    median_latency_ms: float | None


class ExtractSummary(TypedDict):
    provider: str
    attempts: int
    non_empty: int
    non_empty_rate: float
    median_word_count: float | None
    avg_boilerplate_ratio: float | None
    code_block_pages: int
    code_block_preserved: int
    code_block_preserved_rate: float | None
    errors: int


@dataclass(slots=True)
class FetchStats:
    attempts: int = 0
    success: int = 0
    blocked: int = 0
    needs_render: int = 0
    not_found: int = 0
    errors: int = 0
    durations_ms: list[int] = field(default_factory=list)
    cache_reads: int = 0
    cache_hits: int = 0
    cache_writes: int = 0


@dataclass(slots=True)
class ExtractStats:
    attempts: int = 0
    non_empty: int = 0
    errors: int = 0
    word_counts: list[int] = field(default_factory=list)
    boilerplate_ratios: list[float] = field(default_factory=list)
    code_block_pages: int = 0
    code_block_preserved: int = 0


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


_WORD_RE = re.compile(r"[A-Za-z0-9]+")
_LINK_RE = re.compile(r"\[[^\]]+\]\([^\)]+\)")
_CODE_TAG_RE = re.compile(r"<(pre|code)(\s|>)", re.IGNORECASE)
_CODE_FENCE_RE = re.compile(r"^```", re.MULTILINE)
_CODE_INDENT_RE = re.compile(r"^(?: {4}|\t)\S", re.MULTILINE)

_HTML_TYPES = {"text/html", "application/xhtml+xml"}
_TEXT_TYPES = {"text/plain", "application/json", "application/xml", "text/xml"}


def _criterion_for_case(case: object) -> str:
    expected_urls = getattr(case, "expected_urls", ())
    expected_domains = getattr(case, "expected_domains", ())
    if expected_urls:
        return "url"
    if expected_domains:
        return "domain"
    return "none"


def _median_value(values: list[int | float]) -> float | None:
    if not values:
        return None
    return float(median(values))


def _average_value(values: list[float]) -> float | None:
    if not values:
        return None
    return float(sum(values) / float(len(values)))


def _normalize_content_type(content_type: str | None) -> str | None:
    if not content_type:
        return None
    value = content_type.split(";", 1)[0].strip().lower()
    return value or None


def _is_html_content_type(content_type: str | None) -> bool:
    if content_type is None:
        return True
    return content_type in _HTML_TYPES


def _is_text_content_type(content_type: str | None) -> bool:
    if content_type is None:
        return False
    if content_type in _TEXT_TYPES:
        return True
    if content_type.startswith("text/") and content_type not in _HTML_TYPES:
        return True
    return False


def _word_count(value: str) -> int:
    if not value:
        return 0
    return len(_WORD_RE.findall(value))


def _boilerplate_ratio_proxy(markdown: str | None, text: str | None) -> float | None:
    if markdown:
        total = len(markdown)
        if total == 0:
            return None
        link_chars = sum(len(match.group(0)) for match in _LINK_RE.finditer(markdown))
        return link_chars / float(total)
    if text:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if not lines:
            return None
        short_lines = sum(1 for line in lines if len(line.split()) <= 3)
        return short_lines / float(len(lines))
    return None


def _markdown_has_code(markdown: str | None) -> bool:
    if not markdown:
        return False
    if _CODE_FENCE_RE.search(markdown):
        return True
    if _CODE_INDENT_RE.search(markdown):
        return True
    return False


def _select_eval_url(
    case: object, results: list[SearchResultItem], *, case_k: int
) -> tuple[str | None, str | None]:
    expected_urls = getattr(case, "expected_urls", ())
    expected_domains = getattr(case, "expected_domains", ())
    if expected_urls:
        return str(expected_urls[0]), "expected_url"
    if expected_domains:
        for r in results[:case_k]:
            host = get_host(r.url) or ""
            if any(host_matches_domain(host, d) for d in expected_domains):
                return r.url, "expected_domain"
    if results:
        return results[0].url, "top_result"
    return None, None


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


def _score_extraction(
    *, html: str, content_type: str | None, stats: ExtractStats
) -> dict[str, Any]:
    normalized = _normalize_content_type(content_type)
    if normalized and not _is_html_content_type(normalized) and not _is_text_content_type(normalized):
        return {
            "status": "skipped",
            "reason": "unsupported_content_type",
            "content_type": normalized,
        }

    stats.attempts += 1
    markdown = None
    text = None
    strategy = "readability"
    extraction_method = "plain_text"

    try:
        if _is_text_content_type(normalized):
            text = html
            strategy = "text"
            extraction_method = "plain_text"
        else:
            strategy = choose_strategy(html)
            extracted = extract_html(
                html,
                strategy=strategy,
                include_markdown=True,
                include_text=True,
            )
            markdown = extracted.markdown
            text = extracted.text
            extraction_method = extracted.extraction_method
    except Exception as exc:
        stats.errors += 1
        return {
            "status": "error",
            "error": {
                "code": "extract_error",
                "message": str(exc),
                "details": None,
            },
        }

    non_empty = bool((markdown or text or "").strip())
    if non_empty:
        stats.non_empty += 1

    text_source = text or markdown or ""
    word_count = _word_count(text_source)
    stats.word_counts.append(word_count)

    ratio = _boilerplate_ratio_proxy(markdown, text)
    if ratio is not None:
        stats.boilerplate_ratios.append(ratio)

    code_block_present = False
    code_block_preserved = None
    if not _is_text_content_type(normalized):
        code_block_present = bool(_CODE_TAG_RE.search(html))
        if code_block_present:
            stats.code_block_pages += 1
            code_block_preserved = _markdown_has_code(markdown)
            if code_block_preserved:
                stats.code_block_preserved += 1

    return {
        "status": "ok",
        "strategy": strategy,
        "extraction_method": extraction_method,
        "non_empty": non_empty,
        "word_count": word_count,
        "boilerplate_ratio": ratio,
        "code_block_present": code_block_present,
        "code_block_preserved": code_block_preserved,
    }


def _fetch_and_extract(
    *,
    case: object,
    results: list[SearchResultItem],
    case_k: int,
    rules: DomainRules,
    fetch_settings: FetchSettings | None,
    policy: str,
    fetch_stats: FetchStats,
    extract_stats: ExtractStats,
) -> tuple[dict[str, Any], dict[str, Any]]:
    target_url, source = _select_eval_url(case, results, case_k=case_k)
    if target_url is None:
        return {"status": "skipped", "reason": "no_results"}, {
            "status": "skipped",
            "reason": "no_fetch",
        }

    base_entry = {"target_url": target_url, "source": source}

    if fetch_settings is None:
        return {
            **base_entry,
            "status": "skipped",
            "reason": "fetch_disabled",
        }, {
            "status": "skipped",
            "reason": "fetch_disabled",
        }

    if policy == "strict" and not rules.allow:
        return {
            **base_entry,
            "status": "skipped",
            "reason": "policy_violation",
        }, {
            "status": "skipped",
            "reason": "policy_violation",
        }

    if not is_allowed(target_url, rules):
        return {
            **base_entry,
            "status": "skipped",
            "reason": "domain_blocked",
        }, {
            "status": "skipped",
            "reason": "domain_blocked",
        }

    fetch_stats.attempts += 1
    fetch_stats.cache_reads += 1
    t0 = time.time()

    try:
        res = fetch_url(target_url, settings=fetch_settings)
    except WstkError as exc:
        duration_ms = int((time.time() - t0) * 1000)
        if exc.code == "blocked":
            fetch_stats.blocked += 1
        elif exc.code == "needs_render":
            fetch_stats.needs_render += 1
        elif exc.code == "not_found":
            fetch_stats.not_found += 1
        else:
            fetch_stats.errors += 1
        return {
            **base_entry,
            "status": exc.code,
            "duration_ms": duration_ms,
            "error": exc.to_error_dict(),
        }, {"status": "skipped", "reason": "fetch_error"}
    except Exception as exc:
        duration_ms = int((time.time() - t0) * 1000)
        fetch_stats.errors += 1
        return {
            **base_entry,
            "status": "error",
            "duration_ms": duration_ms,
            "error": {
                "code": "unexpected_error",
                "message": str(exc),
                "details": None,
            },
        }, {"status": "skipped", "reason": "fetch_error"}

    duration_ms = int((time.time() - t0) * 1000)
    fetch_stats.success += 1
    fetch_stats.durations_ms.append(duration_ms)

    cache_hit = res.cache_hit is not None
    if cache_hit:
        fetch_stats.cache_hits += 1
    else:
        fetch_stats.cache_writes += 1

    http_info = res.document.http
    artifact = res.document.artifact
    content_type = artifact.content_type if artifact else None

    fetch_entry = {
        **base_entry,
        "status": "ok",
        "duration_ms": duration_ms,
        "http_status": http_info.status if http_info else None,
        "final_url": http_info.final_url if http_info else res.document.url,
        "content_type": content_type,
        "bytes": artifact.bytes if artifact else None,
        "cache_hit": cache_hit,
    }

    html = res.body.decode("utf-8", errors="replace")
    extract_entry = _score_extraction(
        html=html,
        content_type=content_type,
        stats=extract_stats,
    )
    return fetch_entry, extract_entry


def run_search_eval(
    *,
    suite: EvalSuite,
    providers: list[tuple[str, SearchProvider]],
    cache: Cache,
    rules: DomainRules,
    k: int,
    redact: bool,
    include_results: bool,
    fetch_settings: FetchSettings | None,
    policy: str,
) -> SearchEvalRunResult:
    provider_ids = [pid for pid, _p in providers]
    cache_reads = 0
    cache_hits = 0
    cache_writes = 0

    any_error = False
    any_miss = False

    per_provider = {pid: ProviderStats() for pid in provider_ids}
    fetch_by_provider = {pid: FetchStats() for pid in provider_ids}
    extract_by_provider = {pid: ExtractStats() for pid in provider_ids}
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
            fetch_candidates: list[SearchResultItem] = []
            for r in results:
                if (rules.allow or rules.block) and not is_allowed(r.url, rules):
                    continue
                fetch_candidates.append(r)
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

            fetch_entry, extract_entry = _fetch_and_extract(
                case=case,
                results=fetch_candidates,
                case_k=case_k,
                rules=rules,
                fetch_settings=fetch_settings,
                policy=policy,
                fetch_stats=fetch_by_provider[pid],
                extract_stats=extract_by_provider[pid],
            )
            provider_entry["fetch"] = fetch_entry
            provider_entry["extract"] = extract_entry

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

    fetch_summary_by_provider: list[FetchSummary] = []
    for pid in provider_ids:
        stats = fetch_by_provider[pid]
        attempts = stats.attempts
        success_rate = 0.0 if attempts == 0 else stats.success / float(attempts)
        fetch_summary_by_provider.append(
            {
                "provider": pid,
                "attempts": attempts,
                "success": stats.success,
                "success_rate": success_rate,
                "blocked": stats.blocked,
                "needs_render": stats.needs_render,
                "not_found": stats.not_found,
                "errors": stats.errors,
                "median_latency_ms": _median_value(stats.durations_ms),
            }
        )

    fetch_cache = {
        "reads": sum(stats.cache_reads for stats in fetch_by_provider.values()),
        "hits": sum(stats.cache_hits for stats in fetch_by_provider.values()),
        "writes": sum(stats.cache_writes for stats in fetch_by_provider.values()),
    }

    extract_summary_by_provider: list[ExtractSummary] = []
    for pid in provider_ids:
        stats = extract_by_provider[pid]
        attempts = stats.attempts
        non_empty_rate = 0.0 if attempts == 0 else stats.non_empty / float(attempts)
        code_block_rate = (
            None
            if stats.code_block_pages == 0
            else stats.code_block_preserved / float(stats.code_block_pages)
        )
        extract_summary_by_provider.append(
            {
                "provider": pid,
                "attempts": attempts,
                "non_empty": stats.non_empty,
                "non_empty_rate": non_empty_rate,
                "median_word_count": _median_value(stats.word_counts),
                "avg_boilerplate_ratio": _average_value(stats.boilerplate_ratios),
                "code_block_pages": stats.code_block_pages,
                "code_block_preserved": stats.code_block_preserved,
                "code_block_preserved_rate": code_block_rate,
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
            "fetch": {"by_provider": fetch_summary_by_provider, "cache": fetch_cache},
            "extract": {"by_provider": extract_summary_by_provider},
        },
        "cases": cases_out,
    }

    return SearchEvalRunResult(report=report, any_error=any_error, any_miss=any_miss)
