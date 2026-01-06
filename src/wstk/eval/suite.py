from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from wstk.errors import ExitCode, WstkError


@dataclass(frozen=True, slots=True)
class EvalCase:
    id: str
    query: str
    expected_domains: tuple[str, ...] = ()
    expected_urls: tuple[str, ...] = ()
    k: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "query": self.query,
            "expected_domains": list(self.expected_domains),
            "expected_urls": list(self.expected_urls),
            "k": self.k,
        }


@dataclass(frozen=True, slots=True)
class EvalSuite:
    path: str
    cases: tuple[EvalCase, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "case_count": len(self.cases),
            "cases": [c.to_dict() for c in self.cases],
        }


def _coerce_str_list(value: object, *, field_name: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if not isinstance(value, list):
        raise WstkError(
            code="invalid_suite",
            message=f"{field_name} must be a list of strings",
            exit_code=ExitCode.INVALID_USAGE,
        )
    items: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise WstkError(
                code="invalid_suite",
                message=f"{field_name} must be a list of strings",
                exit_code=ExitCode.INVALID_USAGE,
            )
        if item.strip():
            items.append(item.strip())
    return tuple(items)


def _parse_case(raw: object, *, index: int) -> EvalCase:
    if not isinstance(raw, dict):
        raise WstkError(
            code="invalid_suite",
            message="suite cases must be JSON objects",
            exit_code=ExitCode.INVALID_USAGE,
        )

    case_id = raw.get("id")
    if case_id is None:
        case_id = f"case-{index}"
    if not isinstance(case_id, str) or not case_id.strip():
        raise WstkError(
            code="invalid_suite",
            message="case id must be a non-empty string",
            exit_code=ExitCode.INVALID_USAGE,
        )

    query = raw.get("query")
    if not isinstance(query, str) or not query.strip():
        raise WstkError(
            code="invalid_suite",
            message=f"case {case_id!r} query must be a non-empty string",
            exit_code=ExitCode.INVALID_USAGE,
        )

    expected_domains = _coerce_str_list(raw.get("expected_domains"), field_name="expected_domains")
    expected_urls = _coerce_str_list(raw.get("expected_urls"), field_name="expected_urls")

    k = raw.get("k")
    if k is not None:
        if not isinstance(k, int) or k <= 0:
            raise WstkError(
                code="invalid_suite",
                message=f"case {case_id!r} k must be a positive integer",
                exit_code=ExitCode.INVALID_USAGE,
            )

    return EvalCase(
        id=case_id.strip(),
        query=query.strip(),
        expected_domains=expected_domains,
        expected_urls=expected_urls,
        k=k,
    )


def _parse_json_cases(payload: object) -> list[EvalCase]:
    if isinstance(payload, list):
        return [_parse_case(item, index=i + 1) for i, item in enumerate(payload)]
    if isinstance(payload, dict) and isinstance(payload.get("cases"), list):
        cases = payload.get("cases")
        assert isinstance(cases, list)
        return [_parse_case(item, index=i + 1) for i, item in enumerate(cases)]
    raise WstkError(
        code="invalid_suite",
        message="suite must be a JSON array or an object with a 'cases' array",
        exit_code=ExitCode.INVALID_USAGE,
    )


def load_suite(path: str) -> EvalSuite:
    if path == "-":
        content = sys.stdin.read()
        suite_path = "-"
    else:
        suite_path = path
        content = Path(path).read_text(encoding="utf-8")

    suffix = "" if path == "-" else Path(path).suffix.lower()

    if suffix == ".jsonl":
        cases: list[EvalCase] = []
        for idx, line in enumerate(content.splitlines(), start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            try:
                raw = json.loads(stripped)
            except json.JSONDecodeError as e:
                raise WstkError(
                    code="invalid_suite",
                    message=f"invalid JSON on line {idx}: {e.msg}",
                    exit_code=ExitCode.INVALID_USAGE,
                    details={"line": idx},
                ) from e
            cases.append(_parse_case(raw, index=len(cases) + 1))
        if not cases:
            raise WstkError(
                code="invalid_suite",
                message="suite contains no cases",
                exit_code=ExitCode.INVALID_USAGE,
            )
        return EvalSuite(path=suite_path, cases=tuple(cases))

    try:
        payload = json.loads(content)
    except json.JSONDecodeError as e:
        raise WstkError(
            code="invalid_suite",
            message=f"invalid JSON suite: {e.msg}",
            exit_code=ExitCode.INVALID_USAGE,
        ) from e

    cases = _parse_json_cases(payload)
    if not cases:
        raise WstkError(
            code="invalid_suite",
            message="suite contains no cases",
            exit_code=ExitCode.INVALID_USAGE,
        )
    return EvalSuite(path=suite_path, cases=tuple(cases))

