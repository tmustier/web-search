---
name: web-search
description: Web search and content extraction toolkit. Use for searching documentation, facts, current information, or extracting readable content from URLs. Supports multiple providers (ddgs keyless, brave_api with key), caching, and safe defaults. Prefer this over browser-tools when no interaction is needed.
---

# Web Search Toolkit

Search the web and extract readable content. Stable CLI with JSON output for agents.

## Setup

```bash
cd {baseDir}
uv sync  # Install dependencies (once)
```

Optional: Set `BRAVE_API_KEY` for better search reliability (ddgs is keyless but flaky).

## Commands

### Search

```bash
{baseDir}/.venv/bin/wstk search "query"                    # Default (10 results)
{baseDir}/.venv/bin/wstk search "query" -n 5 --plain       # URLs only, one per line
{baseDir}/.venv/bin/wstk search "query" --json             # Machine-readable
{baseDir}/.venv/bin/wstk search "query" --time-range w     # Last week
{baseDir}/.venv/bin/wstk search "site:docs.python.org asyncio"  # Site-scoped
```

Key flags:
- `-n, --max-results <N>` — Number of results (default: 10)
- `--time-range <d|w|m|y>` — Filter by recency
- `--provider <ddgs|brave_api|auto>` — Search provider
- `--plain` — Output URLs only (for piping)
- `--json` — Structured output

### Extract (fetch + extract readable content)

```bash
{baseDir}/.venv/bin/wstk extract https://example.com --plain     # Markdown output
{baseDir}/.venv/bin/wstk extract https://example.com --text      # Plain text
{baseDir}/.venv/bin/wstk extract https://example.com --json      # Full metadata
{baseDir}/.venv/bin/wstk extract ./local-file.html --plain       # From file
```

Key flags:
- `--markdown` / `--text` / `--both` — Output format
- `--strategy <auto|readability|docs>` — Extraction strategy
- `--max-chars <N>` — Truncate output
- `--allow-domain <domain>` — Restrict to specific domains (safety)

### Fetch (raw HTTP, no extraction)

```bash
{baseDir}/.venv/bin/wstk fetch https://example.com --json        # Metadata + status
{baseDir}/.venv/bin/wstk fetch https://example.com --plain       # Path to cached body
```

### List providers

```bash
{baseDir}/.venv/bin/wstk providers --plain
```

## Common Patterns

**Search → extract top result:**
```bash
url=$({baseDir}/.venv/bin/wstk search "python asyncio tutorial" --plain | head -1)
{baseDir}/.venv/bin/wstk extract "$url" --plain --max-chars 8000
```

**Search with JSON for programmatic use:**
```bash
{baseDir}/.venv/bin/wstk search "openai api reference" --json | jq '.data.results[0].url'
```

**Safe extraction (restrict domains):**
```bash
{baseDir}/.venv/bin/wstk extract https://docs.python.org/3/library/asyncio.html \
  --allow-domain docs.python.org --plain
```

## Output Formats

- `--plain` — Stable text for piping (URLs for search, content for extract)
- `--json` — Structured envelope: `{ "ok": bool, "data": {...}, "error": {...} }`
- Default — Human-readable with colors

## Exit Codes

- `0` — Success
- `1` — Runtime failure (network, provider error)
- `2` — Invalid usage
- `3` — Not found / empty result
- `4` — Blocked / access denied
- `5` — Needs JS rendering (page is JS-only)

## Global Flags

- `--timeout <seconds>` — Network timeout
- `--no-cache` — Disable caching
- `--fresh` — Bypass cache reads (still writes)
- `--quiet` — Minimal output
- `--verbose` — Debug diagnostics to stderr
- `--policy <standard|strict|permissive>` — Safety defaults

## When to Use

- Searching for documentation or API references
- Looking up facts or current information
- Extracting content from known URLs
- Any task requiring web search without interactive browsing

Prefer `browser-tools` when you need: JS interaction, form filling, clicking, or visual inspection.
