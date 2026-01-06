from __future__ import annotations

from wstk.errors import ExitCode, WstkError
from wstk.search.base import SearchProvider
from wstk.search.brave_api_provider import BraveApiSearchProvider
from wstk.search.ddgs_provider import DdgsSearchProvider


def list_search_providers(*, timeout: float, proxy: str | None) -> list[SearchProvider]:
    return [
        BraveApiSearchProvider(timeout=timeout, proxy=proxy),
        DdgsSearchProvider(),
    ]


def select_search_provider(
    provider_id: str,
    *,
    timeout: float,
    proxy: str | None,
) -> tuple[SearchProvider, list[str]]:
    providers = list_search_providers(timeout=timeout, proxy=proxy)
    providers_by_id = {p.id: p for p in providers}

    if provider_id != "auto":
        provider = providers_by_id.get(provider_id)
        if provider is None:
            raise WstkError(
                code="invalid_provider",
                message=f"unknown provider: {provider_id}",
                exit_code=ExitCode.INVALID_USAGE,
            )
        return provider, [provider.id]

    # auto: prefer reliability when configured
    brave = providers_by_id["brave_api"]
    brave_enabled, _ = brave.is_enabled()
    if brave_enabled:
        return brave, ["brave_api"]

    ddgs = providers_by_id["ddgs"]
    return ddgs, ["ddgs"]
