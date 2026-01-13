from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from wstk.cli_support import (
    cache_from_args,
    enforce_url_policy,
    envelope_and_exit,
    parse_headers,
    wants_json,
    wants_plain,
)
from wstk.errors import ExitCode, WstkError
from wstk.extract.docs_extractor import extract_docs, looks_like_docs
from wstk.extract.readability_extractor import extract_readability
from wstk.fetch.http import FetchSettings, fetch_url
from wstk.models import DocContent, DocSection, Document, ExtractedContent
from wstk.output import CacheMeta, EnvelopeMeta
from wstk.render.browser import RenderSettings, render_url, resolve_evidence_dir
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
            evidence_dir = resolve_evidence_dir(
                evidence_dir=args.evidence_dir,
                cache_dir=args.cache_dir,
            )
            render_settings = RenderSettings(
                timeout=float(args.timeout),
                proxy=args.proxy,
                wait_ms=0,
                wait_for=None,
                headful=False,
                screenshot=False,
                evidence_dir=evidence_dir,
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
        strategy = "docs" if looks_like_docs(html) else "readability"

    if strategy == "docs":
        extracted = extract_docs(
            html,
            include_markdown=include_markdown,
            include_text=include_text,
        )
        providers = ["docs"]
    else:
        extracted = extract_readability(
            html,
            include_markdown=include_markdown,
            include_text=include_text,
        )
        providers = ["readability"]

    if base_doc.fetch_method == "http":
        providers = ["http", *providers]
    elif base_doc.fetch_method == "browser":
        providers = ["browser", *providers]

    injection_hits = detect_prompt_injection(_text_for_scan(extracted))
    if injection_hits:
        warnings.append(
            "possible prompt injection patterns detected: " + ", ".join(injection_hits)
        )

    extracted = _apply_limits(
        extracted,
        max_chars=args.max_chars,
        max_tokens=args.max_tokens,
    )

    markdown_output = extracted.markdown
    text_output = extracted.text
    if args.redact:
        if markdown_output:
            markdown_output = redact_text(markdown_output)
        if text_output:
            text_output = redact_text(text_output)

    if wants_plain(args):
        if args.text and text_output:
            sys.stdout.write(text_output)
            if not text_output.endswith("\n"):
                sys.stdout.write("\n")
            return ExitCode.OK
        if args.markdown and markdown_output:
            sys.stdout.write(markdown_output)
            if not markdown_output.endswith("\n"):
                sys.stdout.write("\n")
            return ExitCode.OK
        content = markdown_output or text_output or ""
        sys.stdout.write(content)
        if content and not content.endswith("\n"):
            sys.stdout.write("\n")
        return ExitCode.OK if content else ExitCode.NOT_FOUND

    if not wants_json(args):
        content = markdown_output if include_markdown else text_output
        content = content or text_output or markdown_output or ""
        sys.stdout.write(content)
        if content and not content.endswith("\n"):
            sys.stdout.write("\n")
        return ExitCode.OK if content else ExitCode.NOT_FOUND

    doc_dict = base_doc.to_dict()
    doc_dict["extracted"] = extracted.to_dict()
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


def _apply_limits(
    extracted: ExtractedContent, *, max_chars: int, max_tokens: int
) -> ExtractedContent:
    if max_chars <= 0 and max_tokens <= 0:
        return extracted

    markdown = _truncate_value(extracted.markdown, max_chars, max_tokens)
    text = _truncate_value(extracted.text, max_chars, max_tokens)
    doc = extracted.doc
    if doc is not None:
        sections = _truncate_sections(doc.sections, max_chars, max_tokens)
        doc = DocContent(title=doc.title, sections=sections, links=doc.links)

    return ExtractedContent(
        title=extracted.title,
        language=extracted.language,
        extraction_method=extracted.extraction_method,
        markdown=markdown,
        text=text,
        doc=doc,
    )


def _truncate_value(value: str | None, max_chars: int, max_tokens: int) -> str | None:
    if value is None:
        return None
    truncated = value
    if max_tokens > 0:
        tokens = truncated.split()
        if len(tokens) > max_tokens:
            truncated = " ".join(tokens[:max_tokens])
    if max_chars > 0 and len(truncated) > max_chars:
        truncated = truncated[:max_chars]
    return truncated or None


def _truncate_sections(
    sections: list[DocSection], max_chars: int, max_tokens: int
) -> list[DocSection]:
    if max_chars <= 0 and max_tokens <= 0:
        return sections

    remaining_chars = max_chars if max_chars > 0 else None
    remaining_tokens = max_tokens if max_tokens > 0 else None
    truncated_sections: list[DocSection] = []

    for section in sections:
        content, remaining_chars, remaining_tokens = _truncate_with_budget(
            section.content,
            remaining_chars,
            remaining_tokens,
        )
        truncated_sections.append(
            DocSection(
                heading=section.heading,
                level=section.level,
                content=content,
            )
        )
        if remaining_chars is not None and remaining_chars <= 0:
            break
        if remaining_tokens is not None and remaining_tokens <= 0:
            break

    return truncated_sections


def _truncate_with_budget(
    value: str | None,
    remaining_chars: int | None,
    remaining_tokens: int | None,
) -> tuple[str | None, int | None, int | None]:
    if value is None:
        return None, remaining_chars, remaining_tokens

    truncated = value
    if remaining_chars is not None and len(truncated) > remaining_chars:
        truncated = truncated[:remaining_chars]

    if remaining_tokens is not None:
        tokens = truncated.split()
        if len(tokens) > remaining_tokens:
            truncated = " ".join(tokens[:remaining_tokens])
            tokens_used = remaining_tokens
        else:
            tokens_used = len(tokens)
        remaining_tokens -= tokens_used

    if remaining_chars is not None:
        remaining_chars -= len(truncated)

    truncated = truncated.strip() or None
    return truncated, remaining_chars, remaining_tokens


def _text_for_scan(extracted: ExtractedContent) -> str:
    if extracted.markdown:
        return extracted.markdown
    if extracted.text:
        return extracted.text
    doc = extracted.doc
    if doc is None:
        return ""
    sections = [section.content for section in doc.sections if section.content]
    return "\n".join(sections)
