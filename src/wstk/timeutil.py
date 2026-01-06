from __future__ import annotations

import re
from datetime import timedelta

_DURATION_RE = re.compile(r"^\s*(\d+)\s*([smhdw])\s*$", re.IGNORECASE)


def parse_duration(value: str) -> timedelta:
    """Parse a short duration like '30s', '15m', '24h', '7d', '2w'."""
    match = _DURATION_RE.match(value)
    if not match:
        raise ValueError(f"invalid duration: {value!r} (expected e.g. 30s, 15m, 24h, 7d)")

    amount = int(match.group(1))
    unit = match.group(2).lower()
    if unit == "s":
        return timedelta(seconds=amount)
    if unit == "m":
        return timedelta(minutes=amount)
    if unit == "h":
        return timedelta(hours=amount)
    if unit == "d":
        return timedelta(days=amount)
    if unit == "w":
        return timedelta(days=amount * 7)

    raise ValueError(f"invalid duration unit: {unit!r}")
