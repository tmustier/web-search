from __future__ import annotations

import argparse
import sys
import time
from collections.abc import Callable

from wstk import __version__
from wstk.cli_support import add_global_flags, envelope_and_exit
from wstk.commands import eval_cmd, extract_cmd, fetch_cmd, providers_cmd, search_cmd
from wstk.errors import ExitCode, WstkError
from wstk.output import EnvelopeMeta


def build_parser() -> argparse.ArgumentParser:
    global_root = argparse.ArgumentParser(add_help=False)
    add_global_flags(global_root, suppress_defaults=False)

    global_sub = argparse.ArgumentParser(add_help=False)
    add_global_flags(global_sub, suppress_defaults=True)

    parser = argparse.ArgumentParser(prog="wstk", parents=[global_root], add_help=True)
    parser.add_argument("--version", action="version", version=__version__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("providers", parents=[global_sub], help="List available providers")

    search_p = subparsers.add_parser("search", parents=[global_sub], help="Search the web")
    search_p.add_argument("query", type=str, help="Search query")
    search_p.add_argument("-n", "--max-results", type=int, default=10, help="Maximum results")
    search_p.add_argument(
        "--time-range",
        type=str,
        default=None,
        help="Time range (provider-specific)",
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
        "--provider",
        type=str,
        default="auto",
        help="Search provider (default: auto)",
    )
    search_p.add_argument(
        "--include-raw", action="store_true", help="Include provider raw payload subset in JSON"
    )

    fetch_p = subparsers.add_parser("fetch", parents=[global_sub], help="Fetch a URL over HTTP")
    fetch_p.add_argument("url", type=str, help="URL to fetch")
    fetch_p.add_argument("--header", action="append", default=[], help="Extra header: key:value")
    fetch_p.add_argument(
        "--headers-file", type=str, default=None, help="JSON object of headers (path or '-')"
    )
    fetch_p.add_argument("--user-agent", type=str, default=None, help="User-Agent header")
    fetch_p.add_argument("--accept-language", type=str, default=None, help="Accept-Language header")
    fetch_p.add_argument(
        "--max-bytes",
        type=int,
        default=5 * 1024 * 1024,
        help="Max response bytes",
    )
    fetch_p.add_argument(
        "--follow-redirects",
        action="store_true",
        default=True,
        help="Follow redirects",
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


CommandHandler = Callable[..., int]
_COMMANDS: dict[str, CommandHandler] = {
    "providers": providers_cmd.run,
    "search": search_cmd.run,
    "fetch": fetch_cmd.run,
    "extract": extract_cmd.run,
    "eval": eval_cmd.run,
}


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    command = str(args.command)
    start = time.time()
    warnings: list[str] = []

    try:
        handler = _COMMANDS.get(command)
        if handler is None:
            raise WstkError(
                code="invalid_usage",
                message=f"unknown command: {command}",
                exit_code=ExitCode.INVALID_USAGE,
            )
        return handler(args=args, start=start, warnings=warnings)
    except WstkError as e:
        meta = EnvelopeMeta(duration_ms=int((time.time() - start) * 1000))
        if args.json or args.pretty:
            return envelope_and_exit(
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
