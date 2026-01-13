from __future__ import annotations

import argparse
import sys
import time

import wstk.search.registry as search_registry
from wstk.cli_support import (
    cache_from_args,
    domain_rules_from_args,
    envelope_and_exit,
    wants_json,
    wants_plain,
)
from wstk.commands.support import fetch_settings_from_args
from wstk.errors import ExitCode, WstkError
from wstk.eval.runner import run_search_eval
from wstk.eval.suite import load_suite
from wstk.output import EnvelopeMeta
from wstk.search.base import SearchProvider


def register(
    subparsers: argparse._SubParsersAction, *, parents: list[argparse.ArgumentParser]
) -> None:
    p = subparsers.add_parser("eval", parents=parents, help="Run an eval suite")
    p.set_defaults(_handler=run)

    p.add_argument("--suite", type=str, required=True, help="Suite file (JSON or JSONL)")
    p.add_argument(
        "--provider",
        action="append",
        default=[],
        help="Search provider(s) to run (repeatable; default: auto)",
    )
    p.add_argument("-k", "--k", type=int, default=10, help="Top-k used for metrics")
    p.add_argument(
        "--fail-on",
        choices=["none", "error", "miss", "miss_or_error"],
        default="error",
        help="Return non-zero exit code when the run has misses/errors (default: error)",
    )
    p.add_argument(
        "--include-results",
        action="store_true",
        help="Include result items in JSON output",
    )

def _resolve_providers(
    args: argparse.Namespace, warnings: list[str]
) -> list[tuple[str, SearchProvider]]:
    requested_provider_ids = tuple(getattr(args, "provider", []) or ["auto"])

    providers: list[tuple[str, SearchProvider]] = []
    seen: set[str] = set()
    for requested_id in requested_provider_ids:
        provider, provider_meta = search_registry.select_search_provider(
            str(requested_id), timeout=float(args.timeout), proxy=args.proxy
        )
        resolved_id = provider_meta[0] if provider_meta else provider.id
        if resolved_id in seen:
            continue
        enabled, reason = provider.is_enabled()
        if not enabled:
            raise WstkError(
                code="provider_disabled",
                message=f"provider disabled: {resolved_id} ({reason})",
                exit_code=ExitCode.INVALID_USAGE,
            )
        search_registry.append_provider_warnings(warnings, resolved_id)
        providers.append((resolved_id, provider))
        seen.add(resolved_id)
    return providers


def run(*, args: argparse.Namespace, start: float, warnings: list[str]) -> int:
    suite = load_suite(str(args.suite))
    providers = _resolve_providers(args, warnings)

    cache = cache_from_args(args)
    rules = domain_rules_from_args(args)

    policy = str(args.policy)
    allow_domains = tuple(getattr(args, "allow_domain", []) or [])
    if policy == "strict" and not allow_domains:
        warnings.append(
            "strict policy requires --allow-domain for eval fetch/extract; skipping fetch/extract metrics"
        )

    fetch_settings = fetch_settings_from_args(
        args,
        max_bytes=5 * 1024 * 1024,
        follow_redirects=True,
        detect_blocks=True,
        cache=cache,
    )

    eval_result = run_search_eval(
        suite=suite,
        providers=providers,
        cache=cache,
        rules=rules,
        k=int(args.k),
        redact=bool(args.redact),
        include_results=bool(args.include_results),
        fetch_settings=fetch_settings,
        policy=policy,
    )
    report = eval_result.report
    report.setdefault("settings", {})["fail_on"] = str(args.fail_on)
    any_error = eval_result.any_error
    any_miss = eval_result.any_miss
    provider_ids = list(report.get("settings", {}).get("providers", []))

    failed = False
    if args.fail_on in {"error", "miss_or_error"} and any_error:
        failed = True
    if args.fail_on in {"miss", "miss_or_error"} and any_miss:
        failed = True

    if wants_plain(args):
        summary_by_provider = report.get("summary", {}).get("by_provider", [])
        for row in summary_by_provider:
            print(
                "\t".join(
                    [
                        str(row["provider"]),
                        f"{float(row['hit_rate']):.3f}",
                        f"{float(row['mrr']):.3f}",
                        str(int(row["hit_cases"])),
                        str(int(row["criteria_cases"])),
                        str(int(row["errors"])),
                    ]
                )
            )
        if failed:
            print("eval failed", file=sys.stderr)
            return ExitCode.RUNTIME_ERROR
        return ExitCode.OK

    if not wants_json(args):
        print(f"suite: {suite.path} ({len(suite.cases)} cases, k={int(args.k)})")
        summary_by_provider = report.get("summary", {}).get("by_provider", [])
        for row in summary_by_provider:
            print(
                f"{row['provider']}: hit@k {row['hit_cases']}/{row['criteria_cases']} "
                f"({row['hit_rate']:.3f}), mrr {row['mrr']:.3f}, errors {row['errors']}"
            )
        if failed:
            print("eval failed", file=sys.stderr)
            return ExitCode.RUNTIME_ERROR
        return ExitCode.OK

    meta = EnvelopeMeta(duration_ms=int((time.time() - start) * 1000), providers=provider_ids)
    if not failed:
        return envelope_and_exit(
            args=args,
            command="eval",
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
    return envelope_and_exit(
        args=args,
        command="eval",
        ok=False,
        data=report,
        warnings=warnings,
        error=err,
        meta=meta,
    )
