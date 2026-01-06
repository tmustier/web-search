from __future__ import annotations

from datetime import timedelta

import pytest

from wstk.timeutil import parse_duration


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("30s", timedelta(seconds=30)),
        ("15m", timedelta(minutes=15)),
        ("24h", timedelta(hours=24)),
        ("7d", timedelta(days=7)),
        ("2w", timedelta(days=14)),
        ("  5D  ", timedelta(days=5)),
    ],
)
def test_parse_duration(value: str, expected: timedelta) -> None:
    assert parse_duration(value) == expected


def test_parse_duration_rejects_invalid() -> None:
    with pytest.raises(ValueError):
        parse_duration("bogus")
