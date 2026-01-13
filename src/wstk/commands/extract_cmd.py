from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from wstk.cli_support import (
    append_warning,
    enforce_url_policy,
    envelope_and_exit,
    wants_json,
    wants_plain,
)
from wstk.commands.support import fetch_settings_from_args, render_settings_from_args
from wstk.errors import ExitCode, WstkError
from wstk.extract.utils import (
    apply_limits,
    choose_strategy,
    extract_html,
    select_extracted_output,
    text_for_scan,
)
from wstk.fetch.http import fetch_url
from wstk.models import Document
from wstk.output import CacheMeta, EnvelopeMeta
from wstk.render.browser import render_url
from wstk.safety import detect_prompt_injection, redact_text


def register(
    subparsers: argparse._SubParsersAction, *, parents: list[argparse.ArgumentParser]
) -> None:
    p = subparsers.add_parser("extract", parents=parents, help="Extract readable content")
    p.set_defaults(_handler=run)

    p.add_argument("target", type=str, help="URL, path, or '-' for stdin")
    p.add_argument("--strategy", choices=["auto", "readability", "docs"], default="auto")
    p.add_argument("--method", choices=["http", "browser", "auto"], default="http")
    out_group = p.add_mutually_exclusive_group()
    out_group.add_argument("--markdown", action="store_true", help="Output markdown only")
    out_group.add_argument("--text", action="store_true", help="Output text only")
    out_group.add_argument("--both", action="store_true", help="Output both markdown and text")
    p.add_argument("--max-chars", type=int, default=0, help="Truncate extracted output")
    p.add_argument(
        "--max-tokens",
        type=int,
        default=0,
        help="Truncate extracted output by token count (approx)",
    )
    p.add_argument("--include-html", action="store_true", help="Include HTML in JSON (debug)")


def run(*, args: argparse.Namespace, start: float, warnings: list[str]) -> int:
    target = str(args.target)

    include_markdown = bool(
        args.markdown or args.both or (not args.text and not args.markdown and not args.both)
    )
    include_text = bool(
        args.text or args.both or (not args.text and not args.markdown and not args.both)
    )

    method = str(args.method)
    if method == "auto" and args.policy != "permissive":
        raise WstkError(
            code="policy_violation",
            message="auto browser escalation requires --policy permissive",
            exit_code=ExitCode.INVALID_USAGE,
        )

    cache_meta = None
    if target.startswith(("http://", "https://")):
        enforce_url_policy(args=args, url=target, operation="extract")
        html = ""
        if method in {"http", "auto"}:
            fetch_settings = fetch_settings_from_args(
                args,
                max_bytes=5 * 1024 * 1024,
                follow_redirects=True,
                detect_blocks=True,
            )
            try:
                res = fetch_url(target, settings=fetch_settings)
            except WstkError as exc:
                if method == "auto" and exc.code == "needs_render":
                    method = "browser"
                else:
                    raise
            else:
                html = res.body.decode("utf-8", errors="replace")
                base_doc = res.document
                cache_meta = CacheMeta(
                    hit=res.cache_hit is not None,
                    key=res.cache_hit.key if res.cache_hit else None,
                )
        if method == "browser":
            render_settings = render_settings_from_args(
                args,
                wait_ms=0,
                wait_for=None,
                headful=False,
                screenshot=False,
                profile_dir=None,
                profile_label=None,
            )
            render_result = render_url(target, settings=render_settings)
            html = render_result.html
            base_doc = render_result.document
    else:
        if target == "-":
            html = sys.stdin.read()
            source_url = "stdin"
        else:
            path = Path(target)
            html = path.read_text(encoding="utf-8")
            source_url = path.resolve().as_uri()
        base_doc = Document.new(url=source_url, fetch_method="provided")

    strategy = args.strategy
    if strategy == "auto":
        strategy = choose_strategy(html)

    extracted = extract_html(
        html,
        strategy=strategy,
        include_markdown=include_markdown,
        include_text=include_text,
    )

    providers = [strategy]
    if base_doc.fetch_method == "http":
        providers = ["http", *providers]
    elif base_doc.fetch_method == "browser":
        providers = ["browser", *providers]

    injection_hits = detect_prompt_injection(text_for_scan(extracted))
    if injection_hits:
        append_warning(
            warnings,
            "possible prompt injection patterns detected: " + ", ".join(injection_hits),
        )

    extracted = apply_limits(
        extracted,
        max_chars=args.max_chars,
        max_tokens=args.max_tokens,
    )

    if wants_plain(args) or not wants_json(args):
        content = select_extracted_output(
            extracted,
            prefer_markdown=include_markdown,
            markdown_only=bool(args.markdown),
            text_only=bool(args.text),
        )
        if args.redact and content:
            content = redact_text(content)
        if content:
            sys.stdout.write(content)
            if not content.endswith("\n"):
                sys.stdout.write("\n")
            return ExitCode.OK
        return ExitCode.NOT_FOUND

    doc = base_doc.with_extracted(extracted)
    doc_dict = doc.to_dict()
    if args.include_html:
        doc_dict["html"] = html

    meta = EnvelopeMeta(
        duration_ms=int((time.time() - start) * 1000),
        cache=cache_meta,
        providers=providers,
    )
    return envelope_and_exit(
        args=args,
        command="extract",
        ok=True,
        data={"document": doc_dict},
        warnings=warnings,
        error=None,
        meta=meta,
    )
