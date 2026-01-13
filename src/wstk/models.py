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
class RenderInfo:
    engine: str
    dom_path: str | None
    screenshot_path: str | None
    headful: bool
    profile: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "engine": self.engine,
            "dom_path": self.dom_path,
            "screenshot_path": self.screenshot_path,
            "headful": self.headful,
            "profile": self.profile,
        }


@dataclass(frozen=True, slots=True)
class DocLink:
    text: str
    url: str

    def to_dict(self) -> dict[str, Any]:
        return {"text": self.text, "url": self.url}


@dataclass(frozen=True, slots=True)
class DocSection:
    heading: str | None
    level: int | None
    content: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "heading": self.heading,
            "level": self.level,
            "content": self.content,
        }


@dataclass(frozen=True, slots=True)
class DocContent:
    title: str | None
    sections: list[DocSection]
    links: list[DocLink]

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "sections": [section.to_dict() for section in self.sections],
            "links": [link.to_dict() for link in self.links],
        }


@dataclass(frozen=True, slots=True)
class ExtractedContent:
    title: str | None
    language: str | None
    extraction_method: str
    markdown: str | None
    text: str | None
    doc: DocContent | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "language": self.language,
            "extraction_method": self.extraction_method,
            "markdown": self.markdown,
            "text": self.text,
            "doc": None if self.doc is None else self.doc.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class Document:
    url: str
    fetched_at: str
    fetch_method: str
    http: HttpInfo | None = None
    artifact: ArtifactInfo | None = None
    render: RenderInfo | None = None
    extracted: ExtractedContent | None = None

    @staticmethod
    def new(url: str, fetch_method: str) -> Document:
        return Document(url=url, fetched_at=_rfc3339_now(), fetch_method=fetch_method)

    def with_extracted(self, extracted: ExtractedContent) -> Document:
        return Document(
            url=self.url,
            fetched_at=self.fetched_at,
            fetch_method=self.fetch_method,
            http=self.http,
            artifact=self.artifact,
            render=self.render,
            extracted=extracted,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "fetched_at": self.fetched_at,
            "fetch_method": self.fetch_method,
            "http": None if self.http is None else self.http.to_dict(),
            "artifact": None if self.artifact is None else self.artifact.to_dict(),
            "render": None if self.render is None else self.render.to_dict(),
            "extracted": None if self.extracted is None else self.extracted.to_dict(),
        }
