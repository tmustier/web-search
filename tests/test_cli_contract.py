from __future__ import annotations

import json
from dataclasses import dataclass, field

import pytest

import wstk.cli as cli
import wstk.commands.search_cmd as search_cmd
from wstk.errors import ExitCode
from wstk.search.base import SearchProvider
from wstk.search.types import SearchQuery, SearchResultItem


@dataclass(frozen=True, slots=True)
class _FakeSearchProvider(SearchProvider):
    id: str = "fake"
    results: list[SearchResultItem] = field(default_factory=list)

    def is_enabled(self) -> tuple[bool, str | None]:
        return True, None

    def search(self, query: SearchQuery, *, include_raw: bool) -> list[SearchResultItem]:
        return list(self.results)


def test_providers_json_envelope(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = cli.main(["--json", "providers"])
    assert exit_code == ExitCode.OK

    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["ok"] is True
    assert payload["command"] == "providers"
    assert payload["version"] == "0.1.0"
    assert "providers" in payload["data"]


def test_providers_plain(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = cli.main(["--plain", "providers"])
    assert exit_code == ExitCode.OK

    lines = [line for line in capsys.readouterr().out.splitlines() if line.strip()]
    assert "ddgs" in lines
    assert "http" in lines


def test_search_plain_outputs_urls(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = _FakeSearchProvider(
        results=[
            SearchResultItem(
                title="A",
                url="https://example.com/a",
                snippet="a",
                published_at=None,
                source_provider="fake",
            ),
            SearchResultItem(
                title="B",
                url="https://example.com/b",
                snippet=None,
                published_at=None,
                source_provider="fake",
            ),
        ]
    )

    monkeypatch.setattr(
        search_cmd.search_registry,
        "select_search_provider",
        lambda *_a, **_k: (provider, ["fake"]),
    )

    exit_code = cli.main(["--plain", "search", "test"])
    assert exit_code == ExitCode.OK
    assert capsys.readouterr().out.splitlines() == [
        "https://example.com/a",
        "https://example.com/b",
    ]


def test_search_no_results_exit_3(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = _FakeSearchProvider(results=[])
    monkeypatch.setattr(
        search_cmd.search_registry,
        "select_search_provider",
        lambda *_a, **_k: (provider, ["fake"]),
    )

    exit_code = cli.main(["--plain", "search", "test"])
    assert exit_code == ExitCode.NOT_FOUND
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_search_no_results_human_prints_message(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = _FakeSearchProvider(results=[])
    monkeypatch.setattr(
        search_cmd.search_registry,
        "select_search_provider",
        lambda *_a, **_k: (provider, ["fake"]),
    )

    exit_code = cli.main(["search", "test"])
    assert exit_code == ExitCode.NOT_FOUND
    assert "no results" in capsys.readouterr().err.lower()


def test_strict_fetch_requires_allow_domain(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = cli.main(["--json", "--policy", "strict", "fetch", "https://example.com/"])
    assert exit_code == ExitCode.INVALID_USAGE
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "policy_violation"
