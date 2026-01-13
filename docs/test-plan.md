# Test Plan (v0.1.0)

This project is meant to be used by agents, so tests focus on **contract stability** (CLI I/O, exit codes, JSON shape), **determinism** (cache semantics), and **safe failure modes** (blocked/JS-only diagnostics).

## A) Contract tests (CLI)

These should run in CI.

### A1) Help + version
- `wstk --help` includes subcommands and global flags.
- `wstk --version` prints `0.1.0`.
- `wstk <unknown>` exits `2` and prints actionable usage.

### A2) JSON envelope invariants
For each command that supports `--json`:
- stdout is valid JSON only.
- Top-level keys exist: `ok`, `command`, `version`, `data`, `warnings`, `error`, `meta`.
- On failures, `ok=false` and `error.code` is stable.

### A3) Exit code mapping
- `not_found` conditions return `3` (e.g. `search` with no results).
- `blocked` / access denied return `4`.
- `needs_render` / JS-only return `5`.
- invalid usage returns `2`.

### A4) `--plain` stability
- `providers --plain`: provider ids (including `readability` + `docs`), 1 per line.
- `search --plain`: URLs, 1 per line.
- `fetch --plain`: local body path, 1 per line.
- `extract --plain`: extracted content only (markdown by default; `--text`/`--markdown` override).

### A5) Strict policy gating
- `--policy strict` requires `--allow-domain` for URL-based `fetch`/`extract`.
- allowlist / blocklist behaviour is consistent: explicit `--block-domain` wins over allow.

## B) Unit tests

These should run in CI.

- Duration parsing (`7d`, `24h`, etc.).
- Domain matching semantics (exact + subdomain).
- URL redaction (`--redact` removes query + fragment).
- Cache semantics:
  - store/retrieve
  - TTL expiry
  - `--fresh` bypasses reads
  - `--no-cache` disables writes (or writes to temp only)

## C) Provider tests

### C1) Keyed provider (mocked)
Mock the Brave Search API and verify:
- `BRAVE_API_KEY` missing → provider disabled.
- enabled provider returns normalized results.

### C2) Keyless provider (smoke)
Keyless search is inherently flaky. Keep this out of CI by default:
- Optional “smoke” job that runs `wstk search ...` against the public web.
- If it flakes, it should not block merges; capture failures as metrics instead.

## D) Retrieval tests (mocked)

Mock HTTP fetch responses and verify:
- 404 → `not_found` / exit `3`
- 401/403/429 → `blocked` / exit `4`
- “enable javascript” page → `needs_render` / exit `5`
- robots policy: `--robots warn` emits warning; `--robots respect` blocks
- size limit enforcement (`--max-bytes`)
- `--accept` overrides default Accept header (fetch/extract)

## E) Extraction tests (local HTML fixtures)

Use fixture HTML files (no network):
- article-like HTML → markdown non-empty, title extracted
- docs-like HTML with code blocks → ensure code is preserved (future `docs` strategy)
- truncation (`--max-chars`) behaves predictably

## F) End-to-end scenarios (manual / optional automation)

These are the “agent skill” scenarios.

### F1) Basic doc lookup
- `wstk search "<product> docs" --plain | head -n 1 | xargs wstk extract --plain`

### F2) JS-only page
- ensure HTTP path returns exit `5` with a clear message and `wstk render`/`wstk extract --method browser` guidance

### F3) Blocked page
- ensure fail-fast in standard policy with exit `4` and diagnostics

## G) Quality evaluation (`eval-001`)

Define suites with:
- query
- expected domain(s)
- optional expected URL(s)
- optional “gold snippet” text

Produce a report tracking:
- hit@k
- blocked/needs_render rates
- extraction non-empty and simple boilerplate heuristics

Current coverage (v0.1.0):
- `wstk eval --suite ...` implements search + fetch/extract metrics (hit@k, MRR, overlap, blocked/needs_render rates, extraction heuristics) with a sample suite in `suites/search-basic.jsonl`.
