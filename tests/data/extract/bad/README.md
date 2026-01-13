# Bad Extraction Fixtures

This folder contains intentionally noisy HTML fixtures to expose extraction weaknesses.
These are meant for before/after comparisons when tuning extraction quality.

## Fixtures

- `bad-docs-nav.html` — nav + TOC blocks inside `<main>` so docs extraction keeps
  navigation noise.
- `bad-docs-table.html` — dense API table + inline TOC inside `<main>` to stress
  table handling and boilerplate removal.
- `bad-readability-directory.html` — large directory list competing with a short
  article body to test readability target selection.
- `bad-readability-article-nav.html` — navigation list embedded inside `<article>`
  to show readability retaining non-content lists.

## Snapshot outputs

Generated markdown/text snapshots live alongside the fixtures using these suffixes:
- `.docs.md`, `.docs.txt` for `--strategy docs`
- `.readability.md`, `.readability.txt` for `--strategy readability`

## Regenerating snapshots

Run from repo root:

```
uv run wstk extract tests/data/extract/bad/bad-docs-nav.html --strategy docs --plain --markdown > tests/data/extract/bad/bad-docs-nav.docs.md
uv run wstk extract tests/data/extract/bad/bad-docs-nav.html --strategy docs --plain --text > tests/data/extract/bad/bad-docs-nav.docs.txt
uv run wstk extract tests/data/extract/bad/bad-docs-nav.html --strategy readability --plain --markdown > tests/data/extract/bad/bad-docs-nav.readability.md
uv run wstk extract tests/data/extract/bad/bad-docs-nav.html --strategy readability --plain --text > tests/data/extract/bad/bad-docs-nav.readability.txt

uv run wstk extract tests/data/extract/bad/bad-docs-table.html --strategy docs --plain --markdown > tests/data/extract/bad/bad-docs-table.docs.md
uv run wstk extract tests/data/extract/bad/bad-docs-table.html --strategy docs --plain --text > tests/data/extract/bad/bad-docs-table.docs.txt
uv run wstk extract tests/data/extract/bad/bad-docs-table.html --strategy readability --plain --markdown > tests/data/extract/bad/bad-docs-table.readability.md
uv run wstk extract tests/data/extract/bad/bad-docs-table.html --strategy readability --plain --text > tests/data/extract/bad/bad-docs-table.readability.txt

uv run wstk extract tests/data/extract/bad/bad-readability-directory.html --strategy docs --plain --markdown > tests/data/extract/bad/bad-readability-directory.docs.md
uv run wstk extract tests/data/extract/bad/bad-readability-directory.html --strategy docs --plain --text > tests/data/extract/bad/bad-readability-directory.docs.txt
uv run wstk extract tests/data/extract/bad/bad-readability-directory.html --strategy readability --plain --markdown > tests/data/extract/bad/bad-readability-directory.readability.md
uv run wstk extract tests/data/extract/bad/bad-readability-directory.html --strategy readability --plain --text > tests/data/extract/bad/bad-readability-directory.readability.txt

uv run wstk extract tests/data/extract/bad/bad-readability-article-nav.html --strategy docs --plain --markdown > tests/data/extract/bad/bad-readability-article-nav.docs.md
uv run wstk extract tests/data/extract/bad/bad-readability-article-nav.html --strategy docs --plain --text > tests/data/extract/bad/bad-readability-article-nav.docs.txt
uv run wstk extract tests/data/extract/bad/bad-readability-article-nav.html --strategy readability --plain --markdown > tests/data/extract/bad/bad-readability-article-nav.readability.md
uv run wstk extract tests/data/extract/bad/bad-readability-article-nav.html --strategy readability --plain --text > tests/data/extract/bad/bad-readability-article-nav.readability.txt
```
