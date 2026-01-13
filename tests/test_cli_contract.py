from __future__ import annotations

import json
from dataclasses import dataclass, field

import pytest

import wstk.cli as cli
import wstk.cli_support as cli_support
import wstk.commands.extract_cmd as extract_cmd
import wstk.commands.fetch_cmd as fetch_cmd
import wstk.commands.search_cmd as search_cmd
import wstk.robots as robots
from wstk.errors import ExitCode
from wstk.fetch.http import FetchResult, FetchSettings
from wstk.models import ArtifactInfo, Document, HttpInfo
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


class _RecordingSearchProvider(SearchProvider):
    def __init__(self, results: list[SearchResultItem]) -> None:
        self.id = "recording"
        self._results = list(results)
        self.last_query: SearchQuery | None = None

    def is_enabled(self) -> tuple[bool, str | None]:
        return True, None

    def search(self, query: SearchQuery, *, include_raw: bool) -> list[SearchResultItem]:
        self.last_query = query
        return list(self._results)


def _make_fetch_result(url: str, body: bytes = b"<html></html>") -> FetchResult:
    doc = Document.new(url=url, fetch_method="http")
    doc = Document(
        url=doc.url,
        fetched_at=doc.fetched_at,
        fetch_method=doc.fetch_method,
        http=HttpInfo(status=200, final_url=url, headers={"content-type": "text/html"}),
        artifact=ArtifactInfo(
            body_path=None,
            content_type="text/html",
            bytes=len(body),
        ),
        extracted=None,
    )
    return FetchResult(document=doc, body=body, cache_hit=None)


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
    assert "docs" in lines


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


def test_search_site_augments_query_and_filters(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = _RecordingSearchProvider(
        results=[
            SearchResultItem(
                title="Doc",
                url="https://docs.example.com/a",
                snippet=None,
                published_at=None,
                source_provider="fake",
            ),
            SearchResultItem(
                title="Other",
                url="https://other.com/b",
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

    exit_code = cli.main(["--plain", "search", "test", "--site", "https://example.com/docs"])
    assert exit_code == ExitCode.OK
    assert provider.last_query is not None
    assert "site:example.com" in provider.last_query.query
    assert capsys.readouterr().out.splitlines() == ["https://docs.example.com/a"]


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


def test_fetch_accept_header_override(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, dict[str, str]] = {}

    def fake_fetch(url: str, *, settings: FetchSettings) -> FetchResult:
        captured["headers"] = dict(settings.headers)
        return _make_fetch_result(url)

    monkeypatch.setattr(fetch_cmd, "fetch_url", fake_fetch)

    exit_code = cli.main(
        ["--json", "fetch", "https://example.com/", "--accept", "application/json"]
    )
    assert exit_code == ExitCode.OK
    assert captured["headers"]["accept"] == "application/json"
    json.loads(capsys.readouterr().out)


def test_extract_accept_header_override(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, dict[str, str]] = {}

    def fake_fetch(url: str, *, settings: FetchSettings) -> FetchResult:
        captured["headers"] = dict(settings.headers)
        return _make_fetch_result(url)

    monkeypatch.setattr(extract_cmd, "fetch_url", fake_fetch)

    exit_code = cli.main(
        ["--json", "extract", "https://example.com/", "--accept", "application/xml"]
    )
    assert exit_code == ExitCode.OK
    assert captured["headers"]["accept"] == "application/xml"
    json.loads(capsys.readouterr().out)


def test_fetch_robots_warn_adds_warning(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_check(
        url: str, *, user_agent: str | None, timeout: float, proxy: str | None
    ) -> robots.RobotsCheck:
        return robots.RobotsCheck(
            url=url,
            robots_url="https://example.com/robots.txt",
            allowed=False,
            status=200,
        )

    def fake_fetch(url: str, *, settings: FetchSettings) -> FetchResult:
        return _make_fetch_result(url)

    monkeypatch.setattr(cli_support.robots, "check_robots", fake_check)
    monkeypatch.setattr(fetch_cmd, "fetch_url", fake_fetch)

    exit_code = cli.main(["--json", "--robots", "warn", "fetch", "https://example.com/"])
    assert exit_code == ExitCode.OK
    payload = json.loads(capsys.readouterr().out)
    assert any("robots.txt disallows fetch" in warning for warning in payload["warnings"])


def test_fetch_robots_respect_blocks(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_check(
        url: str, *, user_agent: str | None, timeout: float, proxy: str | None
    ) -> robots.RobotsCheck:
        return robots.RobotsCheck(
            url=url,
            robots_url="https://example.com/robots.txt",
            allowed=False,
            status=200,
        )

    def fake_fetch(url: str, *, settings: FetchSettings) -> FetchResult:
        raise AssertionError("fetch should not run")

    monkeypatch.setattr(cli_support.robots, "check_robots", fake_check)
    monkeypatch.setattr(fetch_cmd, "fetch_url", fake_fetch)

    exit_code = cli.main(
        ["--json", "--robots", "respect", "fetch", "https://example.com/"]
    )
    assert exit_code == ExitCode.BLOCKED
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "robots_disallowed"


def test_fetch_robots_strict_policy_blocks(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_check(
        url: str, *, user_agent: str | None, timeout: float, proxy: str | None
    ) -> robots.RobotsCheck:
        return robots.RobotsCheck(
            url=url,
            robots_url="https://example.com/robots.txt",
            allowed=False,
            status=200,
        )

    def fake_fetch(url: str, *, settings: FetchSettings) -> FetchResult:
        raise AssertionError("fetch should not run")

    monkeypatch.setattr(cli_support.robots, "check_robots", fake_check)
    monkeypatch.setattr(fetch_cmd, "fetch_url", fake_fetch)

    exit_code = cli.main(
        [
            "--json",
            "--policy",
            "strict",
            "--allow-domain",
            "example.com",
            "fetch",
            "https://example.com/",
        ]
    )
    assert exit_code == ExitCode.BLOCKED
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "robots_disallowed"
