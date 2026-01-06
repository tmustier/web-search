# Web Search Toolkit — Detailed Spec (draft)

Goal: replace a patchwork of search/browse/scrape scripts with one portable toolkit that agents can invoke consistently across environments.

This spec is intentionally “implementation-aware” (so it can be built), but leaves some choices open (language/runtime, exact extraction stack) pending user decisions.

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

### Global flags

- `-h, --help`
- `--version`
- `--json` (machine output; stable schema; no extra logs on stdout)
- `--pretty` (pretty-print JSON)
- `--quiet` (only essential output)
- `--verbose` (debug logs to stderr)
- `--timeout <seconds>` (default per subcommand)
- `--proxy <url>` (HTTP(S) proxy for search/fetch when supported)
- `--cache-dir <path>` (default: `~/.cache/wstk`)
- `--no-cache`
- `--fresh` (bypass cache reads; still writes new artifacts unless `--no-cache`)
- `--cache-max-mb <N>` (default: 1024; LRU prune)
- `--cache-ttl <duration>` (default: unset; allow e.g. `24h`, `7d`)
- `--evidence-dir <path>` (default: `~/.cache/wstk/evidence`)
- `--redact` (redact common secrets/PII from logs + metadata; never perfect)
- `--robots <warn|respect|ignore>` (default: `warn`)
- `--allow-domain <domain>` (repeatable; restrict network operations)
- `--block-domain <domain>` (repeatable; restrict network operations)

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

### Subcommands

#### `wstk providers`

List available providers and whether they are enabled.

- Output includes:
  - provider id
  - type (`search`, `fetch`, `render`, `extract`)
  - enabled (bool) + reason if disabled
  - required env vars (if any)

#### `wstk search "<query>"`

Search the web and return ranked results.

Key flags:
- `-n, --max-results <N>` (default 10; max depends on provider)
- `--time-range <d|w|m|y|…>` (provider-mapped)
- `--region <code>` (e.g. `us-en`, `uk-en`, `wt-wt`)
- `--safe-search <on|moderate|off>`
- `--provider <id>` (default: `auto`)
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

#### `wstk fetch <url>`

Fetch raw content over HTTP (no JS). Produces a `Document` with `raw_html` and basic metadata.

Key flags:
- `--headers <json>` (advanced)
- `--user-agent <string>`
- `--accept-language <string>`
- `--max-bytes <N>` (default e.g. 5MB)
- `--follow-redirects/--no-follow-redirects`
- `--detect-blocks` (heuristics for bot walls / consent pages)
- `--accept <mime>` (default: `text/html,*/*`)
- `--include-body` (embed response body in JSON; otherwise store in evidence and return a path)

Behavior:
- If blocked (403 / known bot-wall patterns), return exit `4` (and in `--json`, include `blocked=true` and reason). Do not auto-escalate by default.

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

Key flags:
- `--strategy <auto|readability|docs>`
- `--method <http|browser|auto>` (default: `http`; `auto` may try `http` then `browser` in a future “escalate” mode)
- `--markdown/--text/--both` (default: both)
- `--max-chars <N>` (guardrails)
- `--include-html` (embed HTML in JSON; otherwise store in evidence and return a path)

Output:
- `Document` (with `extracted` filled)

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
- `--prefer-domains <domain>` (repeatable)
- `--budget <ms>` or `--budget <tokens>` (future; for limiting work)

Behavior:
- returns a structured bundle: search results + extracted documents for selected hits.

#### `wstk eval --suite <file>`

Run a benchmark suite (queries + expected URLs/answers) and output a report.

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
   - if keys available: prefer paid/official API providers
   - else: keyless providers
2. apply domain preferences (allow/block/site)
3. optionally extract top results (bounded by `--extract-k`, `--method`, and future `--escalate`)

## 8) Provider plugin model

Providers are optional and discovered at runtime.

### Search providers (initial candidates)

- `ddgs` (keyless; multi-backend where supported)
- `brave_api` (optional key; stable)
- `tavily` / `serper` / `bing` (optional keys; future)
- `searxng_local` (optional; requires local service)

### Fetch/render providers

- `httpx`/`requests`-style HTTP fetcher with good defaults
- `playwright` (or CDP) renderer

### Extract providers

- readability-style extractor (good for articles)
- docs extractor (preserve headings, code blocks, nav pruning tuned for docs)

## 9) Configuration

### Precedence

`flags > env vars > project config > user config`

### Config files

- user: `~/.config/wstk/config.toml`
- project: `.wstk.toml` (optional)

### Secrets

Never accept secrets via CLI flags. Use env vars or keychain integration (optional).

## 10) Safety + policy

### Prompt/task injection hygiene (tool-side support)

The toolkit should:

- emit structured outputs that clearly distinguish:
  - `user_query` vs `web_content`
  - `tool_diagnostics` vs `page_text`
- include `source_url` + timestamps + hashes
- allow an agent to apply “domain allowlist” defaults centrally
- support “watch mode” style affordances (surface sensitive domains and require explicit user confirmation at the agent layer)

### Content access policy

- `robots.txt`: default warn-only (`--robots=warn`), with optional strict mode (`--robots=respect`) for teams that want it.
- No CAPTCHA solving.
- If blocked, provide diagnostics and recommended alternatives (different source, cached mirror, user browser).
- Browser profile use is opt-in and clearly labeled; prefer reusing an existing user session only when (a) the user explicitly asks for gated content or (b) it’s unambiguously required and the user consents.

### Data leakage + redaction (why `--redact` exists)

Web retrieval can leak sensitive data into logs/evidence:

- URL query params may contain tokens (OAuth codes, signed URLs, session IDs).
- HTML may contain personalized or private data (“welcome, <name>”, internal docs).
- Request headers/cookies (if using a real browser profile) can grant account access.

Default stance:

- keep sensitive state (cookies, auth headers) out of stdout JSON
- store raw artifacts locally with clear retention controls (size limits, TTL, pruning)

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

## 12) Implementation choices (TBD)

Two plausible stacks:

1. **Python + uv** (pros: great CLI ergonomics, ddgs/httpx, easy packaging, Playwright python; consistent with existing keyless tooling).
2. **Node** (pros: reuse Readability/Turndown code; align with existing brave-search; but multi-provider + packaging can be heavier).

We’ll decide after clarifying requirements: distribution, runtime constraints, and desired extraction quality.

## 13) Open questions (to resolve with you)

This spec deliberately leaves some key decisions open:

- What are the default safety gates when running in an agent context?
- How aggressive should automatic extraction be (always extract top N vs only on explicit request)?
- What should be cached by default (and for how long)?
- When should we escalate to browser rendering automatically vs ask for confirmation?
- What’s the minimum acceptable “evidence” footprint (disk/storage/privacy)?

These are expanded into targeted questions in the project planning discussion.
