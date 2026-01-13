from __future__ import annotations

import argparse
import sys
import time

import wstk.search.registry as search_registry
from wstk.cli_support import domain_rules_from_args, envelope_and_exit, wants_json, wants_plain
from wstk.errors import ExitCode, WstkError
from wstk.output import EnvelopeMeta
from wstk.search.types import SearchQuery, SearchResultItem
from wstk.safety import redact_payload, redact_text
from wstk.urlutil import DomainRules, is_allowed, normalize_domains, redact_url


def register(
    subparsers: argparse._SubParsersAction, *, parents: list[argparse.ArgumentParser]
) -> None:
    p = subparsers.add_parser("search", parents=parents, help="Search the web")
    p.set_defaults(_handler=run)

    p.add_argument("query", type=str, help="Search query")
    p.add_argument("-n", "--max-results", type=int, default=10, help="Maximum results")
    p.add_argument("--time-range", type=str, default=None, help="Time range (provider-specific)")
    p.add_argument("--region", type=str, default=None, help="Region code (e.g. us-en)")
    p.add_argument(
        "--safe-search",
        type=str,
        choices=["on", "moderate", "off"],
        default=None,
        help="Safe search mode",
    )
    p.add_argument("--provider", type=str, default="auto", help="Search provider (default: auto)")
    p.add_argument(
        "--site",
        action="append",
        default=[],
        help="Limit results to domain (repeatable; adds site: filter)",
    )
    p.add_argument(
        "--include-raw", action="store_true", help="Include provider raw payload subset in JSON"
    )


def run(*, args: argparse.Namespace, start: float, warnings: list[str]) -> int:
    provider, provider_meta = search_registry.select_search_provider(
        args.provider, timeout=float(args.timeout), proxy=args.proxy
    )
    search_registry.append_provider_warnings(warnings, provider.id)
    site_domains = _site_domains_from_args(args)
    query_text = _augment_query_with_sites(str(args.query), site_domains)
    q = SearchQuery(
        query=query_text,
        max_results=int(args.max_results),
        region=args.region,
        safe_search=args.safe_search,
        time_range=args.time_range,
    )
    results = provider.search(q, include_raw=bool(args.include_raw))

    rules = domain_rules_from_args(args)
    if site_domains:
        rules = DomainRules(allow=(*rules.allow, *site_domains), block=rules.block)
    if rules.allow or rules.block:
        results = [r for r in results if is_allowed(r.url, rules)]

    if args.redact:
        results = [
            SearchResultItem(
                title=redact_text(r.title),
                url=redact_url(r.url),
                snippet=redact_text(r.snippet) if r.snippet else None,
                published_at=r.published_at,
                source_provider=r.source_provider,
                score=r.score,
                raw=redact_payload(r.raw) if r.raw else None,
            )
            for r in results
        ]

    if wants_plain(args):
        for r in results:
            print(r.url)
        return ExitCode.OK if results else ExitCode.NOT_FOUND

    meta = EnvelopeMeta(duration_ms=int((time.time() - start) * 1000), providers=provider_meta)
    if not results:
        if not wants_json(args):
            print("no results", file=sys.stderr)
            return ExitCode.NOT_FOUND
        err = WstkError(code="not_found", message="no results", exit_code=ExitCode.NOT_FOUND)
        return envelope_and_exit(
            args=args,
            command="search",
            ok=False,
            data={"results": []},
            warnings=warnings,
            error=err,
            meta=meta,
        )

    if not wants_json(args):
        for idx, r in enumerate(results, start=1):
            print(f"{idx}. {r.title}")
            print(f"   {r.url}")
            if r.snippet:
                print(f"   {r.snippet}")
        return ExitCode.OK

    return envelope_and_exit(
        args=args,
        command="search",
        ok=True,
        data={"results": [r.to_dict() for r in results]},
        warnings=warnings,
        error=None,
        meta=meta,
    )


def _site_domains_from_args(args: argparse.Namespace) -> tuple[str, ...]:
    return normalize_domains(getattr(args, "site", []) or [])


def _augment_query_with_sites(query: str, sites: tuple[str, ...]) -> str:
    query_text = query.strip()
    if not sites:
        return query_text
    if len(sites) == 1:
        suffix = f"site:{sites[0]}"
    else:
        joined = " OR ".join(f"site:{site}" for site in sites)
        suffix = f"({joined})"
    if not query_text:
        return suffix
    return f"{query_text} {suffix}"
