# Contributing

Thanks for contributing — this repo is early and iteration is fast.

## Development setup

- Install deps: `uv sync`
- Run the CLI: `uv run wstk --help`

## Checks

- Tests: `uv run pytest`
- Lint: `uv run ruff check .`
- Types: `uv run pyright`

## What to contribute

- New search providers (keyless or optional-key).
- `render` + `pipeline` implementations (see `docs/spec.md`).
- Extraction improvements, especially for docs-heavy pages.
- Eval suites and scoring improvements.

## Safety and secrets

- Do not add API keys, cookies, or tokens to code, tests, docs, or example outputs.
- Prefer domain allowlists (`--allow-domain`) in examples that fetch/extract content.

