from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass

import wstk.search.registry as search_registry
from wstk.cli_support import (
    append_warning,
    domain_rules_from_args,
    enforce_robots_policy,
    enforce_url_policy,
    envelope_and_exit,
    wants_json,
    wants_plain,
)
from wstk.commands.support import fetch_settings_from_args, render_settings_from_args
from wstk.errors import ExitCode, WstkError
from wstk.extract.utils import (
    choose_strategy,
    extract_html,
    select_extracted_output,
    text_for_scan,
)
from wstk.fetch.http import FetchSettings, fetch_url
from wstk.models import Document
from wstk.output import EnvelopeMeta
from wstk.render.browser import render_url
from wstk.safety import detect_prompt_injection, redact_text
from wstk.search.types import SearchQuery, SearchResultItem
from wstk.urlutil import get_host, host_matches_domain, is_allowed, redact_url


@dataclass(frozen=True, slots=True)
class Candidate:
    rank: int
    item: SearchResultItem
    preferred_domain: str | None


def register(
    subparsers: argparse._SubParsersAction, *, parents: list[argparse.ArgumentParser]
) -> None:
    p = subparsers.add_parser(
        "pipeline",
        parents=parents,
        help="Search then extract top results",
    )
    p.set_defaults(_handler=run)

    p.add_argument("query", type=str, help="Search query")
    p.add_argument("--top-k", type=int, default=5, help="Search results to consider")
    p.add_argument("--extract-k", type=int, default=1, help="Results to extract")
    p.add_argument("--method", choices=["http", "browser", "auto"], default="http")
    p.add_argument("--escalate", choices=["none", "render"], default="none")
    p.add_argument("--plan", action="store_true", help="Return candidate plan only")
    p.add_argument(
        "--prefer-domain",
        "--prefer-domains",
        action="append",
        default=[],
        help="Prefer domains when selecting candidates (repeatable)",
    )
    p.add_argument("--provider", type=str, default="auto", help="Search provider")
    p.add_argument("--time-range", type=str, default=None, help="Time range (provider-specific)")
    p.add_argument("--region", type=str, default=None, help="Region code (e.g. us-en)")
    p.add_argument(
        "--safe-search",
        type=str,
        choices=["on", "moderate", "off"],
        default=None,
        help="Safe search mode",
    )
    p.add_argument(
        "--budget",
        type=str,
        default=None,
        help="Budget hint (future; not enforced)",
    )


def run(*, args: argparse.Namespace, start: float, warnings: list[str]) -> int:
    top_k = int(args.top_k)
    extract_k = int(args.extract_k)
    if top_k <= 0 or extract_k <= 0:
        raise WstkError(
            code="invalid_usage",
            message="--top-k and --extract-k must be >= 1",
            exit_code=ExitCode.INVALID_USAGE,
        )

    method = str(args.method)
    if method == "auto" and args.policy != "permissive":
        raise WstkError(
            code="policy_violation",
            message="auto browser escalation requires --policy permissive",
            exit_code=ExitCode.INVALID_USAGE,
        )
    if args.escalate != "none":
        raise WstkError(
            code="invalid_usage",
            message="--escalate is not implemented yet; use --method browser",
            exit_code=ExitCode.INVALID_USAGE,
        )
    if args.budget:
        append_warning(warnings, "--budget is not enforced in v0.1.0")

    provider, provider_meta = search_registry.select_search_provider(
        args.provider, timeout=float(args.timeout), proxy=args.proxy
    )
    provider_id = provider_meta[0] if provider_meta else provider.id
    search_registry.append_provider_warnings(warnings, provider_id)

    query = SearchQuery(
        query=str(args.query),
        max_results=top_k,
        region=args.region,
        safe_search=args.safe_search,
        time_range=args.time_range,
    )
    results = provider.search(query, include_raw=False)

    rules = domain_rules_from_args(args)
    if rules.allow or rules.block:
        results = [r for r in results if is_allowed(r.url, rules)]
    results = results[:top_k]

    if not results:
        return _handle_no_results(args, start, warnings, [provider_id])

    prefer_domains = tuple(str(domain) for domain in (args.prefer_domain or []))
    candidates = _select_candidates(results, extract_k, prefer_domains)
    candidate_payload = [_candidate_payload(candidate) for candidate in candidates]

    if args.plan:
        return _emit_plan_output(
            args=args,
            results=results,
            candidates=candidates,
            candidate_payload=candidate_payload,
            start=start,
            warnings=warnings,
            providers=[provider_id],
        )

    fetch_settings = None
    if method in {"http", "auto"}:
        fetch_settings = fetch_settings_from_args(
            args,
            max_bytes=5 * 1024 * 1024,
            follow_redirects=True,
            detect_blocks=True,
        )

    evidence_dir = None

    documents: list[Document] = []
    provider_chain = [provider_id]
    for candidate in candidates:
        doc, doc_providers = _extract_candidate(
            candidate,
            args=args,
            method=method,
            fetch_settings=fetch_settings,
            evidence_dir=evidence_dir,
            warnings=warnings,
        )
        documents.append(doc)
        _extend_unique(provider_chain, doc_providers)

    if wants_plain(args):
        return _emit_plain_documents(args, documents)

    if not wants_json(args):
        return _emit_human_documents(args, documents)

    meta = EnvelopeMeta(duration_ms=int((time.time() - start) * 1000), providers=provider_chain)
    return envelope_and_exit(
        args=args,
        command="pipeline",
        ok=True,
        data={
            "query": str(args.query),
            "results": [r.to_dict() for r in results],
            "candidates": candidate_payload,
            "documents": [doc.to_dict() for doc in documents],
        },
        warnings=warnings,
        error=None,
        meta=meta,
    )


def _select_candidates(
    results: list[SearchResultItem],
    extract_k: int,
    prefer_domains: tuple[str, ...],
) -> list[Candidate]:
    ranked = list(enumerate(results, start=1))
    preferred: list[Candidate] = []
    remaining: list[Candidate] = []
    for rank, item in ranked:
        preferred_domain = _match_preferred_domain(item.url, prefer_domains)
        candidate = Candidate(rank=rank, item=item, preferred_domain=preferred_domain)
        if preferred_domain:
            preferred.append(candidate)
        else:
            remaining.append(candidate)
    ordered = preferred + remaining
    return ordered[:extract_k]


def _match_preferred_domain(url: str, prefer_domains: tuple[str, ...]) -> str | None:
    if not prefer_domains:
        return None
    host = get_host(url)
    if not host:
        return None
    for domain in prefer_domains:
        if host_matches_domain(host, domain):
            return domain
    return None


def _candidate_payload(candidate: Candidate) -> dict[str, object]:
    payload: dict[str, object] = {
        "rank": candidate.rank,
        "title": candidate.item.title,
        "url": candidate.item.url,
        "snippet": candidate.item.snippet,
        "published_at": candidate.item.published_at,
        "source_provider": candidate.item.source_provider,
        "score": candidate.item.score,
        "reason": "preferred_domain" if candidate.preferred_domain else "top_rank",
    }
    if candidate.preferred_domain:
        payload["preferred_domain"] = candidate.preferred_domain
    return payload


def _extract_candidate(
    candidate: Candidate,
    *,
    args: argparse.Namespace,
    method: str,
    fetch_settings: FetchSettings | None,
    evidence_dir,
    warnings: list[str],
) -> tuple[Document, list[str]]:
    url = candidate.item.url
    enforce_url_policy(args=args, url=url, operation="pipeline")

    html = ""
    base_doc: Document | None = None
    providers: list[str] = []
    robots_checked = False

    if method in {"http", "auto"}:
        if fetch_settings is None:
            raise WstkError(
                code="invalid_usage",
                message="http fetch settings unavailable",
                exit_code=ExitCode.INVALID_USAGE,
            )
        enforce_robots_policy(
            args=args,
            url=url,
            operation="pipeline",
            warnings=warnings,
            user_agent=fetch_settings.headers.get("user-agent"),
        )
        robots_checked = True
        try:
            res = fetch_url(url, settings=fetch_settings)
        except WstkError as exc:
            if method == "auto" and exc.code == "needs_render":
                method = "browser"
            else:
                raise
        else:
            html = res.body.decode("utf-8", errors="replace")
            base_doc = res.document

    if method == "browser":
        if not robots_checked:
            enforce_robots_policy(
                args=args,
                url=url,
                operation="pipeline",
                warnings=warnings,
            )
        render_settings = render_settings_from_args(
            args,
            evidence_dir=evidence_dir,
            wait_ms=0,
            wait_for=None,
            headful=False,
            screenshot=False,
            profile_dir=None,
            profile_label=None,
        )
        render_result = render_url(url, settings=render_settings)
        html = render_result.html
        base_doc = render_result.document

    if base_doc is None:
        raise WstkError(
            code="pipeline_failed",
            message="pipeline did not produce a document",
            exit_code=ExitCode.RUNTIME_ERROR,
        )

    strategy = choose_strategy(html)
    extracted = extract_html(
        html,
        strategy=strategy,
        include_markdown=True,
        include_text=True,
    )

    injection_hits = detect_prompt_injection(text_for_scan(extracted))
    if injection_hits:
        append_warning(
            warnings,
            "possible prompt injection patterns detected: " + ", ".join(injection_hits),
        )

    doc = base_doc.with_extracted(extracted)

    if base_doc.fetch_method == "http":
        providers.append("http")
    elif base_doc.fetch_method == "browser":
        providers.append("browser")
    providers.append(strategy)

    return doc, providers


def _emit_plan_output(
    *,
    args: argparse.Namespace,
    results: list[SearchResultItem],
    candidates: list[Candidate],
    candidate_payload: list[dict[str, object]],
    start: float,
    warnings: list[str],
    providers: list[str],
) -> int:
    if wants_plain(args):
        for candidate in candidates:
            url = candidate.item.url
            if args.redact:
                url = redact_url(url)
            print(url)
        return ExitCode.OK if candidates else ExitCode.NOT_FOUND

    if not wants_json(args):
        for candidate in candidates:
            url = candidate.item.url
            if args.redact:
                url = redact_url(url)
            label = "preferred" if candidate.preferred_domain else "ranked"
            suffix = f" ({label})"
            print(f"{candidate.rank}. {url}{suffix}")
        return ExitCode.OK if candidates else ExitCode.NOT_FOUND

    meta = EnvelopeMeta(duration_ms=int((time.time() - start) * 1000), providers=providers)
    return envelope_and_exit(
        args=args,
        command="pipeline",
        ok=True,
        data={
            "query": str(args.query),
            "results": [r.to_dict() for r in results],
            "candidates": candidate_payload,
            "documents": [],
        },
        warnings=warnings,
        error=None,
        meta=meta,
    )


def _emit_plain_documents(args: argparse.Namespace, documents: list[Document]) -> int:
    outputs: list[str] = []
    for doc in documents:
        extracted = doc.extracted
        if extracted is None:
            continue
        content = select_extracted_output(extracted, prefer_markdown=True)
        if args.redact and content:
            content = redact_text(content)
        if content:
            outputs.append(content)

    if not outputs:
        return ExitCode.NOT_FOUND

    sys.stdout.write("\n\n---\n\n".join(outputs))
    if not outputs[-1].endswith("\n"):
        sys.stdout.write("\n")
    return ExitCode.OK


def _emit_human_documents(args: argparse.Namespace, documents: list[Document]) -> int:
    if not documents:
        print("no results", file=sys.stderr)
        return ExitCode.NOT_FOUND

    for idx, doc in enumerate(documents, start=1):
        url = doc.url
        if args.redact:
            url = redact_url(url)
        print(f"[{idx}] {url}")
        extracted = doc.extracted
        content = ""
        if extracted is not None:
            content = select_extracted_output(extracted, prefer_markdown=True)
        if args.redact and content:
            content = redact_text(content)
        if content:
            sys.stdout.write(content)
            if not content.endswith("\n"):
                sys.stdout.write("\n")
        if idx < len(documents):
            print("\n---\n")
    return ExitCode.OK


def _handle_no_results(
    args: argparse.Namespace,
    start: float,
    warnings: list[str],
    providers: list[str],
) -> int:
    if wants_plain(args):
        return ExitCode.NOT_FOUND
    if not wants_json(args):
        print("no results", file=sys.stderr)
        return ExitCode.NOT_FOUND
    err = WstkError(code="not_found", message="no results", exit_code=ExitCode.NOT_FOUND)
    meta = EnvelopeMeta(duration_ms=int((time.time() - start) * 1000), providers=providers)
    return envelope_and_exit(
        args=args,
        command="pipeline",
        ok=False,
        data={"results": [], "documents": [], "candidates": []},
        warnings=warnings,
        error=err,
        meta=meta,
    )


def _extend_unique(values: list[str], extra: list[str]) -> None:
    for value in extra:
        if value not in values:
            values.append(value)
