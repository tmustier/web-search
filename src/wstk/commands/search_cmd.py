from __future__ import annotations

import argparse
import sys
import time

import wstk.search.registry as search_registry
from wstk.cli_support import domain_rules_from_args, envelope_and_exit
from wstk.errors import ExitCode, WstkError
from wstk.output import EnvelopeMeta
from wstk.search.types import SearchQuery, SearchResultItem
from wstk.urlutil import is_allowed, redact_url


def run(*, args: argparse.Namespace, start: float, warnings: list[str]) -> int:
    provider, provider_meta = search_registry.select_search_provider(
        args.provider, timeout=float(args.timeout), proxy=args.proxy
    )
    q = SearchQuery(
        query=str(args.query),
        max_results=int(args.max_results),
        region=args.region,
        safe_search=args.safe_search,
        time_range=args.time_range,
    )
    results = provider.search(q, include_raw=bool(args.include_raw))

    rules = domain_rules_from_args(args)
    if rules.allow or rules.block:
        results = [r for r in results if is_allowed(r.url, rules)]

    if args.redact:
        results = [
            SearchResultItem(
                title=r.title,
                url=redact_url(r.url),
                snippet=r.snippet,
                published_at=r.published_at,
                source_provider=r.source_provider,
                score=r.score,
                raw=r.raw,
            )
            for r in results
        ]

    if args.plain and not (args.json or args.pretty):
        for r in results:
            print(r.url)
        return ExitCode.OK if results else ExitCode.NOT_FOUND

    meta = EnvelopeMeta(duration_ms=int((time.time() - start) * 1000), providers=provider_meta)
    if not results:
        if not (args.json or args.pretty):
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

    if not (args.json or args.pretty):
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
