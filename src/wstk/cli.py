from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlencode

from wstk import __version__
from wstk.cache import Cache, CacheSettings, make_cache_key
from wstk.errors import ExitCode, WstkError
from wstk.eval.scoring import normalize_url_for_match, score_search_results
from wstk.eval.suite import EvalCase, load_suite
from wstk.extract.readability_extractor import extract_readability
from wstk.fetch.http import FetchSettings, fetch_url
from wstk.output import CacheMeta, EnvelopeMeta, make_envelope, print_json
from wstk.search.base import SearchProvider
from wstk.search.registry import list_search_providers, select_search_provider
from wstk.search.types import SearchQuery, SearchResultItem
from wstk.timeutil import parse_duration
from wstk.urlutil import DomainRules, is_allowed, redact_url


def _add_global_flags(parser: argparse.ArgumentParser, *, suppress_defaults: bool) -> None:
    def default(value):
        return argparse.SUPPRESS if suppress_defaults else value

    parser.add_argument(
        "--json",
        action="store_true",
        default=default(False),
        help="Output machine-readable JSON",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        default=default(False),
        help="Pretty-print JSON (implies --json)",
    )
    parser.add_argument(
        "--plain",
        action="store_true",
        default=default(False),
        help="Stable text output for piping",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        default=default(False),
        help="Reduce non-essential output",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=default(False),
        help="Verbose diagnostics to stderr",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        default=default(False),
        help="Disable ANSI color output",
    )
    parser.add_argument(
        "--no-input",
        action="store_true",
        default=default(False),
        help="Never prompt or open interactive flows; fail with actionable diagnostics",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=default(15.0),
        help="Network timeout in seconds",
    )
    parser.add_argument(
        "--proxy",
        type=str,
        default=default(None),
        help="HTTP(S) proxy URL",
    )
    parser.add_argument(
        "--cache-dir",
        type=str,
        default=default("~/.cache/wstk"),
        help="Cache directory",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        default=default(False),
        help="Disable cache",
    )
    parser.add_argument(
        "--fresh",
        action="store_true",
        default=default(False),
        help="Bypass cache reads",
    )
    parser.add_argument(
        "--cache-max-mb",
        type=int,
        default=default(1024),
        help="Cache size budget in MB",
    )
    parser.add_argument(
        "--cache-ttl",
        type=str,
        default=default("7d"),
        help="Cache TTL (e.g. 24h, 7d)",
    )
    parser.add_argument(
        "--evidence-dir",
        type=str,
        default=default(None),
        help="Evidence directory (optional)",
    )
    parser.add_argument(
        "--redact",
        action="store_true",
        default=default(False),
        help="Redact query strings from URLs in output",
    )
    parser.add_argument(
        "--robots",
        choices=["warn", "respect", "ignore"],
        default=default("warn"),
        help="robots.txt stance (default: warn)",
    )
    parser.add_argument(
        "--allow-domain",
        action="append",
        default=default([]),
        help="Allow domain (repeatable); restricts network operations",
    )
    parser.add_argument(
        "--block-domain",
        action="append",
        default=default([]),
        help="Block domain (repeatable); restricts network operations",
    )
    parser.add_argument(
        "--policy",
        choices=["standard", "strict", "permissive"],
        default=default("standard"),
        help="Policy mode (default: standard)",
    )


def build_parser() -> argparse.ArgumentParser:
    global_root = argparse.ArgumentParser(add_help=False)
    _add_global_flags(global_root, suppress_defaults=False)

    global_sub = argparse.ArgumentParser(add_help=False)
    _add_global_flags(global_sub, suppress_defaults=True)

    parser = argparse.ArgumentParser(prog="wstk", parents=[global_root], add_help=True)
    parser.add_argument("--version", action="version", version=__version__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("providers", parents=[global_sub], help="List available providers")

    search_p = subparsers.add_parser("search", parents=[global_sub], help="Search the web")
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

    fetch_p = subparsers.add_parser("fetch", parents=[global_sub], help="Fetch a URL over HTTP")
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
        "extract", parents=[global_sub], help="Extract readable content"
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

    eval_p = subparsers.add_parser("eval", parents=[global_sub], help="Run an eval suite")
    eval_p.add_argument("--suite", type=str, required=True, help="Suite file (JSON or JSONL)")
    eval_p.add_argument(
        "--provider",
        action="append",
        default=[],
        help="Search provider(s) to run (repeatable; default: auto)",
    )
    eval_p.add_argument("-k", "--k", type=int, default=10, help="Top-k used for metrics")
    eval_p.add_argument(
        "--fail-on",
        choices=["none", "error", "miss", "miss_or_error"],
        default="error",
        help="Return non-zero exit code when the run has misses/errors (default: error)",
    )
    eval_p.add_argument(
        "--include-results", action="store_true", help="Include result items in JSON output"
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


@dataclass(slots=True)
class _EvalProviderStats:
    cases_total: int = 0
    criteria_cases: int = 0
    hit_cases: int = 0
    mrr_sum: float = 0.0
    errors: int = 0


@dataclass(frozen=True, slots=True)
class _EvalProviderSummary:
    provider: str
    cases_total: int
    criteria_cases: int
    hit_cases: int
    hit_rate: float
    mrr: float
    errors: int

    def to_dict(self) -> dict[str, object]:
        return {
            "provider": self.provider,
            "cases_total": self.cases_total,
            "criteria_cases": self.criteria_cases,
            "hit_cases": self.hit_cases,
            "hit_rate": self.hit_rate,
            "mrr": self.mrr,
            "errors": self.errors,
        }


@dataclass(frozen=True, slots=True)
class _EvalOverlapSummary:
    a: str
    b: str
    avg_jaccard: float
    cases: int

    def to_dict(self) -> dict[str, object]:
        return {
            "a": self.a,
            "b": self.b,
            "avg_jaccard": self.avg_jaccard,
            "cases": self.cases,
        }


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
            providers_data: list[dict[str, object]] = []

            for p in list_search_providers(timeout=float(args.timeout), proxy=args.proxy):
                enabled, reason = p.is_enabled()
                providers_data.append(
                    {
                        "id": p.id,
                        "type": "search",
                        "enabled": enabled,
                        "reason": reason,
                        "required_env": ["BRAVE_API_KEY"] if p.id == "brave_api" else [],
                    }
                )

            providers_data.append(
                {"id": "http", "type": "fetch", "enabled": True, "reason": None, "required_env": []}
            )
            providers_data.append(
                {
                    "id": "readability",
                    "type": "extract",
                    "enabled": True,
                    "reason": None,
                    "required_env": [],
                }
            )

            if args.plain and not (args.json or args.pretty):
                for item in providers_data:
                    print(item["id"])
                return ExitCode.OK

            if not (args.json or args.pretty):
                for item in providers_data:
                    status = "enabled" if item["enabled"] else f"disabled ({item['reason']})"
                    print(f"{item['type']}: {item['id']} - {status}")
                return ExitCode.OK

            meta = EnvelopeMeta(
                duration_ms=int((time.time() - start) * 1000),
                providers=[str(p["id"]) for p in providers_data],
            )
            return _envelope_and_exit(
                args=args,
                command=command,
                ok=True,
                data={"providers": providers_data},
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

        if command == "eval":
            suite = load_suite(str(args.suite))
            requested_provider_ids = tuple(getattr(args, "provider", []) or ["auto"])

            eval_providers: list[tuple[str, SearchProvider]] = []
            eval_provider_ids: list[str] = []
            for requested_id in requested_provider_ids:
                provider, provider_meta = select_search_provider(
                    str(requested_id), timeout=float(args.timeout), proxy=args.proxy
                )
                resolved_id = provider_meta[0] if provider_meta else provider.id
                if resolved_id in eval_provider_ids:
                    continue
                enabled, reason = provider.is_enabled()
                if not enabled:
                    raise WstkError(
                        code="provider_disabled",
                        message=f"provider disabled: {resolved_id} ({reason})",
                        exit_code=ExitCode.INVALID_USAGE,
                    )
                eval_providers.append((resolved_id, provider))
                eval_provider_ids.append(resolved_id)

            cache = _cache_from_args(args)
            rules = _domain_rules_from_args(args)

            cache_reads = 0
            cache_hits = 0
            cache_writes = 0

            any_error = False
            any_miss = False

            per_provider_stats = {pid: _EvalProviderStats() for pid in eval_provider_ids}
            url_sets: dict[tuple[str, str], set[str]] = {}

            def criterion_for_case(case: EvalCase) -> str:
                if case.expected_urls:
                    return "url"
                if case.expected_domains:
                    return "domain"
                return "none"

            cases_out: list[dict] = []

            for case in suite.cases:
                case_k = int(case.k or args.k)
                criterion = criterion_for_case(case)
                case_by_provider: dict[str, object] = {}
                case_entry: dict[str, object] = {
                    "id": case.id,
                    "query": case.query,
                    "expected_domains": list(case.expected_domains),
                    "expected_urls": list(case.expected_urls),
                    "k": case_k,
                    "by_provider": case_by_provider,
                }

                for pid, provider in eval_providers:
                    stats = per_provider_stats[pid]
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
                    hit = cache.get(key=key)
                    cached_payload = None
                    if hit is not None:
                        cache_hits += 1
                        try:
                            cached_payload = json.loads(
                                hit.body_path.read_bytes().decode("utf-8", errors="replace")
                            )
                        except Exception:
                            cached_payload = None

                    results: list[SearchResultItem] = []
                    results_dicts: list[dict] = []

                    if isinstance(cached_payload, list):
                        for item in cached_payload:
                            parsed = _search_item_from_dict(item, fallback_provider=pid)
                            if parsed is None:
                                continue
                            results.append(parsed)
                            results_dicts.append(parsed.to_dict())
                    else:
                        try:
                            provider_results = provider.search(query, include_raw=False)
                        except WstkError as e:
                            any_error = True
                            stats.errors += 1
                            case_by_provider[pid] = {"error": e.to_error_dict()}
                            continue
                        except Exception as e:  # pragma: no cover
                            any_error = True
                            stats.errors += 1
                            case_by_provider[pid] = {
                                "error": {
                                    "code": "unexpected_error",
                                    "message": str(e),
                                    "details": None,
                                }
                            }
                            continue

                        results = list(provider_results)
                        results_dicts = [r.to_dict() for r in provider_results]
                        cache.put(
                            key=key,
                            meta={"kind": "search", "provider": pid},
                            body=json.dumps(results_dicts, ensure_ascii=False).encode("utf-8"),
                        )
                        cache_writes += 1

                    duration_ms = int((time.time() - t0) * 1000)

                    filtered_results: list[SearchResultItem] = []
                    filtered_dicts: list[dict] = []
                    for r in results:
                        if (rules.allow or rules.block) and not is_allowed(r.url, rules):
                            continue
                        url = redact_url(r.url) if args.redact else r.url
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

                    for d in results_dicts:
                        url = d.get("url")
                        if not isinstance(url, str):
                            continue
                        if (rules.allow or rules.block) and not is_allowed(url, rules):
                            continue
                        if args.redact:
                            d = {**d, "url": redact_url(url)}
                        filtered_dicts.append(d)

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

                    provider_entry: dict[str, object] = {
                        "criterion": criterion,
                        "passed": passed,
                        "duration_ms": duration_ms,
                        "score": score.to_dict(),
                    }
                    if args.include_results:
                        provider_entry["results"] = filtered_dicts[:case_k]
                    case_by_provider[pid] = provider_entry

                cases_out.append(case_entry)

            provider_summaries: list[_EvalProviderSummary] = []
            for pid in eval_provider_ids:
                stats = per_provider_stats[pid]
                criteria_cases = stats.criteria_cases
                hit_cases = stats.hit_cases
                hit_rate = 0.0 if criteria_cases == 0 else hit_cases / float(criteria_cases)
                mrr = 0.0 if criteria_cases == 0 else stats.mrr_sum / float(criteria_cases)
                provider_summaries.append(
                    _EvalProviderSummary(
                        provider=pid,
                        cases_total=stats.cases_total,
                        criteria_cases=criteria_cases,
                        hit_cases=hit_cases,
                        hit_rate=hit_rate,
                        mrr=mrr,
                        errors=stats.errors,
                    )
                )

            overlap_summaries: list[_EvalOverlapSummary] = []
            if len(eval_provider_ids) >= 2:
                for i, a in enumerate(eval_provider_ids):
                    for b in eval_provider_ids[i + 1 :]:
                        values: list[float] = []
                        for case in suite.cases:
                            a_set = url_sets.get((case.id, a), set())
                            b_set = url_sets.get((case.id, b), set())
                            union = a_set | b_set
                            if not union:
                                continue
                            values.append(len(a_set & b_set) / float(len(union)))
                        avg_jaccard = 0.0 if not values else sum(values) / float(len(values))
                        overlap_summaries.append(
                            _EvalOverlapSummary(
                                a=a,
                                b=b,
                                avg_jaccard=avg_jaccard,
                                cases=len(values),
                            )
                        )

            report = {
                "suite": {"path": suite.path, "case_count": len(suite.cases)},
                "settings": {
                    "providers": list(eval_provider_ids),
                    "k": int(args.k),
                    "fail_on": str(args.fail_on),
                },
                "summary": {
                    "by_provider": [s.to_dict() for s in provider_summaries],
                    "overlap": [o.to_dict() for o in overlap_summaries],
                    "cache": {"reads": cache_reads, "hits": cache_hits, "writes": cache_writes},
                },
                "cases": cases_out,
            }

            failed = False
            if args.fail_on in {"error", "miss_or_error"} and any_error:
                failed = True
            if args.fail_on in {"miss", "miss_or_error"} and any_miss:
                failed = True

            if args.plain and not (args.json or args.pretty):
                for row in provider_summaries:
                    print(
                        "\t".join(
                            [
                                row.provider,
                                f"{row.hit_rate:.3f}",
                                f"{row.mrr:.3f}",
                                str(row.hit_cases),
                                str(row.criteria_cases),
                                str(row.errors),
                            ]
                        )
                    )
                if failed:
                    print("eval failed", file=sys.stderr)
                    return ExitCode.RUNTIME_ERROR
                return ExitCode.OK

            if not (args.json or args.pretty):
                print(f"suite: {suite.path} ({len(suite.cases)} cases, k={int(args.k)})")
                for row in provider_summaries:
                    print(
                        f"{row.provider}: hit@k {row.hit_cases}/{row.criteria_cases} "
                        f"({row.hit_rate:.3f}), mrr {row.mrr:.3f}, errors {row.errors}"
                    )
                if failed:
                    print("eval failed", file=sys.stderr)
                    return ExitCode.RUNTIME_ERROR
                return ExitCode.OK

            meta = EnvelopeMeta(
                duration_ms=int((time.time() - start) * 1000),
                providers=list(eval_provider_ids),
            )
            if not failed:
                return _envelope_and_exit(
                    args=args,
                    command=command,
                    ok=True,
                    data=report,
                    warnings=warnings,
                    error=None,
                    meta=meta,
                )

            err = WstkError(
                code="eval_failed",
                message="eval failed",
                exit_code=ExitCode.RUNTIME_ERROR,
                details={"miss": any_miss, "error": any_error, "fail_on": str(args.fail_on)},
            )
            return _envelope_and_exit(
                args=args,
                command=command,
                ok=False,
                data=report,
                warnings=warnings,
                error=err,
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
