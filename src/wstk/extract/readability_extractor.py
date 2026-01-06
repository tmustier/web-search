from __future__ import annotations

from bs4 import BeautifulSoup
from markdownify import markdownify as to_markdown
from readability import Document as ReadabilityDocument

from wstk.models import ExtractedContent


def extract_readability(
    html: str, *, include_markdown: bool, include_text: bool
) -> ExtractedContent:
    doc = ReadabilityDocument(html)
    title = doc.short_title() or None
    summary_html = doc.summary(html_partial=True)

    markdown: str | None = None
    text: str | None = None

    if include_markdown:
        markdown = to_markdown(summary_html, heading_style="ATX")
        markdown = markdown.strip() or None

    if include_text:
        soup = BeautifulSoup(summary_html, "lxml")
        text = soup.get_text(separator="\n", strip=True) or None

    return ExtractedContent(
        title=title,
        language=None,
        extraction_method="readability_lxml+markdownify",
        markdown=markdown,
        text=text,
    )
