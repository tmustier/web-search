from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from wstk import __version__
from wstk.cache import Cache, CacheSettings
from wstk.errors import ExitCode, WstkError
from wstk.extract.readability_extractor import extract_readability
from wstk.fetch.http import FetchSettings, fetch_url
from wstk.output import CacheMeta, EnvelopeMeta, make_envelope, print_json
from wstk.search.registry import list_search_providers, select_search_provider
from wstk.search.types import SearchQuery
from wstk.timeutil import parse_duration
from wstk.urlutil import DomainRules, is_allowed, redact_url


def build_parser() -> argparse.ArgumentParser:
    global_parser = argparse.ArgumentParser(add_help=False)
    global_parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    global_parser.add_argument(
        "--pretty", action="store_true", help="Pretty-print JSON (implies --json)"
    )
    global_parser.add_argument("--plain", action="store_true", help="Stable text output for piping")
    global_parser.add_argument("--quiet", action="store_true", help="Reduce non-essential output")
    global_parser.add_argument(
        "--verbose", action="store_true", help="Verbose diagnostics to stderr"
    )
    global_parser.add_argument("--no-color", action="store_true", help="Disable ANSI color output")
    global_parser.add_argument(
        "--no-input",
        action="store_true",
        help="Never prompt or open interactive flows; fail with actionable diagnostics",
    )
    global_parser.add_argument(
        "--timeout", type=float, default=15.0, help="Network timeout in seconds"
    )
    global_parser.add_argument("--proxy", type=str, default=None, help="HTTP(S) proxy URL")
    global_parser.add_argument(
        "--cache-dir", type=str, default="~/.cache/wstk", help="Cache directory"
    )
    global_parser.add_argument("--no-cache", action="store_true", help="Disable cache")
    global_parser.add_argument("--fresh", action="store_true", help="Bypass cache reads")
    global_parser.add_argument(
        "--cache-max-mb", type=int, default=1024, help="Cache size budget in MB"
    )
    global_parser.add_argument(
        "--cache-ttl", type=str, default="7d", help="Cache TTL (e.g. 24h, 7d)"
    )
    global_parser.add_argument(
        "--evidence-dir", type=str, default=None, help="Evidence directory (optional)"
    )
    global_parser.add_argument(
        "--redact", action="store_true", help="Redact query strings from URLs in output"
    )
    global_parser.add_argument(
        "--robots",
        choices=["warn", "respect", "ignore"],
        default="warn",
        help="robots.txt stance (default: warn)",
    )
    global_parser.add_argument(
        "--allow-domain",
        action="append",
        default=[],
        help="Allow domain (repeatable); restricts network operations",
    )
    global_parser.add_argument(
        "--block-domain",
        action="append",
        default=[],
        help="Block domain (repeatable); restricts network operations",
    )
    global_parser.add_argument(
        "--policy",
        choices=["standard", "strict", "permissive"],
        default="standard",
        help="Policy mode (default: standard)",
    )

    parser = argparse.ArgumentParser(prog="wstk", parents=[global_parser], add_help=True)
    parser.add_argument("--version", action="version", version=__version__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("providers", parents=[global_parser], help="List available providers")

    search_p = subparsers.add_parser("search", parents=[global_parser], help="Search the web")
    search_p.add_argument("query", type=str, help="Search query")
    search_p.add_argument("-n", "--max-results", type=int, default=10, help="Maximum results")
    search_p.add_argument(
        "--time-range", type=str, default=None, help="Time range (provider-specific)"
    )
    search_p.add_argument("--region", type=str, default=None, help="Region code (e.g. us-en)")
    search_p.add_argument(
        "--safe-search",
        type=str,
        choices=["on", "moderate", "off"],
        default=None,
        help="Safe search mode",
    )
    search_p.add_argument(
        "--provider", type=str, default="auto", help="Search provider (default: auto)"
    )
    search_p.add_argument(
        "--include-raw", action="store_true", help="Include provider raw payload subset in JSON"
    )

    fetch_p = subparsers.add_parser("fetch", parents=[global_parser], help="Fetch a URL over HTTP")
    fetch_p.add_argument("url", type=str, help="URL to fetch")
    fetch_p.add_argument(
        "--header", action="append", default=[], help="Extra header (repeatable): key:value"
    )
    fetch_p.add_argument(
        "--headers-file", type=str, default=None, help="JSON object of headers (path or '-')"
    )
    fetch_p.add_argument("--user-agent", type=str, default=None, help="User-Agent header")
    fetch_p.add_argument("--accept-language", type=str, default=None, help="Accept-Language header")
    fetch_p.add_argument(
        "--max-bytes", type=int, default=5 * 1024 * 1024, help="Max response bytes"
    )
    fetch_p.add_argument(
        "--follow-redirects", action="store_true", default=True, help="Follow redirects"
    )
    fetch_p.add_argument(
        "--no-follow-redirects",
        action="store_false",
        dest="follow_redirects",
        help="Do not follow redirects",
    )
    fetch_p.add_argument(
        "--detect-blocks", action="store_true", default=True, help="Heuristics for bot walls/JS"
    )
    fetch_p.add_argument(
        "--no-detect-blocks", action="store_false", dest="detect_blocks", help="Disable heuristics"
    )
    fetch_p.add_argument("--include-body", action="store_true", help="Include body in JSON (debug)")

    extract_p = subparsers.add_parser(
        "extract", parents=[global_parser], help="Extract readable content"
    )
    extract_p.add_argument("target", type=str, help="URL, path, or '-' for stdin")
    extract_p.add_argument("--strategy", choices=["auto", "readability", "docs"], default="auto")
    extract_p.add_argument("--method", choices=["http", "browser", "auto"], default="http")
    out_group = extract_p.add_mutually_exclusive_group()
    out_group.add_argument("--markdown", action="store_true", help="Output markdown only")
    out_group.add_argument("--text", action="store_true", help="Output text only")
    out_group.add_argument("--both", action="store_true", help="Output both markdown and text")
    extract_p.add_argument("--max-chars", type=int, default=0, help="Truncate extracted output")
    extract_p.add_argument(
        "--include-html", action="store_true", help="Include HTML in JSON (debug)"
    )

    return parser


def _domain_rules_from_args(args: argparse.Namespace) -> DomainRules:
    allow = tuple(getattr(args, "allow_domain", []) or [])
    block = tuple(getattr(args, "block_domain", []) or [])
    return DomainRules(allow=allow, block=block)


def _cache_from_args(args: argparse.Namespace) -> Cache:
    cache_dir = Path(str(args.cache_dir)).expanduser()
    ttl = parse_duration(str(args.cache_ttl))
    max_mb = int(args.cache_max_mb)
    enabled = not bool(args.no_cache)
    fresh = bool(args.fresh)
    return Cache(
        CacheSettings(cache_dir=cache_dir, ttl=ttl, max_mb=max_mb, enabled=enabled, fresh=fresh)
    )


def _default_headers(args: argparse.Namespace) -> dict[str, str]:
    headers: dict[str, str] = {
        "accept": "text/html,*/*",
        "accept-language": "en-US,en;q=0.9",
        "user-agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }
    if getattr(args, "user_agent", None):
        headers["user-agent"] = str(args.user_agent)
    if getattr(args, "accept_language", None):
        headers["accept-language"] = str(args.accept_language)
    return headers


def _parse_headers(args: argparse.Namespace) -> dict[str, str]:
    restricted = {"authorization", "cookie", "set-cookie"}
    headers = _default_headers(args)

    def add_header(k: str, v: str) -> None:
        key = k.strip().lower()
        if key in restricted:
            raise WstkError(
                code="invalid_header",
                message=f"refusing to set restricted header: {k}",
                exit_code=ExitCode.INVALID_USAGE,
            )
        headers[key] = v.strip()

    for entry in getattr(args, "header", []) or []:
        if ":" not in entry:
            raise WstkError(
                code="invalid_header",
                message=f"invalid --header value: {entry!r} (expected key:value)",
                exit_code=ExitCode.INVALID_USAGE,
            )
        k, v = entry.split(":", 1)
        add_header(k, v)

    headers_file = getattr(args, "headers_file", None)
    if headers_file:
        content = (
            sys.stdin.read()
            if headers_file == "-"
            else Path(headers_file).read_text(encoding="utf-8")
        )
        parsed = json.loads(content)
        if not isinstance(parsed, dict):
            raise WstkError(
                code="invalid_headers",
                message="--headers-file must contain a JSON object",
                exit_code=ExitCode.INVALID_USAGE,
            )
        for k, v in parsed.items():
            add_header(str(k), str(v))

    return headers


def _print_envelope(args: argparse.Namespace, payload: dict) -> None:
    use_json = bool(args.json or args.pretty)
    if not use_json:
        return
    print_json(payload, pretty=bool(args.pretty))


def _envelope_and_exit(
    *,
    args: argparse.Namespace,
    command: str,
    ok: bool,
    data: object,
    warnings: list[str],
    error: WstkError | None,
    meta: EnvelopeMeta,
) -> int:
    payload = make_envelope(
        ok=ok,
        command=command,
        version=__version__,
        data=data,
        warnings=warnings,
        error=None if error is None else error.to_error_dict(),
        meta=meta,
    )
    _print_envelope(args, payload)
    return ExitCode.OK if ok else (error.exit_code if error is not None else ExitCode.RUNTIME_ERROR)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    command = str(args.command)
    start = time.time()
    warnings: list[str] = []

    try:
        if command == "providers":
            providers = []

            for p in list_search_providers(timeout=float(args.timeout), proxy=args.proxy):
                enabled, reason = p.is_enabled()
                providers.append(
                    {
                        "id": p.id,
                        "type": "search",
                        "enabled": enabled,
                        "reason": reason,
                        "required_env": ["BRAVE_API_KEY"] if p.id == "brave_api" else [],
                    }
                )

            providers.append(
                {"id": "http", "type": "fetch", "enabled": True, "reason": None, "required_env": []}
            )
            providers.append(
                {
                    "id": "readability",
                    "type": "extract",
                    "enabled": True,
                    "reason": None,
                    "required_env": [],
                }
            )

            if args.plain and not (args.json or args.pretty):
                for item in providers:
                    print(item["id"])
                return ExitCode.OK

            if not (args.json or args.pretty):
                for item in providers:
                    status = "enabled" if item["enabled"] else f"disabled ({item['reason']})"
                    print(f"{item['type']}: {item['id']} - {status}")
                return ExitCode.OK

            meta = EnvelopeMeta(
                duration_ms=int((time.time() - start) * 1000),
                providers=[p["id"] for p in providers],
            )
            return _envelope_and_exit(
                args=args,
                command=command,
                ok=True,
                data={"providers": providers},
                warnings=warnings,
                error=None,
                meta=meta,
            )

        if command == "search":
            provider, provider_meta = select_search_provider(
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

            rules = _domain_rules_from_args(args)
            if rules.allow or rules.block:
                results = [r for r in results if is_allowed(r.url, rules)]

            if args.redact:
                results = [
                    type(r)(
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

            meta = EnvelopeMeta(
                duration_ms=int((time.time() - start) * 1000), providers=provider_meta
            )
            if not results:
                if not (args.json or args.pretty):
                    print("no results", file=sys.stderr)
                    return ExitCode.NOT_FOUND
                err = WstkError(
                    code="not_found", message="no results", exit_code=ExitCode.NOT_FOUND
                )
                return _envelope_and_exit(
                    args=args,
                    command=command,
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

            return _envelope_and_exit(
                args=args,
                command=command,
                ok=True,
                data={"results": [r.to_dict() for r in results]},
                warnings=warnings,
                error=None,
                meta=meta,
            )

        if command == "fetch":
            url = str(args.url)
            rules = _domain_rules_from_args(args)
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

            headers = _parse_headers(args)
            cache = _cache_from_args(args)
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
                hit=res.cache_hit is not None, key=res.cache_hit.key if res.cache_hit else None
            )

            doc_dict = res.document.to_dict()
            if args.include_body:
                doc_dict["body"] = res.body.decode("utf-8", errors="replace")

            meta = EnvelopeMeta(
                duration_ms=int((time.time() - start) * 1000), cache=cache_meta, providers=["http"]
            )

            if not (args.json or args.pretty):
                http_info = res.document.http
                artifact = res.document.artifact
                status = http_info.status if http_info else "unknown"
                print(f"HTTP {status} {res.document.url}")
                if artifact and artifact.body_path:
                    print(f"body: {artifact.body_path}")
                return ExitCode.OK

            return _envelope_and_exit(
                args=args,
                command=command,
                ok=True,
                data={"document": doc_dict},
                warnings=warnings,
                error=None,
                meta=meta,
            )

        if command == "extract":
            target = str(args.target)

            include_markdown = bool(
                args.markdown
                or args.both
                or (not args.text and not args.markdown and not args.both)
            )
            include_text = bool(
                args.text or args.both or (not args.text and not args.markdown and not args.both)
            )

            if args.strategy == "docs":
                raise WstkError(
                    code="not_implemented",
                    message="docs extraction strategy not implemented yet",
                    exit_code=ExitCode.RUNTIME_ERROR,
                )

            if args.method == "browser":
                raise WstkError(
                    code="not_implemented",
                    message="browser method not implemented yet",
                    exit_code=ExitCode.RUNTIME_ERROR,
                )

            rules = _domain_rules_from_args(args)
            cache_meta = None
            if target.startswith(("http://", "https://")):
                if args.policy == "strict" and not rules.allow:
                    raise WstkError(
                        code="policy_violation",
                        message="strict policy requires --allow-domain for network extract",
                        exit_code=ExitCode.INVALID_USAGE,
                    )
                if (rules.allow or rules.block) and not is_allowed(target, rules):
                    raise WstkError(
                        code="domain_blocked",
                        message="URL blocked by domain rules",
                        exit_code=ExitCode.INVALID_USAGE,
                        details={"url": target},
                    )

                headers = _parse_headers(args)
                cache = _cache_from_args(args)
                fetch_settings = FetchSettings(
                    timeout=float(args.timeout),
                    proxy=args.proxy,
                    headers=headers,
                    max_bytes=5 * 1024 * 1024,
                    follow_redirects=True,
                    detect_blocks=True,
                    cache=cache,
                )
                res = fetch_url(target, settings=fetch_settings)
                html = res.body.decode("utf-8", errors="replace")
                base_doc = res.document
                cache_meta = CacheMeta(
                    hit=res.cache_hit is not None, key=res.cache_hit.key if res.cache_hit else None
                )
            else:
                base_doc = None
                if target == "-":
                    html = sys.stdin.read()
                else:
                    html = Path(target).read_text(encoding="utf-8")

            extracted = extract_readability(
                html, include_markdown=include_markdown, include_text=include_text
            )

            if args.max_chars and args.max_chars > 0:
                markdown = extracted.markdown[: args.max_chars] if extracted.markdown else None
                text = extracted.text[: args.max_chars] if extracted.text else None
                extracted = type(extracted)(
                    title=extracted.title,
                    language=extracted.language,
                    extraction_method=extracted.extraction_method,
                    markdown=markdown,
                    text=text,
                )

            if args.plain and not (args.json or args.pretty):
                if args.text and extracted.text:
                    sys.stdout.write(extracted.text)
                    if not extracted.text.endswith("\n"):
                        sys.stdout.write("\n")
                    return ExitCode.OK
                if args.markdown and extracted.markdown:
                    sys.stdout.write(extracted.markdown)
                    if not extracted.markdown.endswith("\n"):
                        sys.stdout.write("\n")
                    return ExitCode.OK
                content = extracted.markdown or extracted.text or ""
                sys.stdout.write(content)
                if content and not content.endswith("\n"):
                    sys.stdout.write("\n")
                return ExitCode.OK if content else ExitCode.NOT_FOUND

            if not (args.json or args.pretty):
                # Default human output: print extracted content to stdout.
                content = extracted.markdown if include_markdown else extracted.text
                content = content or extracted.text or extracted.markdown or ""
                sys.stdout.write(content)
                if content and not content.endswith("\n"):
                    sys.stdout.write("\n")
                return ExitCode.OK if content else ExitCode.NOT_FOUND

            if base_doc is None:
                meta = EnvelopeMeta(
                    duration_ms=int((time.time() - start) * 1000), providers=["readability"]
                )
                return _envelope_and_exit(
                    args=args,
                    command=command,
                    ok=True,
                    data={"extracted": extracted.to_dict()},
                    warnings=warnings,
                    error=None,
                    meta=meta,
                )

            doc_dict = base_doc.to_dict()
            doc_dict["extracted"] = extracted.to_dict()
            if args.include_html:
                doc_dict["html"] = html

            meta = EnvelopeMeta(
                duration_ms=int((time.time() - start) * 1000),
                cache=cache_meta,
                providers=["http", "readability"],
            )
            return _envelope_and_exit(
                args=args,
                command=command,
                ok=True,
                data={"document": doc_dict},
                warnings=warnings,
                error=None,
                meta=meta,
            )

        raise WstkError(
            code="invalid_usage",
            message=f"unknown command: {command}",
            exit_code=ExitCode.INVALID_USAGE,
        )
    except WstkError as e:
        meta = EnvelopeMeta(duration_ms=int((time.time() - start) * 1000))
        if args.json or args.pretty:
            return _envelope_and_exit(
                args=args,
                command=command,
                ok=False,
                data={},
                warnings=warnings,
                error=e,
                meta=meta,
            )
        print(f"error: {e.message}", file=sys.stderr)
        if e.details and args.verbose:
            print(f"details: {e.details}", file=sys.stderr)
        return e.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
