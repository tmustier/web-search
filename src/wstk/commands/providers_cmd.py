from __future__ import annotations

import argparse
import time

import wstk.search.registry as search_registry
from wstk.cli_support import envelope_and_exit, wants_json, wants_plain
from wstk.errors import ExitCode
from wstk.output import EnvelopeMeta
from wstk.render.browser import render_available


def register(
    subparsers: argparse._SubParsersAction, *, parents: list[argparse.ArgumentParser]
) -> None:
    p = subparsers.add_parser("providers", parents=parents, help="List available providers")
    p.set_defaults(_handler=run)


def run(*, args: argparse.Namespace, start: float, warnings: list[str]) -> int:
    providers_data: list[dict[str, object]] = []

    for info in search_registry.list_search_provider_info(
        timeout=float(args.timeout), proxy=args.proxy
    ):
        provider = info.provider
        enabled, reason = provider.is_enabled()
        payload = {
            "id": provider.id,
            "type": "search",
            "enabled": enabled,
            "reason": reason,
            "required_env": list(info.required_env),
        }
        if info.privacy_warning:
            payload["privacy_warning"] = info.privacy_warning
        providers_data.append(payload)

    providers_data.append(
        {"id": "http", "type": "fetch", "enabled": True, "reason": None, "required_env": []}
    )
    browser_enabled, browser_reason = render_available()
    providers_data.append(
        {
            "id": "browser",
            "type": "render",
            "enabled": browser_enabled,
            "reason": browser_reason,
            "required_env": [],
        }
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

    if wants_plain(args):
        for item in providers_data:
            print(item["id"])
        return ExitCode.OK

    if not wants_json(args):
        for item in providers_data:
            status = "enabled" if item["enabled"] else f"disabled ({item['reason']})"
            print(f"{item['type']}: {item['id']} - {status}")
        return ExitCode.OK

    meta = EnvelopeMeta(
        duration_ms=int((time.time() - start) * 1000),
        providers=[str(p["id"]) for p in providers_data],
    )
    return envelope_and_exit(
        args=args,
        command="providers",
        ok=True,
        data={"providers": providers_data},
        warnings=warnings,
        error=None,
        meta=meta,
    )
