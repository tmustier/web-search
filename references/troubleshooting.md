# Troubleshooting: blocked or JS-only pages

Use this guide when `wstk fetch` or `wstk extract` returns exit code `4` (blocked) or `5` (needs render).

## Blocked / access denied (exit code 4)

Signals:
- JSON: `ok=false`, `error.code=blocked`, and `error.details.reason` plus `next_steps`.
- Plain output: exit code `4` with diagnostics on stderr.

What to try:
- Confirm domain policy: strict mode requires `--allow-domain` for network access.
- Review `error.details.pattern` for bot-wall matches; disable heuristics with `--no-detect-blocks` if it is a false positive.
- Adjust request headers: `--user-agent`, `--accept-language`, or `--header "key:value"`.
- Route through a proxy if your network requires it: `--proxy <url>`.
- Escalate to a real browser session when needed (see JS-only notes below).

## JS-only / needs render (exit code 5)

Signals:
- JSON: `ok=false`, `error.code=needs_render`, and `error.details.reason`.
- HTML contains JS-shell patterns like `enable javascript` or `<noscript>`.

What to try:
- Run `wstk render <url>` to capture a DOM snapshot (add `--screenshot` if helpful).
- Or use `wstk extract --method browser <url>` for one-step extraction.
- If you need interaction, use `browser-tools` to capture HTML, then run `wstk extract ./saved.html`.
- If you only want raw HTML despite the warning, disable detection with `--no-detect-blocks`.

## Useful debug flags

- `--include-body` (fetch only) to embed the body in JSON for inspection.
- `--max-bytes` to cap downloads.
- `--timeout` to tune slow sites.
- `--no-cache` or `--fresh` to avoid stale results.
