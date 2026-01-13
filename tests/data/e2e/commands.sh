#!/usr/bin/env bash
set +e

# Baseline search + pipeline plan
uv run wstk search "python dataclasses docs" --json --max-results 3 \
  > tests/data/e2e/search-python-dataclasses.json
uv run wstk pipeline "python dataclasses docs" --json --top-k 3 --extract-k 1 \
  --prefer-domain docs.python.org --plan \
  > tests/data/e2e/pipeline-python-dataclasses.plan.json

# Baseline fetch/extract
uv run wstk fetch https://docs.python.org/3/library/dataclasses.html --json --max-bytes 200000 \
  > tests/data/e2e/fetch-python-dataclasses.json
uv run wstk extract https://docs.python.org/3/library/dataclasses.html --json --strategy docs \
  --markdown --max-chars 4000 \
  > tests/data/e2e/extract-python-dataclasses.docs.json
uv run wstk extract https://www.sqlite.org/whynot.html --json --strategy readability \
  --markdown --max-chars 4000 \
  > tests/data/e2e/extract-sqlite-whynot.readability.json
uv run wstk extract https://en.wikipedia.org/wiki/List_of_HTTP_status_codes --json \
  --strategy readability --markdown --max-chars 4000 \
  > tests/data/e2e/extract-wikipedia-http-status.readability.json

# Non-HTML content
uv run wstk fetch https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf \
  --json --max-bytes 200000 \
  > tests/data/e2e/fetch-w3c-dummy-pdf.json
uv run wstk fetch https://people.sc.fsu.edu/~jburkardt/data/csv/airtravel.csv --json \
  --max-bytes 200000 \
  > tests/data/e2e/fetch-airtravel-csv.json

# Tough tasks: JS-only, gated, bot-protected
uv run wstk extract https://huggingface.co/datasets/google/fleurs --json --strategy docs \
  --markdown --max-chars 2000 \
  > tests/data/e2e/extract-hf-fleurs.json
uv run wstk fetch https://huggingface.co/datasets/google/fleurs/resolve/main/README.md \
  --json --max-bytes 200000 \
  > tests/data/e2e/fetch-hf-fleurs-readme.json
uv run wstk fetch https://huggingface.co/datasets/gaia-benchmark/GAIA --json --max-bytes 200000 \
  > tests/data/e2e/fetch-hf-gaia.json
uv run wstk fetch https://huggingface.co/datasets/gaia-benchmark/GAIA/resolve/main/README.md \
  --json --max-bytes 200000 \
  > tests/data/e2e/fetch-hf-gaia-readme.json
uv run wstk fetch https://www.notion.so/ --json --max-bytes 200000 \
  > tests/data/e2e/fetch-notion.json
uv run wstk fetch https://httpbin.org/basic-auth/user/passwd --json --max-bytes 200000 \
  > tests/data/e2e/fetch-httpbin-basic-auth.json
uv run wstk extract https://www.kaggle.com/competitions/browsecomp --json --strategy docs \
  --markdown --max-chars 2000 \
  > tests/data/e2e/extract-kaggle-browsecomp.json
uv run wstk extract "https://www.kaggle.com/datasets?sort=hotness" --json --strategy docs \
  --markdown --max-chars 2000 \
  > tests/data/e2e/extract-kaggle-datasets.json
