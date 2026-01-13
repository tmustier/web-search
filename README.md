# Web Search Toolkit

A portable “search + fetch + render + extract” toolkit intended for coding/research agents (Codex CLI, Claude Code, Droid/Factory, etc.).

- Spec: `docs/spec.md`
- Research notes: `docs/research.md`
- Agent wrapper (Codex/Cursor): `SKILL.md`
- Claude Code wrapper notes: `docs/claude-code.md`
- References: `references/providers.md`, `references/troubleshooting.md`

## Status

`0.1.0` is a Python reference implementation with a stable-ish CLI contract:

- `wstk providers`
- `wstk search`
- `wstk pipeline` (search → extract helper)
- `wstk fetch`
- `wstk render`
- `wstk extract` (HTTP or browser)
- `wstk eval` (search + fetch/extract metrics: hit@k, MRR, blocked rate, extraction heuristics)

## Install (dev)

- Install deps: `uv sync`
- Run: `uv run wstk --help`
- Render support: `uv pip install playwright` and `playwright install chromium`

## Usage

Search:

- `uv run wstk search "openai codex cli" --plain | head -n 5`
- `uv run wstk search "openai codex cli" --site openai.com --plain`
- `uv run wstk search "openai codex cli" --json | jq '.data.results[0].url'`

Pipeline:

- `uv run wstk pipeline "openai codex cli" --json`
- `uv run wstk pipeline "openai codex cli" --plan --plain`

Fetch + extract:

- `uv run wstk fetch https://example.com/ --json`
- `uv run wstk extract https://example.com/ --plain --text`

Render:

- `uv run wstk render https://example.com/ --json`
- `uv run wstk extract --method browser https://example.com/ --plain --text`

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

MIT (see `LICENSE`).

## Contributing

See `CONTRIBUTING.md`.
