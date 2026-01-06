from __future__ import annotations

import json
from pathlib import Path

import pytest

from wstk.errors import ExitCode, WstkError
from wstk.eval.suite import load_suite


def test_load_suite_jsonl(tmp_path: Path) -> None:
    suite_path = tmp_path / "suite.jsonl"
    suite_path.write_text(
        "\n".join(
            [
                "# comment",
                "",
                json.dumps(
                    {
                        "id": "a",
                        "query": "python venv",
                        "expected_domains": ["docs.python.org"],
                    }
                ),
                json.dumps(
                    {
                        "id": "b",
                        "query": "go mod init",
                        "expected_urls": ["https://go.dev/ref/mod"],
                        "k": 5,
                    }
                ),
            ]
        ),
        encoding="utf-8",
    )

    suite = load_suite(str(suite_path))
    assert suite.path.endswith("suite.jsonl")
    assert len(suite.cases) == 2
    assert suite.cases[0].id == "a"
    assert suite.cases[0].expected_domains == ("docs.python.org",)
    assert suite.cases[1].expected_urls == ("https://go.dev/ref/mod",)
    assert suite.cases[1].k == 5


def test_load_suite_json_array(tmp_path: Path) -> None:
    suite_path = tmp_path / "suite.json"
    suite_path.write_text(
        json.dumps(
            [
                {
                    "id": "a",
                    "query": "mdn fetch",
                    "expected_domains": ["developer.mozilla.org"],
                }
            ]
        ),
        encoding="utf-8",
    )
    suite = load_suite(str(suite_path))
    assert len(suite.cases) == 1
    assert suite.cases[0].id == "a"


def test_load_suite_missing_query_is_invalid_usage(tmp_path: Path) -> None:
    suite_path = tmp_path / "suite.json"
    suite_path.write_text(json.dumps([{"id": "a"}]), encoding="utf-8")
    with pytest.raises(WstkError) as exc:
        load_suite(str(suite_path))
    assert exc.value.exit_code == ExitCode.INVALID_USAGE

