from __future__ import annotations

import argparse
import time

import wstk.search.registry as search_registry
from wstk.cli_support import envelope_and_exit
from wstk.errors import ExitCode
from wstk.output import EnvelopeMeta


def run(*, args: argparse.Namespace, start: float, warnings: list[str]) -> int:
    providers_data: list[dict[str, object]] = []

    for p in search_registry.list_search_providers(timeout=float(args.timeout), proxy=args.proxy):
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
    return envelope_and_exit(
        args=args,
        command="providers",
        ok=True,
        data={"providers": providers_data},
        warnings=warnings,
        error=None,
        meta=meta,
    )
