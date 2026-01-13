from __future__ import annotations

import re

from bs4 import BeautifulSoup, Tag
from markdownify import markdownify as to_markdown

from wstk.models import DocContent, DocLink, DocSection, ExtractedContent

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")


def looks_like_docs(html: str) -> bool:
    soup = BeautifulSoup(html, "lxml")
    root = _content_root(soup)

    headings = root.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])
    code_blocks = root.find_all("pre")
    nav_blocks = root.find_all(["nav", "aside"])
    toc_blocks = root.find_all(class_=re.compile(r"toc|sidebar|nav|menu", re.I))

    if len(code_blocks) >= 1 and len(headings) >= 2:
        return True
    if len(headings) >= 6:
        return True
    if (nav_blocks or toc_blocks) and len(headings) >= 2:
        return True
    return False


def extract_docs(
    html: str, *, include_markdown: bool, include_text: bool
) -> ExtractedContent:
    soup = BeautifulSoup(html, "lxml")
    _strip_unwanted(soup)
    root = _content_root(soup)
    title = _title_from(soup, root)

    doc_markdown = to_markdown(str(root), heading_style="ATX").strip()
    markdown = doc_markdown or None
    if not include_markdown:
        markdown = None

    text = None
    if include_text:
        text = root.get_text(separator="\n", strip=True) or None

    sections = _sections_from_markdown(doc_markdown)
    links = _links_from_root(root)

    doc = DocContent(title=title, sections=sections, links=links)
    return ExtractedContent(
        title=title,
        language=None,
        extraction_method="docs_lxml+markdownify",
        markdown=markdown,
        text=text,
        doc=doc,
    )


def _strip_unwanted(soup: BeautifulSoup) -> None:
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()


def _content_root(soup: BeautifulSoup) -> Tag:
    for selector in ["main", "article"]:
        found = soup.find(selector)
        if found is not None:
            return found
    return soup.body or soup


def _title_from(soup: BeautifulSoup, root: Tag) -> str | None:
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
        if title:
            return title
    heading = root.find(["h1", "h2"])
    if heading:
        text = heading.get_text(separator=" ", strip=True)
        return text or None
    return None


def _links_from_root(root: BeautifulSoup) -> list[DocLink]:
    links: list[DocLink] = []
    for anchor in root.find_all("a", href=True):
        href = str(anchor.get("href", "")).strip()
        if not href:
            continue
        text = anchor.get_text(separator=" ", strip=True) or href
        links.append(DocLink(text=text, url=href))
    return links


def _sections_from_markdown(markdown: str) -> list[DocSection]:
    sections: list[DocSection] = []
    current_heading: str | None = None
    current_level: int | None = None
    current_lines: list[str] = []

    def flush() -> None:
        nonlocal current_heading, current_level, current_lines
        if current_heading is None and not current_lines:
            return
        content = "\n".join(current_lines).strip() or None
        sections.append(
            DocSection(heading=current_heading, level=current_level, content=content)
        )
        current_heading = None
        current_level = None
        current_lines = []

    in_code_block = False

    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code_block = not in_code_block
            current_lines.append(line)
            continue
        if not in_code_block:
            match = _HEADING_RE.match(stripped)
            if match:
                flush()
                current_level = len(match.group(1))
                heading_text = match.group(2).strip()
                current_heading = heading_text or None
                continue
        current_lines.append(line)

    flush()
    return [section for section in sections if section.heading or section.content]
