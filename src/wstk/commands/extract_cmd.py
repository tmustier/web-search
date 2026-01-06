from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from wstk.cli_support import (
    cache_from_args,
    domain_rules_from_args,
    envelope_and_exit,
    parse_headers,
)
from wstk.errors import ExitCode, WstkError
from wstk.extract.readability_extractor import extract_readability
from wstk.fetch.http import FetchSettings, fetch_url
from wstk.output import CacheMeta, EnvelopeMeta
from wstk.urlutil import is_allowed


def run(*, args: argparse.Namespace, start: float, warnings: list[str]) -> int:
    target = str(args.target)

    include_markdown = bool(
        args.markdown or args.both or (not args.text and not args.markdown and not args.both)
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

    rules = domain_rules_from_args(args)
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

        headers = parse_headers(args)
        cache = cache_from_args(args)
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
            hit=res.cache_hit is not None,
            key=res.cache_hit.key if res.cache_hit else None,
        )
    else:
        base_doc = None
        if target == "-":
            html = sys.stdin.read()
        else:
            html = Path(target).read_text(encoding="utf-8")

    extracted = extract_readability(
        html,
        include_markdown=include_markdown,
        include_text=include_text,
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
        content = extracted.markdown if include_markdown else extracted.text
        content = content or extracted.text or extracted.markdown or ""
        sys.stdout.write(content)
        if content and not content.endswith("\n"):
            sys.stdout.write("\n")
        return ExitCode.OK if content else ExitCode.NOT_FOUND

    if base_doc is None:
        meta = EnvelopeMeta(
            duration_ms=int((time.time() - start) * 1000),
            providers=["readability"],
        )
        return envelope_and_exit(
            args=args,
            command="extract",
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
    return envelope_and_exit(
        args=args,
        command="extract",
        ok=True,
        data={"document": doc_dict},
        warnings=warnings,
        error=None,
        meta=meta,
    )
