from __future__ import annotations

import argparse
import time

from wstk.cli_support import (
    cache_from_args,
    domain_rules_from_args,
    envelope_and_exit,
    parse_headers,
)
from wstk.errors import ExitCode, WstkError
from wstk.fetch.http import FetchSettings, fetch_url
from wstk.output import CacheMeta, EnvelopeMeta
from wstk.urlutil import is_allowed


def run(*, args: argparse.Namespace, start: float, warnings: list[str]) -> int:
    url = str(args.url)
    rules = domain_rules_from_args(args)
    if args.policy == "strict" and not rules.allow:
        raise WstkError(
            code="policy_violation",
            message="strict policy requires --allow-domain for network fetch",
            exit_code=ExitCode.INVALID_USAGE,
        )
    if (rules.allow or rules.block) and not is_allowed(url, rules):
        raise WstkError(
            code="domain_blocked",
            message="URL blocked by domain rules",
            exit_code=ExitCode.INVALID_USAGE,
            details={"url": url},
        )

    headers = parse_headers(args)
    cache = cache_from_args(args)
    fetch_settings = FetchSettings(
        timeout=float(args.timeout),
        proxy=args.proxy,
        headers=headers,
        max_bytes=int(args.max_bytes),
        follow_redirects=bool(args.follow_redirects),
        detect_blocks=bool(args.detect_blocks),
        cache=cache,
    )
    res = fetch_url(url, settings=fetch_settings)

    if args.plain and not (args.json or args.pretty):
        if res.document.artifact and res.document.artifact.body_path:
            print(res.document.artifact.body_path)
        else:
            print(res.document.url)
        return ExitCode.OK

    cache_meta = CacheMeta(
        hit=res.cache_hit is not None,
        key=res.cache_hit.key if res.cache_hit else None,
    )
    doc_dict = res.document.to_dict()
    if args.include_body:
        doc_dict["body"] = res.body.decode("utf-8", errors="replace")

    meta = EnvelopeMeta(
        duration_ms=int((time.time() - start) * 1000),
        cache=cache_meta,
        providers=["http"],
    )

    if not (args.json or args.pretty):
        http_info = res.document.http
        artifact = res.document.artifact
        status = http_info.status if http_info else "unknown"
        print(f"HTTP {status} {res.document.url}")
        if artifact and artifact.body_path:
            print(f"body: {artifact.body_path}")
        return ExitCode.OK

    return envelope_and_exit(
        args=args,
        command="fetch",
        ok=True,
        data={"document": doc_dict},
        warnings=warnings,
        error=None,
        meta=meta,
    )
