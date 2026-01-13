from __future__ import annotations

import argparse
import time

from wstk.cli_support import (
    enforce_robots_policy,
    enforce_url_policy,
    envelope_and_exit,
    wants_json,
    wants_plain,
)
from wstk.commands.support import fetch_settings_from_args
from wstk.errors import ExitCode
from wstk.fetch.http import fetch_url
from wstk.output import CacheMeta, EnvelopeMeta
from wstk.urlutil import redact_url


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
    p.add_argument("--accept", type=str, default=None, help="Accept header")
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

    fetch_settings = fetch_settings_from_args(
        args,
        max_bytes=int(args.max_bytes),
        follow_redirects=bool(args.follow_redirects),
        detect_blocks=bool(args.detect_blocks),
    )
    enforce_robots_policy(
        args=args,
        url=url,
        operation="fetch",
        warnings=warnings,
        user_agent=fetch_settings.headers.get("user-agent"),
    )
    res = fetch_url(url, settings=fetch_settings)

    if wants_plain(args):
        if res.document.artifact and res.document.artifact.body_path:
            print(res.document.artifact.body_path)
        else:
            output_url = res.document.url
            if args.redact:
                output_url = redact_url(output_url)
            print(output_url)
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
        output_url = res.document.url
        if args.redact:
            output_url = redact_url(output_url)
        print(f"HTTP {status} {output_url}")
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
