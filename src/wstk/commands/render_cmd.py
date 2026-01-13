from __future__ import annotations

import argparse
import time
from pathlib import Path

from wstk.cli_support import enforce_url_policy, envelope_and_exit, wants_json, wants_plain
from wstk.errors import ExitCode, WstkError
from wstk.output import EnvelopeMeta
from wstk.render.browser import (
    RenderSettings,
    render_url,
    resolve_evidence_dir,
    resolve_system_profile,
)
from wstk.urlutil import redact_url


def register(
    subparsers: argparse._SubParsersAction, *, parents: list[argparse.ArgumentParser]
) -> None:
    p = subparsers.add_parser("render", parents=parents, help="Render a URL in a browser")
    p.set_defaults(_handler=run)

    p.add_argument("url", type=str, help="URL to render")
    profile_group = p.add_mutually_exclusive_group()
    profile_group.add_argument(
        "--profile",
        type=str,
        default=None,
        help="Browser profile directory",
    )
    profile_group.add_argument(
        "--use-system-profile",
        action="store_true",
        default=False,
        help="Use system browser profile",
    )
    p.add_argument("--wait", type=int, default=0, help="Wait ms after load")
    p.add_argument(
        "--wait-for",
        type=str,
        default=None,
        help="Wait for selector or 'network-idle'",
    )
    p.add_argument("--screenshot", action="store_true", help="Capture screenshot to evidence")
    head_group = p.add_mutually_exclusive_group()
    head_group.add_argument("--headful", action="store_true", default=False, help="Headful mode")
    head_group.add_argument(
        "--headless",
        action="store_false",
        dest="headful",
        help="Headless mode (default)",
    )


def run(*, args: argparse.Namespace, start: float, warnings: list[str]) -> int:
    url = str(args.url)
    enforce_url_policy(args=args, url=url, operation="render")

    if args.no_input and args.headful:
        raise WstkError(
            code="no_input",
            message="--headful is not allowed with --no-input",
            exit_code=ExitCode.INVALID_USAGE,
        )
    if args.wait < 0:
        raise WstkError(
            code="invalid_wait",
            message="--wait must be >= 0",
            exit_code=ExitCode.INVALID_USAGE,
        )

    profile_dir = None
    profile_label = None
    if args.profile:
        profile_dir = Path(str(args.profile)).expanduser()
        profile_label = "custom"
    elif args.use_system_profile:
        profile_dir = resolve_system_profile()
        profile_label = "system"

    if args.policy == "strict" and profile_dir is not None:
        raise WstkError(
            code="policy_violation",
            message="strict policy forbids browser profile reuse",
            exit_code=ExitCode.INVALID_USAGE,
        )

    if profile_label:
        warnings.append("render used a browser profile; treat output as privileged")
    if args.headful:
        warnings.append("render used headful mode")

    evidence_dir = resolve_evidence_dir(
        evidence_dir=args.evidence_dir,
        cache_dir=args.cache_dir,
    )
    settings = RenderSettings(
        timeout=float(args.timeout),
        proxy=args.proxy,
        wait_ms=int(args.wait),
        wait_for=args.wait_for,
        headful=bool(args.headful),
        screenshot=bool(args.screenshot),
        evidence_dir=evidence_dir,
        profile_dir=profile_dir,
        profile_label=profile_label,
    )

    result = render_url(url, settings=settings)
    doc = result.document

    if wants_plain(args):
        if doc.artifact and doc.artifact.body_path:
            print(doc.artifact.body_path)
        else:
            output_url = doc.url
            if args.redact:
                output_url = redact_url(output_url)
            print(output_url)
        return ExitCode.OK

    if not wants_json(args):
        status = doc.http.status if doc.http else "unknown"
        output_url = doc.url
        if args.redact:
            output_url = redact_url(output_url)
        print(f"BROWSER {status} {output_url}")
        if doc.artifact and doc.artifact.body_path:
            print(f"dom: {doc.artifact.body_path}")
        if doc.render and doc.render.screenshot_path:
            print(f"screenshot: {doc.render.screenshot_path}")
        return ExitCode.OK

    meta = EnvelopeMeta(
        duration_ms=int((time.time() - start) * 1000),
        providers=["browser"],
    )
    return envelope_and_exit(
        args=args,
        command="render",
        ok=True,
        data={"document": doc.to_dict()},
        warnings=warnings,
        error=None,
        meta=meta,
    )
