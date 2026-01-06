# Web Search Toolkit (spec + reference implementation)

This repo is a spec and reference implementation plan for a portable “search + fetch + render + extract” toolkit intended for coding/research agents (Codex CLI, Claude Code, Droid/Factory, etc.).

- Spec: `docs/spec.md`
- Research notes: `docs/research.md`

## Status

`0.1.0` implements a baseline CLI: `providers`, `search`, `fetch`, `extract`, and `eval` (search-only metrics).

## Quickstart (dev)

- Install deps: `uv sync`
- Run: `uv run wstk --help`
- Run eval: `uv run wstk eval --suite suites/search-basic.jsonl --provider ddgs`
