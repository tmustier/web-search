from __future__ import annotations

import json
from pathlib import Path

import pytest

import wstk.cli as cli
import wstk.commands.extract_cmd as extract_cmd
import wstk.commands.render_cmd as render_cmd
from wstk.errors import ExitCode, WstkError
from wstk.models import ArtifactInfo, Document, HttpInfo, RenderInfo
from wstk.render.browser import RenderResult


def _render_result(url: str, *, dom_path: Path, html: str) -> RenderResult:
    html_bytes = html.encode("utf-8")
    doc = Document.new(url=url, fetch_method="browser")
    doc = Document(
        url=doc.url,
        fetched_at=doc.fetched_at,
        fetch_method=doc.fetch_method,
        http=HttpInfo(status=200, final_url=url, headers={"content-type": "text/html"}),
        artifact=ArtifactInfo(
            body_path=str(dom_path),
            content_type="text/html",
            bytes=len(html_bytes),
        ),
        render=RenderInfo(
            engine="playwright",
            dom_path=str(dom_path),
            screenshot_path=None,
            headful=False,
            profile=None,
        ),
        extracted=None,
    )
    return RenderResult(document=doc, html=html)


def test_render_json_envelope(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    dom_path = tmp_path / "render.html"

    def fake_render(url: str, *, settings) -> RenderResult:
        return _render_result(
            url,
            dom_path=dom_path,
            html="<html><body>ok</body></html>",
        )

    monkeypatch.setattr(render_cmd, "render_url", fake_render)

    exit_code = cli.main(
        [
            "--json",
            "--evidence-dir",
            str(tmp_path),
            "render",
            "https://example.com",
        ]
    )
    assert exit_code == ExitCode.OK

    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["command"] == "render"
    assert payload["data"]["document"]["fetch_method"] == "browser"


def test_render_plain_outputs_dom_path(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    dom_path = tmp_path / "render.html"

    def fake_render(url: str, *, settings) -> RenderResult:
        return _render_result(
            url,
            dom_path=dom_path,
            html="<html><body>ok</body></html>",
        )

    monkeypatch.setattr(render_cmd, "render_url", fake_render)

    exit_code = cli.main(
        [
            "--plain",
            "--evidence-dir",
            str(tmp_path),
            "render",
            "https://example.com",
        ]
    )
    assert exit_code == ExitCode.OK
    assert capsys.readouterr().out.strip() == str(dom_path)


def test_extract_browser_uses_render(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    dom_path = tmp_path / "render.html"

    def fake_render(url: str, *, settings) -> RenderResult:
        return _render_result(
            url,
            dom_path=dom_path,
            html="<html><body><h1>Hello</h1></body></html>",
        )

    monkeypatch.setattr(extract_cmd, "render_url", fake_render)

    exit_code = cli.main(
        [
            "--json",
            "--evidence-dir",
            str(tmp_path),
            "extract",
            "--method",
            "browser",
            "https://example.com",
        ]
    )
    assert exit_code == ExitCode.OK
    payload = json.loads(capsys.readouterr().out)
    assert payload["data"]["document"]["fetch_method"] == "browser"
    assert "browser" in payload["meta"]["providers"]
    assert "Hello" in (payload["data"]["document"]["extracted"]["markdown"] or "")


def test_extract_auto_falls_back_to_render(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    dom_path = tmp_path / "render.html"

    def fake_fetch(*_args, **_kwargs):
        raise WstkError(
            code="needs_render",
            message="render required",
            exit_code=ExitCode.NEEDS_RENDER,
            details={},
        )

    def fake_render(url: str, *, settings) -> RenderResult:
        return _render_result(
            url,
            dom_path=dom_path,
            html="<html><body><h1>Hello</h1></body></html>",
        )

    monkeypatch.setattr(extract_cmd, "fetch_url", fake_fetch)
    monkeypatch.setattr(extract_cmd, "render_url", fake_render)

    exit_code = cli.main(
        [
            "--json",
            "--policy",
            "permissive",
            "--evidence-dir",
            str(tmp_path),
            "extract",
            "--method",
            "auto",
            "https://example.com",
        ]
    )
    assert exit_code == ExitCode.OK
    payload = json.loads(capsys.readouterr().out)
    assert payload["data"]["document"]["fetch_method"] == "browser"
    assert "browser" in payload["meta"]["providers"]
