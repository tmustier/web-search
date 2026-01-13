from __future__ import annotations

import argparse
import sys
import time
from collections.abc import Callable
from typing import cast

from wstk import __version__
from wstk.cli_support import add_global_flags, envelope_and_exit, wants_json
from wstk.commands import (
    eval_cmd,
    extract_cmd,
    fetch_cmd,
    pipeline_cmd,
    providers_cmd,
    render_cmd,
    search_cmd,
)
from wstk.errors import ExitCode, WstkError
from wstk.output import EnvelopeMeta
from wstk.safety import redact_payload


def build_parser() -> argparse.ArgumentParser:
    global_root = argparse.ArgumentParser(add_help=False)
    add_global_flags(global_root, suppress_defaults=False)

    global_sub = argparse.ArgumentParser(add_help=False)
    add_global_flags(global_sub, suppress_defaults=True)

    parser = argparse.ArgumentParser(prog="wstk", parents=[global_root], add_help=True)
    parser.add_argument("--version", action="version", version=__version__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    parents = [global_sub]
    providers_cmd.register(subparsers, parents=parents)
    search_cmd.register(subparsers, parents=parents)
    pipeline_cmd.register(subparsers, parents=parents)
    fetch_cmd.register(subparsers, parents=parents)
    render_cmd.register(subparsers, parents=parents)
    extract_cmd.register(subparsers, parents=parents)
    eval_cmd.register(subparsers, parents=parents)

    return parser


CommandHandler = Callable[..., int]

def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    command = str(args.command)
    start = time.time()
    warnings: list[str] = []

    try:
        handler = cast(CommandHandler | None, getattr(args, "_handler", None))
        if handler is None:  # pragma: no cover
            raise WstkError(
                code="invalid_usage",
                message=f"unknown command: {command}",
                exit_code=ExitCode.INVALID_USAGE,
            )
        return handler(args=args, start=start, warnings=warnings)
    except WstkError as e:
        meta = EnvelopeMeta(duration_ms=int((time.time() - start) * 1000))
        if wants_json(args):
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
            details = e.details
            if getattr(args, "redact", False):
                details = redact_payload(details)
            print(f"details: {details}", file=sys.stderr)
        return e.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
