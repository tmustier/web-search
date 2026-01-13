from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import pytest

import wstk.cli as cli
import wstk.commands.eval_cmd as eval_cmd
import wstk.eval.runner as eval_runner
from wstk.errors import ExitCode, WstkError
from wstk.fetch.http import FetchResult, FetchSettings
from wstk.models import ArtifactInfo, Document, HttpInfo
from wstk.search.base import SearchProvider
from wstk.search.types import SearchQuery, SearchResultItem


@dataclass(frozen=True, slots=True)
class _FakeSearchProvider(SearchProvider):
    id: str = "fake"
    results: list[SearchResultItem] = field(default_factory=list)
    error: WstkError | None = None

    def is_enabled(self) -> tuple[bool, str | None]:
        return True, None

    def search(self, query: SearchQuery, *, include_raw: bool) -> list[SearchResultItem]:
        if self.error is not None:
            raise self.error
        return list(self.results)


def _patch_fetch(monkeypatch: pytest.MonkeyPatch, *, body: bytes | None = None) -> None:
    if body is None:
        body = b"<html><body><h1>Test</h1><p>Hello world</p></body></html>"

    def fake_fetch(url: str, *, settings: FetchSettings) -> FetchResult:
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

    monkeypatch.setattr(eval_runner, "fetch_url", fake_fetch)


def _write_suite(tmp_path: Path, *, expected_domains: list[str]) -> Path:
    suite_path = tmp_path / "suite.jsonl"
    suite_path.write_text(
        json.dumps(
            {
                "id": "case-1",
                "query": "test query",
                "expected_domains": expected_domains,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return suite_path


def test_eval_json_envelope_ok(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    provider = _FakeSearchProvider(
        results=[
            SearchResultItem(
                title="A",
                url="https://example.com/a",
                snippet=None,
                published_at=None,
                source_provider="fake",
            )
        ]
    )
    monkeypatch.setattr(
        eval_cmd.search_registry,
        "select_search_provider",
        lambda *_a, **_k: (provider, ["fake"]),
    )
    _patch_fetch(monkeypatch)

    suite_path = _write_suite(tmp_path, expected_domains=["example.com"])
    exit_code = cli.main(
        [
            "--json",
            "--cache-dir",
            str(tmp_path / "cache"),
            "eval",
            "--suite",
            str(suite_path),
            "--provider",
            "fake",
        ]
    )
    assert exit_code == ExitCode.OK

    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["command"] == "eval"
    assert payload["data"]["summary"]["by_provider"][0]["provider"] == "fake"
    fetch_summary = payload["data"]["summary"]["fetch"]["by_provider"][0]
    extract_summary = payload["data"]["summary"]["extract"]["by_provider"][0]
    assert fetch_summary["attempts"] == 1
    assert fetch_summary["success"] == 1
    assert extract_summary["attempts"] == 1


def test_eval_fail_on_miss_returns_exit_1(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    provider = _FakeSearchProvider(
        results=[
            SearchResultItem(
                title="A",
                url="https://example.com/a",
                snippet=None,
                published_at=None,
                source_provider="fake",
            )
        ]
    )
    monkeypatch.setattr(
        eval_cmd.search_registry,
        "select_search_provider",
        lambda *_a, **_k: (provider, ["fake"]),
    )
    _patch_fetch(monkeypatch)

    suite_path = _write_suite(tmp_path, expected_domains=["missing.example"])
    exit_code = cli.main(
        [
            "--json",
            "--cache-dir",
            str(tmp_path / "cache"),
            "eval",
            "--suite",
            str(suite_path),
            "--provider",
            "fake",
            "--fail-on",
            "miss",
        ]
    )
    assert exit_code == ExitCode.RUNTIME_ERROR
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "eval_failed"


def test_eval_fail_on_error_returns_exit_1(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    provider = _FakeSearchProvider(
        error=WstkError(code="provider_error", message="boom", exit_code=ExitCode.RUNTIME_ERROR)
    )
    monkeypatch.setattr(
        eval_cmd.search_registry,
        "select_search_provider",
        lambda *_a, **_k: (provider, ["fake"]),
    )

    suite_path = _write_suite(tmp_path, expected_domains=["example.com"])
    exit_code = cli.main(
        [
            "--json",
            "--cache-dir",
            str(tmp_path / "cache"),
            "eval",
            "--suite",
            str(suite_path),
            "--provider",
            "fake",
        ]
    )
    assert exit_code == ExitCode.RUNTIME_ERROR
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "eval_failed"
