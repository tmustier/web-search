from __future__ import annotations

from dataclasses import dataclass

from wstk.errors import ExitCode, WstkError
from wstk.search.base import SearchProvider
from wstk.search.brave_api_provider import BraveApiSearchProvider
from wstk.search.ddgs_provider import DdgsSearchProvider


@dataclass(frozen=True, slots=True)
class SearchProviderMetadata:
    required_env: tuple[str, ...] = ()
    privacy_warning: str | None = None


@dataclass(frozen=True, slots=True)
class SearchProviderInfo:
    provider: SearchProvider
    required_env: tuple[str, ...]
    privacy_warning: str | None


_SEARCH_PROVIDER_METADATA: dict[str, SearchProviderMetadata] = {
    "brave_api": SearchProviderMetadata(
        required_env=("BRAVE_API_KEY",),
        privacy_warning="brave_api sends queries to the Brave Search API.",
    ),
    "ddgs": SearchProviderMetadata(
        privacy_warning=(
            "ddgs uses DuckDuckGo public endpoints; queries are sent to third-party services."
        ),
    ),
}


def list_search_providers(*, timeout: float, proxy: str | None) -> list[SearchProvider]:
    return [
        BraveApiSearchProvider(timeout=timeout, proxy=proxy),
        DdgsSearchProvider(),
    ]


def list_search_provider_info(*, timeout: float, proxy: str | None) -> list[SearchProviderInfo]:
    providers = list_search_providers(timeout=timeout, proxy=proxy)
    info: list[SearchProviderInfo] = []
    for provider in providers:
        meta = _SEARCH_PROVIDER_METADATA.get(provider.id, SearchProviderMetadata())
        info.append(
            SearchProviderInfo(
                provider=provider,
                required_env=meta.required_env,
                privacy_warning=meta.privacy_warning,
            )
        )
    return info


def provider_warnings(provider_id: str) -> list[str]:
    meta = _SEARCH_PROVIDER_METADATA.get(provider_id)
    if not meta or not meta.privacy_warning:
        return []
    return [meta.privacy_warning]


def append_provider_warnings(warnings: list[str], provider_id: str) -> None:
    for warning in provider_warnings(provider_id):
        if warning not in warnings:
            warnings.append(warning)


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
