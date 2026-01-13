# Claude Code Wrapper

Use `wstk` from Claude Code as a deterministic, JSON-first tool for search, fetch, and extraction.

## Default contract

- Prefer `--json` for tool calls and parse `ok`, `error.code`, and `warnings`.
- Surface concise diagnostics by relaying `error.message` and `error.details.reason` when `ok=false`.
- Use `--plain` only when piping to other commands.
- Add `--no-input` for non-interactive runs; add `--redact` when URLs/content may be sensitive.

## Setup

```bash
cd {baseDir}
uv sync
```

## Examples

Search with JSON output:

```bash
uv run wstk search "claude code tools" --json
```

Extract readable content:

```bash
uv run wstk extract https://example.com --json
```

Pipeline: search then extract top result (plain piping):

```bash
url=$(uv run wstk search "python asyncio" --plain | head -1)
uv run wstk extract "$url" --plain --max-chars 8000
```

## Handling blocked / JS-only pages

- Blocked pages return exit code `4` with `error.code=blocked`.
- JS-only pages return exit code `5` with `error.code=needs_render`.
- See `references/troubleshooting.md` for advanced flags and escalation options.

## Provider selection

- `--provider auto` prefers `brave_api` when `BRAVE_API_KEY` is set.
- `wstk providers --json` lists enabled providers and privacy warnings.
- See `references/providers.md` for provider-specific behavior.
