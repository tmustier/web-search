from __future__ import annotations

from wstk.extract.docs_extractor import extract_docs, looks_like_docs
from wstk.extract.readability_extractor import extract_readability
from wstk.models import DocContent, DocSection, ExtractedContent


def choose_strategy(html: str) -> str:
    return "docs" if looks_like_docs(html) else "readability"


def extract_html(
    html: str, *, strategy: str, include_markdown: bool, include_text: bool
) -> ExtractedContent:
    if strategy == "docs":
        return extract_docs(html, include_markdown=include_markdown, include_text=include_text)
    return extract_readability(
        html, include_markdown=include_markdown, include_text=include_text
    )


def apply_limits(
    extracted: ExtractedContent, *, max_chars: int, max_tokens: int
) -> ExtractedContent:
    if max_chars <= 0 and max_tokens <= 0:
        return extracted

    markdown = _truncate_value(extracted.markdown, max_chars, max_tokens)
    text = _truncate_value(extracted.text, max_chars, max_tokens)
    doc = extracted.doc
    if doc is not None:
        sections = _truncate_sections(doc.sections, max_chars, max_tokens)
        doc = DocContent(title=doc.title, sections=sections, links=doc.links)

    return ExtractedContent(
        title=extracted.title,
        language=extracted.language,
        extraction_method=extracted.extraction_method,
        markdown=markdown,
        text=text,
        doc=doc,
    )


def select_extracted_output(
    extracted: ExtractedContent,
    *,
    prefer_markdown: bool = True,
    markdown_only: bool = False,
    text_only: bool = False,
) -> str:
    markdown = extracted.markdown or ""
    text = extracted.text or ""

    if markdown_only and markdown:
        return markdown
    if text_only and text:
        return text
    if prefer_markdown:
        return markdown or text
    return text or markdown


def text_for_scan(extracted: ExtractedContent) -> str:
    if extracted.markdown:
        return extracted.markdown
    if extracted.text:
        return extracted.text
    doc = extracted.doc
    if doc is None:
        return ""
    sections = [section.content for section in doc.sections if section.content]
    return "\n".join(sections)


def _truncate_value(value: str | None, max_chars: int, max_tokens: int) -> str | None:
    if value is None:
        return None
    truncated = value
    if max_tokens > 0:
        tokens = truncated.split()
        if len(tokens) > max_tokens:
            truncated = " ".join(tokens[:max_tokens])
    if max_chars > 0 and len(truncated) > max_chars:
        truncated = truncated[:max_chars]
    return truncated or None


def _truncate_sections(
    sections: list[DocSection], max_chars: int, max_tokens: int
) -> list[DocSection]:
    if max_chars <= 0 and max_tokens <= 0:
        return sections

    remaining_chars = max_chars if max_chars > 0 else None
    remaining_tokens = max_tokens if max_tokens > 0 else None
    truncated_sections: list[DocSection] = []

    for section in sections:
        content, remaining_chars, remaining_tokens = _truncate_with_budget(
            section.content,
            remaining_chars,
            remaining_tokens,
        )
        truncated_sections.append(
            DocSection(
                heading=section.heading,
                level=section.level,
                content=content,
            )
        )
        if remaining_chars is not None and remaining_chars <= 0:
            break
        if remaining_tokens is not None and remaining_tokens <= 0:
            break

    return truncated_sections


def _truncate_with_budget(
    value: str | None,
    remaining_chars: int | None,
    remaining_tokens: int | None,
) -> tuple[str | None, int | None, int | None]:
    if value is None:
        return None, remaining_chars, remaining_tokens

    truncated = value
    if remaining_chars is not None and len(truncated) > remaining_chars:
        truncated = truncated[:remaining_chars]

    if remaining_tokens is not None:
        tokens = truncated.split()
        if len(tokens) > remaining_tokens:
            truncated = " ".join(tokens[:remaining_tokens])
            tokens_used = remaining_tokens
        else:
            tokens_used = len(tokens)
        remaining_tokens -= tokens_used

    if remaining_chars is not None:
        remaining_chars -= len(truncated)

    truncated = truncated.strip() or None
    return truncated, remaining_chars, remaining_tokens
