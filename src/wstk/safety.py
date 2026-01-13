from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from wstk.urlutil import redact_url

_PROMPT_INJECTION_PATTERNS = {
    "ignore_instructions": re.compile(
        r"ignore\s+(?:all|previous|above)\s+instructions", re.IGNORECASE
    ),
    "system_prompt": re.compile(r"system\s+prompt", re.IGNORECASE),
    "developer_message": re.compile(r"developer\s+message", re.IGNORECASE),
    "reveal_instructions": re.compile(
        r"(reveal|show|leak)\s+(?:the\s+)?(system|developer)\s+prompt",
        re.IGNORECASE,
    ),
    "override_safety": re.compile(
        r"(bypass|override)\s+(?:safety|security|policy|guardrails)",
        re.IGNORECASE,
    ),
}

_KEY_VALUE_PATTERN = re.compile(
    r"\b(api[_-]?key|token|secret|password|passwd|pwd|session|signature)\b(\s*[:=]\s*)([^\s\"']{6,})",
    re.IGNORECASE,
)

_SECRET_PATTERNS = [
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bASIA[0-9A-Z]{16}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
    re.compile(r"\bsk_(?:live|test)_[A-Za-z0-9]{16,}\b"),
    re.compile(r"\beyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\b"),
    re.compile(r"\bbearer\s+[a-z0-9._\-+/=]{10,}\b", re.IGNORECASE),
]

_EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_URL_PATTERN = re.compile(r"https?://[^\s\"'<>]+")


def detect_prompt_injection(text: str) -> list[str]:
    if not text:
        return []
    matches: list[str] = []
    for label, pattern in _PROMPT_INJECTION_PATTERNS.items():
        if pattern.search(text):
            matches.append(label)
    return matches


def redact_text(text: str) -> str:
    if not text:
        return text
    redacted = _URL_PATTERN.sub(lambda match: redact_url(match.group(0)), text)
    redacted = _KEY_VALUE_PATTERN.sub(_redact_key_value, redacted)
    for pattern in _SECRET_PATTERNS:
        redacted = pattern.sub("[REDACTED]", redacted)
    redacted = _EMAIL_PATTERN.sub("[REDACTED_EMAIL]", redacted)
    return redacted


def redact_payload(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: redact_payload(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_payload(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_payload(item) for item in value)
    if isinstance(value, str):
        return _redact_string(value)
    return value


def _redact_key_value(match: re.Match[str]) -> str:
    return f"{match.group(1)}{match.group(2)}REDACTED"


def _redact_string(value: str) -> str:
    if _looks_like_url(value):
        return redact_text(redact_url(value))
    return redact_text(value)


def _looks_like_url(value: str) -> bool:
    parsed = urlparse(value)
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        return True
    if parsed.scheme == "file" and parsed.path:
        return True
    return False
