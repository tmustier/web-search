# Provider Notes

This reference describes how `wstk search` providers behave and which flags matter when choosing them.

## Provider selection

- `--provider auto` prefers `brave_api` when `BRAVE_API_KEY` is set, otherwise `ddgs`.
- `wstk providers --json` lists enabled providers, required env vars, and privacy warnings.
- `warnings` in JSON output include provider privacy notes (useful for agent logs).

## ddgs (keyless)

- Keyless, best-effort provider using public DuckDuckGo endpoints.
- Can be flaky or rate-limited; prefer `brave_api` when reliability is critical.
- Queries are sent to third-party services (see privacy warning).

## brave_api

- Requires `BRAVE_API_KEY` in the environment.
- Typically more reliable and consistent results.
- Queries are sent to the Brave Search API (see privacy warning).

## Common flags

- `--provider <ddgs|brave_api|auto>` to force or auto-select a provider.
- `--time-range <d|w|m|y>` and `--region <code>` for recency/locale filters.
- `--safe-search <on|moderate|off>` for content filtering.
- `--include-raw` to add a provider payload subset in JSON (debugging).
- `--proxy <url>` for network routing when required.
