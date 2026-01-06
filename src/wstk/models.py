from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


def _rfc3339_now() -> str:
    return datetime.now(tz=UTC).isoformat()


@dataclass(frozen=True, slots=True)
class HttpInfo:
    status: int
    final_url: str
    headers: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "final_url": self.final_url,
            "headers": self.headers,
        }


@dataclass(frozen=True, slots=True)
class ArtifactInfo:
    body_path: str | None
    content_type: str | None
    bytes: int | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "body_path": self.body_path,
            "content_type": self.content_type,
            "bytes": self.bytes,
        }


@dataclass(frozen=True, slots=True)
class ExtractedContent:
    title: str | None
    language: str | None
    extraction_method: str
    markdown: str | None
    text: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "language": self.language,
            "extraction_method": self.extraction_method,
            "markdown": self.markdown,
            "text": self.text,
        }


@dataclass(frozen=True, slots=True)
class Document:
    url: str
    fetched_at: str
    fetch_method: str
    http: HttpInfo | None = None
    artifact: ArtifactInfo | None = None
    extracted: ExtractedContent | None = None

    @staticmethod
    def new(url: str, fetch_method: str) -> Document:
        return Document(url=url, fetched_at=_rfc3339_now(), fetch_method=fetch_method)

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "fetched_at": self.fetched_at,
            "fetch_method": self.fetch_method,
            "http": None if self.http is None else self.http.to_dict(),
            "artifact": None if self.artifact is None else self.artifact.to_dict(),
            "extracted": None if self.extracted is None else self.extracted.to_dict(),
        }
