# Web Search Toolkit

A portable “search + fetch + (render) + extract” toolkit intended for coding/research agents (Codex CLI, Claude Code, Droid/Factory, etc.).

- Spec: `docs/spec.md`
- Research notes: `docs/research.md`

## Status

`0.1.0` is a Python reference implementation with a stable-ish CLI contract:

- `wstk providers`
- `wstk search`
- `wstk fetch`
- `wstk extract`
- `wstk eval` (search-only: hit@k, MRR, overlap)

## Install (dev)

- Install deps: `uv sync`
- Run: `uv run wstk --help`

## Usage

Search:

- `uv run wstk search "openai codex cli" --plain | head -n 5`
- `uv run wstk search "openai codex cli" --json | jq '.data.results[0].url'`

Fetch + extract:

- `uv run wstk fetch https://example.com/ --json`
- `uv run wstk extract https://example.com/ --plain --text`

Eval:

- `uv run wstk eval --suite suites/search-basic.jsonl --provider ddgs --plain`
- `uv run wstk eval --suite suites/search-basic.jsonl --provider brave_api --fail-on miss --json`

## Providers

- Keyless default: `ddgs` (best-effort; can be flaky).
- Optional: `brave_api` (set `BRAVE_API_KEY`).

## Safety / privacy

- Prefer `--allow-domain` (and `--policy strict`) when fetching/extracting to reduce accidental data exfiltration.
- Remote providers (e.g. search APIs) send your query to a third-party service by design.

## License

TBD (choose a license before making the repo public).

## Contributing

See `CONTRIBUTING.md`.
