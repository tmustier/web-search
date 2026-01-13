# Extraction Baselines

This folder holds deterministic extraction snapshots for manual comparison when tuning extractors.

## Contents

- `docs-sample.html` — synthetic docs-like fixture (nav/toc/sidebar + main content).
- `docs-sample.docs.md` — `--strategy docs --markdown` output.
- `docs-sample.docs.txt` — `--strategy docs --text` output.
- `docs-sample.readability.md` — `--strategy readability --markdown` output.
- `docs-sample.readability.txt` — `--strategy readability --text` output.
- `bad/` — intentionally noisy fixtures + snapshots for before/after comparisons.

## Regenerating snapshots

Run from repo root:

```
uv run wstk extract tests/data/extract/docs-sample.html --strategy docs --plain --markdown > tests/data/extract/docs-sample.docs.md
uv run wstk extract tests/data/extract/docs-sample.html --strategy docs --plain --text > tests/data/extract/docs-sample.docs.txt
uv run wstk extract tests/data/extract/docs-sample.html --strategy readability --plain --markdown > tests/data/extract/docs-sample.readability.md
uv run wstk extract tests/data/extract/docs-sample.html --strategy readability --plain --text > tests/data/extract/docs-sample.readability.txt
```

Keep the fixture small and fully local so snapshots stay stable.
