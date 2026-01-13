from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from wstk import __version__
from wstk.cache import Cache, CacheSettings
from wstk.errors import ExitCode, WstkError
from wstk.output import EnvelopeMeta, make_envelope, print_json
from wstk.safety import redact_payload
from wstk.timeutil import parse_duration
from wstk.urlutil import DomainRules, is_allowed


def wants_json(args: argparse.Namespace) -> bool:
    return bool(getattr(args, "json", False) or getattr(args, "pretty", False))


def wants_plain(args: argparse.Namespace) -> bool:
    return bool(getattr(args, "plain", False) and not wants_json(args))


def append_warning(warnings: list[str], message: str) -> None:
    if message not in warnings:
        warnings.append(message)


def add_global_flags(parser: argparse.ArgumentParser, *, suppress_defaults: bool) -> None:
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
        help="Redact common secrets/PII from output",
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


def domain_rules_from_args(args: argparse.Namespace) -> DomainRules:
    allow = tuple(getattr(args, "allow_domain", []) or [])
    block = tuple(getattr(args, "block_domain", []) or [])
    return DomainRules(allow=allow, block=block)


def enforce_url_policy(*, args: argparse.Namespace, url: str, operation: str) -> None:
    rules = domain_rules_from_args(args)
    if args.policy == "strict" and not rules.allow:
        raise WstkError(
            code="policy_violation",
            message=f"strict policy requires --allow-domain for network {operation}",
            exit_code=ExitCode.INVALID_USAGE,
        )
    if (rules.allow or rules.block) and not is_allowed(url, rules):
        raise WstkError(
            code="domain_blocked",
            message="URL blocked by domain rules",
            exit_code=ExitCode.INVALID_USAGE,
            details={"url": url},
        )


def cache_from_args(args: argparse.Namespace) -> Cache:
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


def parse_headers(args: argparse.Namespace) -> dict[str, str]:
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


def print_envelope(args: argparse.Namespace, payload: dict) -> None:
    if not wants_json(args):
        return
    print_json(payload, pretty=bool(getattr(args, "pretty", False)))


def envelope_and_exit(
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
    if getattr(args, "redact", False):
        payload = redact_payload(payload)
    print_envelope(args, payload)
    return ExitCode.OK if ok else (error.exit_code if error is not None else ExitCode.RUNTIME_ERROR)
