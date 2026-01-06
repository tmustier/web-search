from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class ExitCode:
    OK = 0
    RUNTIME_ERROR = 1
    INVALID_USAGE = 2
    NOT_FOUND = 3
    BLOCKED = 4
    NEEDS_RENDER = 5


@dataclass(frozen=True, slots=True)
class WstkError(Exception):
    code: str
    message: str
    exit_code: int = ExitCode.RUNTIME_ERROR
    details: dict[str, Any] | None = None

    def to_error_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "details": self.details,
        }
