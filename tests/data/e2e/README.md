# E2E Snapshot Dataset

Real-world CLI outputs captured for extraction quality comparisons and regression checks.

## Notes

- Outputs are JSON envelopes from `wstk` commands.
- Some snapshots intentionally capture failures (`blocked`, `needs_render`, `401`).
- Outputs are size-bounded with `--max-results`, `--max-bytes`, and `--max-chars`.
- Regeneration commands are in `tests/data/e2e/commands.sh` (some exit non-zero by design).
- Treat the raw JSON snapshots as canonical ground truth; do not edit them for comparisons.

## Comparison guidance

Use derived summaries for comparisons without mutating snapshots.

**Stable summary fields (semantic):**
- `ok`, `command`, `error.code`, `error.details.reason`
- `data.document.fetch_method`, `data.document.http.status`, `data.document.http.final_url`
- `data.document.artifact.content_type`, `data.document.artifact.bytes`
- Extracted content length (markdown/text) and optional content hash for drift checks

**Informational diffs (volatile, non-gating):**
- `data.document.fetched_at` (age delta)
- `meta.duration_ms` (latency delta)
- `meta.cache.hit` (cache behavior)
- `data.document.artifact.body_path` (local path changes)

## Coverage

| ID | Category | Command | Output | Expected outcome |
| --- | --- | --- | --- | --- |
| search-python-dataclasses | baseline search | `wstk search "python dataclasses docs" --json --max-results 3` | `tests/data/e2e/search-python-dataclasses.json` | ok |
| pipeline-python-dataclasses-plan | baseline pipeline (plan) | `wstk pipeline "python dataclasses docs" --json --top-k 3 --extract-k 1 --prefer-domain docs.python.org --plan` | `tests/data/e2e/pipeline-python-dataclasses.plan.json` | ok |
| fetch-python-dataclasses | baseline fetch (docs) | `wstk fetch https://docs.python.org/3/library/dataclasses.html --json --max-bytes 200000` | `tests/data/e2e/fetch-python-dataclasses.json` | ok |
| extract-python-dataclasses-docs | docs extraction | `wstk extract https://docs.python.org/3/library/dataclasses.html --json --strategy docs --markdown --max-chars 4000` | `tests/data/e2e/extract-python-dataclasses.docs.json` | ok |
| extract-sqlite-whynot | article extraction | `wstk extract https://www.sqlite.org/whynot.html --json --strategy readability --markdown --max-chars 4000` | `tests/data/e2e/extract-sqlite-whynot.readability.json` | ok |
| extract-wikipedia-http-status | table-heavy page | `wstk extract https://en.wikipedia.org/wiki/List_of_HTTP_status_codes --json --strategy readability --markdown --max-chars 4000` | `tests/data/e2e/extract-wikipedia-http-status.readability.json` | ok |
| fetch-w3c-dummy-pdf | non-HTML (PDF) | `wstk fetch https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf --json --max-bytes 200000` | `tests/data/e2e/fetch-w3c-dummy-pdf.json` | ok |
| fetch-airtravel-csv | non-HTML (CSV) | `wstk fetch https://people.sc.fsu.edu/~jburkardt/data/csv/airtravel.csv --json --max-bytes 200000` | `tests/data/e2e/fetch-airtravel-csv.json` | ok |
| extract-hf-fleurs | JS-only dataset viewer | `wstk extract https://huggingface.co/datasets/google/fleurs --json --strategy docs --markdown --max-chars 2000` | `tests/data/e2e/extract-hf-fleurs.json` | needs_render |
| fetch-hf-fleurs-readme | dataset README fallback | `wstk fetch https://huggingface.co/datasets/google/fleurs/resolve/main/README.md --json --max-bytes 200000` | `tests/data/e2e/fetch-hf-fleurs-readme.json` | ok |
| fetch-hf-gaia | gated dataset page | `wstk fetch https://huggingface.co/datasets/gaia-benchmark/GAIA --json --max-bytes 200000` | `tests/data/e2e/fetch-hf-gaia.json` | needs_render |
| fetch-hf-gaia-readme | gated dataset README | `wstk fetch https://huggingface.co/datasets/gaia-benchmark/GAIA/resolve/main/README.md --json --max-bytes 200000` | `tests/data/e2e/fetch-hf-gaia-readme.json` | ok |
| fetch-notion | login-gated landing | `wstk fetch https://www.notion.so/ --json --max-bytes 200000` | `tests/data/e2e/fetch-notion.json` | needs_render |
| fetch-httpbin-basic-auth | explicit 401 auth gate | `wstk fetch https://httpbin.org/basic-auth/user/passwd --json --max-bytes 200000` | `tests/data/e2e/fetch-httpbin-basic-auth.json` | blocked (401) |
| extract-kaggle-browsecomp | bot-protected (Kaggle) | `wstk extract https://www.kaggle.com/competitions/browsecomp --json --strategy docs --markdown --max-chars 2000` | `tests/data/e2e/extract-kaggle-browsecomp.json` | blocked (bot wall) |
| extract-kaggle-datasets | interactive filters (Kaggle) | `wstk extract "https://www.kaggle.com/datasets?sort=hotness" --json --strategy docs --markdown --max-chars 2000` | `tests/data/e2e/extract-kaggle-datasets.json` | blocked (bot wall) |
