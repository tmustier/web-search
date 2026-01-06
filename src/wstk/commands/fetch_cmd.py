from __future__ import annotations

import argparse
import time

from wstk.cli_support import (
    cache_from_args,
    enforce_url_policy,
    envelope_and_exit,
    parse_headers,
    wants_json,
    wants_plain,
)
from wstk.errors import ExitCode
from wstk.fetch.http import FetchSettings, fetch_url
from wstk.output import CacheMeta, EnvelopeMeta


def register(
    subparsers: argparse._SubParsersAction, *, parents: list[argparse.ArgumentParser]
) -> None:
    p = subparsers.add_parser("fetch", parents=parents, help="Fetch a URL over HTTP")
    p.set_defaults(_handler=run)

    p.add_argument("url", type=str, help="URL to fetch")
    p.add_argument("--header", action="append", default=[], help="Extra header: key:value")
    p.add_argument(
        "--headers-file",
        type=str,
        default=None,
        help="JSON object of headers (path or '-')",
    )
    p.add_argument("--user-agent", type=str, default=None, help="User-Agent header")
    p.add_argument("--accept-language", type=str, default=None, help="Accept-Language header")
    p.add_argument(
        "--max-bytes",
        type=int,
        default=5 * 1024 * 1024,
        help="Max response bytes",
    )
    p.add_argument("--follow-redirects", action="store_true", default=True, help="Follow redirects")
    p.add_argument(
        "--no-follow-redirects",
        action="store_false",
        dest="follow_redirects",
        help="Do not follow redirects",
    )
    p.add_argument(
        "--detect-blocks",
        action="store_true",
        default=True,
        help="Heuristics for bot walls/JS",
    )
    p.add_argument(
        "--no-detect-blocks",
        action="store_false",
        dest="detect_blocks",
        help="Disable heuristics",
    )
    p.add_argument("--include-body", action="store_true", help="Include body in JSON (debug)")


def run(*, args: argparse.Namespace, start: float, warnings: list[str]) -> int:
    url = str(args.url)
    enforce_url_policy(args=args, url=url, operation="fetch")

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

    if wants_plain(args):
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

    if not wants_json(args):
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
