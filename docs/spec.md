# Web Search Toolkit — Detailed Spec (draft)

Goal: replace a patchwork of search/browse/scrape scripts with one portable toolkit that agents can invoke consistently across environments.

This spec is intentionally “implementation-aware” (so it can be built), but leaves some choices open (language/runtime, exact extraction stack) pending user decisions.

## Implementation status (v0.1.0, Python)

Reference implementation lives in this repo:

- Implemented: `wstk providers`, `wstk search`, `wstk pipeline`, `wstk fetch`, `wstk render`, `wstk extract` (HTTP + browser, readability/docs), `wstk eval` (search + fetch/extract metrics)
- Search providers: `ddgs` (keyless), `brave_api` (optional `BRAVE_API_KEY`)
- Fetch: `httpx` + local cache (TTL + size budget)

## 1) Problem statement

Today’s agent workflows are fragmented:

- One-off scripts per provider (Brave API, DDG wrappers, bespoke scrapers).
- Inconsistent output formats (hard to chain).
- Unclear fallback behavior (when search fails, when fetch 403s, when pages are JS-only).
- Hard to evaluate quality systematically.
- Safety posture varies (prompt/task injection risk, accidental exfiltration).

We want a single toolkit with:

- stable CLI + JSON output schema
- provider plugins (optional keys, keyless defaults)
- layered fallback (search → fetch → render → extract)
- explicit provenance (evidence artifacts, timestamps, methods)
- agent-friendly safety defaults

## 2) Scope

### In scope

- Web search across multiple providers (keyless default + optional API keys).
- Fetching page content with good “polite” defaults, proxy support, and diagnostics.
- Rendering JS pages locally (browser automation) when HTTP fetch is insufficient.
- Extracting readable content (Markdown + plain text) with provider/strategy metadata.
- Caching and evidence capture to make runs reproducible and debuggable.
- A small evaluation harness to compare search and extraction quality over time.
- “Skill wrappers” for common agent runtimes (Codex/Claude/Droid) that progressively disclose complexity.

### Out of scope (explicit non-goals)

- CAPTCHA solving.
- “Stealth/anti-bot bypass” is not part of the default core path; if ever included, it must be explicit opt-in, tightly budgeted, and designed to avoid large-scale scraping.
- Automated login to third-party sites without the user’s explicit session/profile.
- A full autonomous browser agent (planning/execution loop). This is a *toolkit* used by agents.
- Large-scale crawling.

## 3) Design principles (derived from research)

1. **Layered fallbacks**: prefer cheap/fast deterministic steps first; escalate only when needed.
2. **Make uncertainty visible**: include “why we think this result is relevant”, failure reasons, and extraction confidence.
3. **Evidence-first**: store artifacts (raw HTML, final extracted markdown, optional screenshot) so answers can be audited.
4. **Safety by default**: treat web content as untrusted; add guardrails like domain allow/block and explicit “interactive” mode.
5. **Composable interfaces**: stable JSON for machine use; readable text for humans; predictable exit codes.
6. **Fail fast, escalate explicitly**: default to “diagnose and stop” on blocks/JS-only pages; make escalation a deliberate choice (`--method auto`, `--render`, or future `--try-hard`).

## 4) User stories

- As an agent, I can search for documentation and get stable JSON results, optionally scoped to domains and time windows.
- As an agent, I can fetch and extract readable content from a URL, with an explicit escalation path from HTTP → rendered browsing when needed.
- As a user, I can run the same query later and see what changed (cache/evidence).
- As a user, I can configure preferred providers and keys once; the toolkit uses them automatically.
- As an agent author, I can add a new search provider without changing downstream code.

## 5) High-level architecture

### Components

1. **CLI frontend** (`wstk` placeholder name)
2. **Core orchestration** (fallback logic + retries + caching + evidence)
3. **Search providers** (plugins)
4. **Fetchers**:
   - `http` fetcher (fast, no JS)
   - `browser` fetcher (JS rendering, local)
5. **Extractors**:
   - `readability`-style for articles
   - `docs`-oriented extractor (preserve headings/code blocks/TOC)
6. **Store**:
   - cache (inputs → outputs)
   - evidence artifacts (snapshots, metadata)
7. **Eval harness**:
   - query sets
   - scoring + report generation

### Data model: “Document”

All downstream components operate on a common `Document` structure:

- `url` (canonical)
- `fetched_at` (RFC3339)
- `fetch_method` (`http` | `browser` | `provided`)
- `http` metadata (status, headers subset, final_url, redirects)
- `raw_html` (optional, may be stored in evidence store)
- `render` metadata (optional: screenshot path, DOM snapshot id)
- `extracted`:
  - `markdown` (optional)
  - `text` (optional)
  - `doc` (optional; structured sections + links for docs mode)
  - `title`
  - `language`
  - `content_hash`
  - `extraction_method` + version

## 6) CLI specification (portable contract)

### Command name

Working name: `wstk` (“web search toolkit”). Bikeshed later.

### Output contract

- Primary data goes to **stdout**.
- Diagnostics go to **stderr**.
- In `--json` mode:
  - stdout must be **valid JSON only** (no banners, no progress spinners).
  - stderr may include logs (unless `--quiet`).
- In `--plain` mode:
  - stdout is stable, line-oriented text intended for piping (no color, no extra decorations).
  - stderr may include logs/warnings (unless `--quiet`).

### Global flags

- `-h, --help`
- `--version`
- `--json` (machine output; stable schema; no extra logs on stdout)
- `--pretty` (pretty-print JSON)
- `--plain` (stable, line-oriented text for piping)
- `--quiet` (only essential output)
- `--verbose` (debug logs to stderr)
- `--no-color` (disable ANSI color output)
- `--no-input` (never prompt / never open interactive flows; fail with actionable diagnostics)
- `--timeout <seconds>` (default per subcommand)
- `--proxy <url>` (HTTP(S) proxy for search/fetch when supported)
- `--cache-dir <path>` (default: `~/.cache/wstk`)
- `--no-cache`
- `--fresh` (bypass cache reads; still writes new artifacts unless `--no-cache`)
- `--cache-max-mb <N>` (default: 1024; LRU prune)
- `--cache-ttl <duration>` (default: `7d`; allow e.g. `24h`, `7d`)
- `--evidence-dir <path>` (default: `~/.cache/wstk/evidence`)
- `--redact` (redact common secrets/PII from logs + metadata; never perfect)
- `--robots <warn|respect|ignore>` (default: `warn`)
- `--allow-domain <domain>` (repeatable; restrict network operations)
- `--block-domain <domain>` (repeatable; restrict network operations)
- `--policy <standard|strict|permissive>` (default: `standard`; sets safety + caching defaults, explicit flags override)

Notes:
- `--pretty` implies `--json` (or errors if `--json` is not supported by the command).
- Respect `NO_COLOR` and `TERM=dumb` unless overridden.

### JSON envelope (baseline)

In `--json` mode, commands return a consistent top-level envelope:

```json
{
  "ok": true,
  "command": "search",
  "version": "0.1.0",
  "data": {},
  "warnings": [],
  "error": null,
  "meta": {
    "duration_ms": 1234,
    "cache": { "hit": false },
    "providers": ["ddgs"]
  }
}
```

On failure (`ok=false`), `error` is populated with:

- `code` (stable string, e.g. `blocked`, `timeout`, `provider_error`)
- `message` (human readable)
- `details` (optional structured context)

### Exit codes (baseline)

- `0` success
- `1` runtime failure (network, provider error, unexpected exception)
- `2` invalid usage (CLI parsing/validation)
- `3` not found / empty result (only for commands where “no results” is distinct)
- `4` blocked / access denied (403, bot wall, paywall detected, etc.)
- `5` needs render / JS-only (the next step is typically `wstk render ...` or `wstk extract --method browser ...`)

### Subcommands

#### `wstk providers`

List available providers and whether they are enabled.

- In `--plain` mode, output provider ids one per line.
- Output includes:
  - provider id
  - type (`search`, `fetch`, `render`, `extract`)
  - enabled (bool) + reason if disabled
  - required env vars (if any)
  - optional `privacy_warning` when provider sends data to third parties
- Extract providers include `readability` and `docs`.

#### `wstk search "<query>"`

Search the web and return ranked results.

Key flags:
- `-n, --max-results <N>` (default 10; max depends on provider)
- `--time-range <d|w|m|y|…>` (provider-mapped)
- `--region <code>` (e.g. `us-en`, `uk-en`, `wt-wt`)
- `--safe-search <on|moderate|off>`
- `--provider <id>` (default: `auto`)
- `--include-raw` (include a provider-specific raw payload subset in JSON)
- `--allow-domain <domain>` (repeatable)
- `--block-domain <domain>` (repeatable)
- `--site <domain>` (syntactic sugar: allow-domain + query augmentation)

Result item schema (minimum):
- `title`
- `url`
- `snippet`
- `published_at` (optional)
- `source_provider`
- `score` (optional, normalized 0–1 if available)

Optional additions (strongly preferred for debugging/eval):
- `result_id` (stable per run; can be a hash of url+title)
- `matched_rules` (e.g. `["site:docs", "preferred_domain"]`)
- `raw` (provider-specific raw payload subset, gated behind `--verbose` or `--include-raw`)

`--plain` behavior:
- output the result URLs, one per line (best for `... | head -n 1 | xargs wstk extract`).

#### `wstk fetch <url>`

Fetch raw content over HTTP (no JS). Produces a `Document` with `raw_html` and basic metadata.

Key flags:
- `--header <key:value>` (repeatable; rejects `authorization`/`cookie`/`set-cookie`)
- `--headers-file <path|->` (advanced; JSON object; use `-` to read from stdin if it contains sensitive values)
- `--user-agent <string>`
- `--accept-language <string>`
- `--max-bytes <N>` (default e.g. 5MB)
- `--follow-redirects/--no-follow-redirects`
- `--detect-blocks` (heuristics for bot walls / consent pages)
- `--accept <mime>` (default: `text/html,*/*`)
- `--include-body` (embed response body in JSON; otherwise store in evidence and return a path)

Behavior:
- If blocked (403 / known bot-wall patterns), return exit `4` (and in `--json`, include `blocked=true` and reason). Do not auto-escalate by default.
- For blocked/JS-only responses, include `next_steps` suggestions (render/extract with browser, use a profile, or alternate sources).

`--plain` behavior:
- output a local path to the stored response body (useful for piping into `wstk extract <path>`)

Block/consent heuristics (non-exhaustive):
- status codes: 401/403/429
- “enable javascript” / “verify you are human” / “checking your browser”
- consent interstitials that replace content (cookie banners that require interaction)

#### `wstk render <url>`

Render a page in a real browser engine locally and output a `Document` with final DOM snapshot + optional screenshot.

Key flags:
- `--profile <path>` or `--use-system-profile` (explicitly opt-in; for logged-in browsing)
- `--wait <ms>` / `--wait-for <selector|network-idle>`
- `--screenshot` (store to evidence dir; return path in JSON)
- `--headful/--headless` (default: headless; allow “assist” mode)

Notes:
- Rendering is an explicit escalation path. It should be clearly labeled “interactive/privileged” when using a real profile.

#### `wstk extract <url|path>`

Extract readable content.

Inputs:
- URL (will fetch/render as needed), or
- path to previously saved HTML/Document.
- `-` (read HTML/Document JSON from stdin)

Key flags:
- `--strategy <auto|readability|docs>`
- `--method <http|browser|auto>` (default: `http`; `auto` may try `http` then `browser` in a future “escalate” mode)
- `--accept <mime>` (default: `text/html,*/*`; applies to HTTP fetch)
- `--markdown/--text/--both` (default: both)
- `--max-chars <N>` (guardrails)
- `--max-tokens <N>` (approx token cap)
- `--include-html` (embed HTML in JSON; otherwise store in evidence and return a path)

Output:
- `Document` (with `extracted` filled)
- `extracted.doc` includes headings/sections/links for `--strategy docs`

`--plain` behavior:
- output extracted content (markdown by default; `--text`/`--markdown` override)

Content-type handling:
- HTML: use extractor strategies.
- PDF: store the PDF to evidence, extract text via a local tool (e.g. `pdftotext`) when available; otherwise return “unsupported” with guidance.
- Plain text / JSON: treat as already-extracted (with size guards).

#### `wstk pipeline "<query>"`

One-shot “search → pick → extract” helper intended for agents.

Key flags:
- `--top-k <N>` (search results to consider)
- `--extract-k <N>` (how many results to extract; default: 1)
- `--method <http|browser|auto>` (default: `http`)
- `--escalate <none|render>` (default: `none`; future)
- `--plan` (no fetch/extract; return candidate URLs + rationale only)
- `--prefer-domains <domain>` (repeatable)
- `--budget <ms>` or `--budget <tokens>` (future; for limiting work)

Behavior:
- returns a structured bundle: search results + extracted documents for selected hits.

#### `wstk eval --suite <file>`

Run a benchmark suite (queries + expected URLs/answers) and output a report.

Implementation status (v0.1.0):
- Implemented: search eval (`hit@k`, MRR, URL overlap), with cache-backed determinism controls.
- Implemented: fetch/extract metrics (blocked/needs_render rates, extraction heuristics).

Suite format:
- `.jsonl` (recommended): one JSON object per line (blank lines + `#` comments allowed).
- `.json`: either a JSON array of cases or `{ "cases": [...] }`.

Case schema (v0.1.0):
- `id` (string, optional; defaults to `case-<n>`)
- `query` (string, required)
- `expected_domains` (list of strings, optional)
- `expected_urls` (list of strings, optional)
- `k` (int, optional; overrides global `--k` for this case)

Evaluation criterion (v0.1.0):
- If `expected_urls` is set: case passes when any expected URL appears in top-`k` (normalized, query/fragment stripped).
- Else if `expected_domains` is set: case passes when any expected domain appears in top-`k` (subdomains allowed).
- Else: case is unscored.

Fetch/extract target selection (v0.1.0):
- If `expected_urls` is provided, use the first URL.
- Else, use the first top-`k` result that matches `expected_domains`.
- Else, use the top result.

Key flags (v0.1.0):
- `--suite <path>`
- `--provider <id>` (repeatable; default: `auto`)
- `-k, --k <N>` (default: 10)
- `--fail-on <none|error|miss|miss_or_error>` (default: `error`)
- `--include-results` (include result items in JSON output)

Metrics (v0):
- search: hit@k, URL overlap, “expected domain present”
- fetch: success rate, blocked rate, median latency
- extract: non-empty, word count, boilerplate ratio proxy, code-block preservation (heuristic)

## 7) Fallback policy (core orchestration)

Default resolution for `extract <url>`:

1. `fetch` via HTTP
2. if blocked/empty/JS shell → return a typed failure (`blocked` / `needs_render`) with diagnostics and suggested next command(s)
3. on success: `extract` with `strategy=auto` (choose readability vs docs heuristic)

Default resolution for `pipeline "<query>"`:

1. `search` with provider `auto`:
   - prefer the most reliable configured provider(s) (API keys / local services / endpoints the user explicitly set up)
   - fall back to best-effort keyless providers if nothing is configured
2. apply domain preferences (allow/block/site)
3. optionally extract top results (bounded by `--extract-k`, `--method`, and future `--escalate`)

## 8) Provider plugin model

Providers are optional and discovered at runtime.

### Search providers (initial candidates)

- `ddgs` (keyless; multi-backend where supported)
- `brave_api` (optional key; stable)
- `firecrawl_endpoint` (optional endpoint + key; can provide search and/or extraction depending on server capabilities)
- `tavily` / `serper` / `bing` (optional keys; future)
- `searxng_local` (optional; requires local service)

### Provider `auto` default ordering (search)

When multiple search providers are enabled and `--provider auto` is used, the built-in default order should prefer reliability *when configured*:

1. `brave_api` (if `BRAVE_API_KEY` configured)
2. `searxng_local` (if base URL configured and reachable)
3. `firecrawl_endpoint` (if base URL is **local/self-hosted**; otherwise requires explicit opt-in)
4. `ddgs` (best-effort keyless fallback)

Users must be able to override this order in config.

### `firecrawl_endpoint` provider (optional)

This is an optional integration with a **Firecrawl-compatible HTTP endpoint** (cloud or self-hosted) to improve success rates on difficult sites (dynamic content, blocks, etc.) without embedding Firecrawl code in this repo.

Configuration (suggested):

- `FIRECRAWL_BASE_URL` (required): e.g. `https://api.firecrawl.dev` or a self-hosted URL
- `FIRECRAWL_API_KEY` (optional): if required by the endpoint; never passed via CLI flags
- `FIRECRAWL_ALLOW_AUTO` (optional, default false): allow use under `--provider auto` even when the base URL is remote/cloud

Behavior expectations:

- Treated as a remote provider: it may send URLs (and possibly retrieved page content) to a third-party service depending on deployment; emit clear metadata about when it was used.
- In `standard` policy, it is only eligible for `--provider auto` when the base URL is local/self-hosted (e.g. `localhost`, loopback). For remote/cloud endpoints, require explicit opt-in (config) or explicit `--provider firecrawl_endpoint`.

License note:

- Firecrawl’s OSS backend is AGPL-3.0; do not vendor/embed it here. An endpoint integration keeps this project’s licensing independent.

### Fetch/render providers

- `httpx`/`requests`-style HTTP fetcher with good defaults
- `playwright` (or CDP) renderer

### Extract providers

- readability-style extractor (good for articles)
- docs extractor (preserve headings, code blocks, nav pruning tuned for docs)
- optional “remote extractor” providers (e.g. Firecrawl endpoint) as explicit opt-ins

## 9) Configuration

### Precedence

`flags > env vars > project config > user config`

### Config files

- user: `~/.config/wstk/config.toml`
- project: `.wstk.toml` (optional)

### Secrets

Never accept secrets via CLI flags. Use env vars or keychain integration (optional).

### Provider selection and precedence

Each subcommand that supports `--provider auto` should use a deterministic priority order:

1. provider explicitly set by CLI flag
2. provider explicitly set in project config (`.wstk.toml`)
3. provider explicitly set in user config (`~/.config/wstk/config.toml`)
4. built-in defaults:
   - prefer configured “reliability” providers (API keys / local services / endpoints)
   - fall back to keyless providers

Users should be able to reorder provider preference (globally or per command) via config.

## 10) Safety + policy

### Prompt/task injection hygiene (tool-side support)

The toolkit should:

- emit structured outputs that clearly distinguish:
  - `user_query` vs `web_content`
  - `tool_diagnostics` vs `page_text`
- include `source_url` + timestamps + hashes
- allow an agent to apply “domain allowlist” defaults centrally
- warn when extracted content matches common prompt-injection phrases (surfaced via `warnings`)
- support “watch mode” style affordances (surface sensitive domains and require explicit user confirmation at the agent layer)

### Policy modes (pragmatic defaults, easy overrides)

This project’s safety stance is “useful by default, with explicit escalations”. The CLI should support `--policy` to bundle sensible defaults, while keeping the agent in control via explicit flags.

Policy modes must:

- change defaults, not capabilities (explicit flags always win)
- emit **warnings + diagnostics**, not imperative “do X” instructions (agents decide what to do next)
- be designed around *outcomes* (predictability vs success rate vs compliance posture)

#### `standard` (default)

Goal: work well for day-to-day agent research without surprising behavior.

- Blocks: fail fast with diagnostics; no automatic escalation to browser rendering.
- `robots.txt`: warn-only (`--robots=warn`).
- Caching: on by default; raw artifacts stored locally, bounded by `--cache-ttl` (default `7d`) and `--cache-max-mb` (default `1024`).
- Redaction: off by default (favor debuggability/repro), but:
  - never include cookies/auth headers in stdout JSON
  - emit a warning when URLs look secret-bearing (e.g., OAuth code / signed URL patterns)
- Privileged browsing (session reuse): supported but opt-in (`render --profile/--use-system-profile`).
  - When a real profile/session is used, default to **no cache writes** unless explicitly overridden (to reduce accidental retention of private/authenticated content).
- Remote extraction providers (e.g. Firecrawl endpoint): available, but not automatically used (agents must opt in via `--provider` or permissive escalation).

#### `strict` (compliance-focused)

Goal: minimize policy risk and accidental data retention, even at the cost of lower success rates.

- Require an explicit allowlist (`--allow-domain`) for page retrieval operations (`fetch`, `render`, `extract` when input is a URL).
- `robots.txt`: respect (`--robots=respect`).
- Rendering: disabled unless explicitly requested (and never with a real user profile/session).
- Caching: metadata-only by default; require explicit opt-in to store raw artifacts.
- Redaction: on by default (sanitize logs/metadata; still not a guarantee).

#### `permissive` (try-hard, higher variance)

Goal: maximize one-shot success when the user accepts higher unpredictability and policy surface area.

- Allows opt-in “auto escalation” flows (e.g. `--method auto` or future `--escalate=render`).
- May allow additional compatibility tactics (retries/backoff; alternate representations like `?output=1`, print views) while staying bounded by budgets.
- May optionally use configured remote extraction providers as an explicit escalation path (still bounded by budgets and never the default path).
- Any “stealth/bypass” tactics must be explicit, isolated, and budgeted (see below).

### Content access policy

- `robots.txt`: default warn-only (`--robots=warn`), with optional strict mode (`--robots=respect`) for teams that want it.
- No CAPTCHA solving.
- If blocked, provide diagnostics and recommended alternatives (different source, cached mirror, user browser).
- Browser profile use is opt-in and clearly labeled; prefer reusing an existing user session only when (a) the user explicitly asks for gated content or (b) it’s unambiguously required and the user consents.

### Anti-bot scope (compatibility vs bypass)

There’s a pragmatic distinction between:

- **Compatibility** (generally acceptable): realistic headers/UA, cookie jar, conservative retries/backoff, JS rendering, user-provided proxies, and opt-in reuse of the user’s existing authenticated session.
- **Bypass/stealth** (reputationally sensitive): tactics whose primary purpose is to defeat bot detection.

Project posture:

- “Compatibility” is in scope (often necessary for docs).
- “Bypass/stealth” should never be the default path. If supported, it must be explicit opt-in, with strict budgets, and designed to avoid turning this into a bulk scraping toolkit.

### Data leakage + redaction (why `--redact` exists)

Web retrieval can leak sensitive data into logs/evidence:

- URL query params may contain tokens (OAuth codes, signed URLs, session IDs).
- HTML may contain personalized or private data (“welcome, <name>”, internal docs).
- Request headers/cookies (if using a real browser profile) can grant account access.

Default stance:

- keep sensitive state (cookies, auth headers) out of stdout JSON
- store raw artifacts locally with clear retention controls (size limits, TTL, pruning)
- `--redact` scrubs common secrets/PII from outputs (URLs, text, metadata)

## 11) Packaging for agent ecosystems (progressive disclosure)

We want “one core toolkit” + thin wrappers:

- **Core**: a CLI installed locally (`wstk`) with stable JSON schemas.
- **Codex skill**: minimal `SKILL.md` that teaches the agent the pipeline and how to call the CLI, with references for advanced flags.
- **Claude Code skill**: same concept (one skill; scripts in `scripts/`).
- **Droid/Factory skill**: same concept (or MCP server wrapper later).

Progressive disclosure approach:

- SKILL.md: “how to choose search vs fetch vs render vs extract”; default flows; safety rules.
- `references/`: provider-specific behavior, troubleshooting 403/JS, evaluation playbook.
- `scripts/`: small deterministic helpers (e.g., normalize URL, detect JS shell, boilerplate scoring).

## 12) Implementation choices

### Reference implementation language (proposed)

**Python** as the reference implementation, with a stable CLI+JSON contract so additional implementations can exist later.

Rationale (outcome-focused):

- Fastest path to a “works everywhere” local tool with minimal integration friction for agents (good CLI ergonomics, strong HTTP ecosystem, easy plugin boundaries).
- Easiest to keep the core lightweight while making heavy features (JS rendering, browser automation) optional.
- Keeps future options open: once the interface is proven, a Go/Rust single-binary rewrite is straightforward because the contract is already defined and testable.

Alternatives we may want later:

- **TypeScript/Node**: strong for reusing existing Readability/Turndown patterns and Playwright, but tends to pull a heavier dependency graph by default and can be harder to keep “optional”.
- **Go/Rust**: great for distribution (single binary) and performance, but you still need an external browser engine for JS rendering and a solid extraction stack; better as a follow-on once behavior is validated.

### Tooling (proposed)

- Dependency management / runner: `uv` (fast, reproducible, simple)
- Type checking: `pyright` (fast, good editor support; treat type errors as CI failures)
- Lint/format: `ruff` (format + lint; keep rules minimal at first)
- Tests: `pytest` (focus on CLI contract + provider selection + caching behaviors)
- Pre-commit: `pre-commit` hooks for `ruff` + `pyright` (keep local + CI aligned)
- CI: GitHub Actions running `ruff`, `pyright`, `pytest` on PRs
- Coverage (optional): `pytest-cov` with a soft floor initially (avoid blocking early refactors)

## 13) Open questions (to resolve with you)

This spec deliberately leaves some key decisions open:

- What are the default safety gates when running in an agent context?
- How aggressive should automatic extraction be (always extract top N vs only on explicit request)?
- What should be cached by default (and for how long)?
- When should we escalate to browser rendering automatically vs ask for confirmation?
- What’s the minimum acceptable “evidence” footprint (disk/storage/privacy)?

These are expanded into targeted questions in the project planning discussion.
