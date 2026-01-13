from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import pytest

import wstk.cli as cli
import wstk.commands.pipeline_cmd as pipeline_cmd
from wstk.errors import ExitCode
from wstk.fetch.http import FetchResult
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


def _fetch_result(url: str, *, tmp_path: Path, html: str) -> FetchResult:
    body = html.encode("utf-8")
    body_path = tmp_path / "body.html"
    body_path.write_bytes(body)

    doc = Document.new(url=url, fetch_method="http")
    doc = Document(
        url=doc.url,
        fetched_at=doc.fetched_at,
        fetch_method=doc.fetch_method,
        http=HttpInfo(status=200, final_url=url, headers={"content-type": "text/html"}),
        artifact=ArtifactInfo(
            body_path=str(body_path),
            content_type="text/html",
            bytes=len(body),
        ),
        extracted=None,
    )
    return FetchResult(document=doc, body=body, cache_hit=None)


def test_pipeline_plan_prefers_domain(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _FakeSearchProvider(
        results=[
            SearchResultItem(
                title="Blog",
                url="https://example.com/post",
                snippet="blog",
                published_at=None,
                source_provider="fake",
            ),
            SearchResultItem(
                title="Docs",
                url="https://docs.example.com/guide",
                snippet="docs",
                published_at=None,
                source_provider="fake",
            ),
        ]
    )

    monkeypatch.setattr(
        pipeline_cmd.search_registry,
        "select_search_provider",
        lambda *_a, **_k: (provider, ["fake"]),
    )

    exit_code = cli.main(
        [
            "--json",
            "pipeline",
            "--plan",
            "--prefer-domains",
            "docs.example.com",
            "test",
        ]
    )
    assert exit_code == ExitCode.OK

    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    candidates = payload["data"]["candidates"]
    assert candidates[0]["url"] == "https://docs.example.com/guide"
    assert candidates[0]["reason"] == "preferred_domain"


def test_pipeline_extracts_document(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    provider = _FakeSearchProvider(
        results=[
            SearchResultItem(
                title="Doc",
                url="https://example.com/page",
                snippet="snippet",
                published_at=None,
                source_provider="fake",
            )
        ]
    )

    monkeypatch.setattr(
        pipeline_cmd.search_registry,
        "select_search_provider",
        lambda *_a, **_k: (provider, ["fake"]),
    )

    def fake_fetch(url: str, *, settings) -> FetchResult:
        return _fetch_result(
            url,
            tmp_path=tmp_path,
            html="<html><body><h1>Hello</h1><p>World</p></body></html>",
        )

    monkeypatch.setattr(pipeline_cmd, "fetch_url", fake_fetch)

    exit_code = cli.main(["--json", "pipeline", "test"])
    assert exit_code == ExitCode.OK

    payload = json.loads(capsys.readouterr().out)
    doc = payload["data"]["documents"][0]
    extracted = doc["extracted"]
    content = (extracted.get("markdown") or "") + (extracted.get("text") or "")
    assert "Hello" in content
