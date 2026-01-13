# web-search - Progress Log

## Project Overview

**Started**: 2026-01-06
**Status**: v0.1.0 implementation in progress
**Repository**: https://github.com/tmustier/web-search

### Project Goals

- Portable “search + fetch + render + extract” toolkit for coding/research agents.
- Keyless-by-default (public web) with optional API keys/endpoints for reliability.
- Opinionated defaults that are easy for agents: fail fast by default, explicit escalation paths when needed.
- Extensible provider model for search/fetch/extract and optional anti-bot tooling.

### Key Decisions

- **[D1]** Default behavior is fail fast; add “try harder” as an explicit `--policy` mode.
- **[D2]** Robots.txt is warn-only by default; `strict` policy can respect.
- **[D3]** Cache raw responses with bounded size; default TTL `7d` (configurable).
- **[D4]** Prefer configured reliable providers (API keys/endpoints) over keyless fallbacks.
- **[D5]** Firecrawl is integrated only via an endpoint provider (avoid vendoring AGPL code).

---

## Current State

**Last Updated**: 2026-01-13

### What's Working
- Spec draft and defaults: `docs/spec.md`
- Research notes and references: `docs/research.md`
- Repo overview: `README.md`
- Session continuity config: `.long-task-harness/*`, `AGENTS.md`, `.claude/settings.json`
- Python reference implementation scaffold: `pyproject.toml`, `src/wstk/*`, `uv.lock`
- Working CLI: `wstk providers|search|pipeline|fetch|render|extract|eval`
- Sample eval suite: `suites/search-basic.jsonl`

### What's Not Working
- Extraction quality needs tuning for docs-heavy pages (formatting / code blocks)

### Blocked On
- None.

---

## Session Log

### Session 1 | 2026-01-06 | Commits: b7e2984..103ae4b

#### Metadata
- **Features**: docs-001 (completed), harness-001 (completed)
- **Files Changed**:
  - `README.md` - repo overview
  - `docs/spec.md` - spec draft (CLI, providers, policy modes)
  - `docs/research.md` - research + safety references
  - `.long-task-harness/*` - harness tracking + project plan
  - `AGENTS.md` - persistent harness invocation (Codex)
  - `.claude/settings.json` - Claude Code hooks
- **Commit Summary**: `Add initial web search toolkit spec`, `Document Python tooling: pyright`, `Add additional tooling: uv, pre-commit, CI`, `chore: initialize long-task-harness`

#### Goal
Capture spec + research and set up continuity harness

#### Accomplished
- [x] Wrote spec and research notes
- [x] Documented defaults (policy modes, caching, provider precedence, Firecrawl endpoint provider)
- [x] Initialized long-task-harness
- [x] Replaced placeholder harness features with project plan
- [x] Added persistent harness invocation (`AGENTS.md`)
- [x] Installed Claude Code project hooks (`.claude/settings.json`)
- [x] Installed repo-local git pre-commit hook (not tracked in git)

#### Decisions
- **[D1]** Fail-fast default with `--policy` bundling (standard/strict/permissive).
- **[D2]** Warn-only robots default; strict mode available.
- **[D3]** Prefer configured reliable providers by default.

#### Context & Learnings
- Local “browser with profile/cookies” tools can be powerful but high privilege; keep them as explicit escalation paths.
- Existing skills often require API keys; the keyless baseline needs careful choice to avoid brittle scraping.

#### Next Steps
1. Add Python package + CLI scaffold (uv, ruff, pyright, pytest)
2. Implement baseline providers (keyless search + HTTP fetch + readability extraction)
3. Decide the “good enough” keyless search baseline + default extraction shape (reader-mode vs doc-mode)

---

### Session 2 | 2026-01-06 | Commits: ed849fe..ea363cd

#### Metadata
- **Features**: docs-001 (progressed), harness-001 (progressed)
- **Files Changed**:
  - `docs/spec.md` - CLI refinements (`--plain`, `--no-color`, `--no-input`), clearer error modes, Firecrawl auto gating
  - `.long-task-harness/features.json` - add eval + wrapper features; refine CLI/provider requirements
- **Commit Summary**: `docs: refine spec and feature roadmap`

#### Goal
Refine the CLI contract and roadmap based on early review

#### Accomplished
- [x] Tightened CLI output modes (`--plain`) and non-interactive behavior (`--no-input`)
- [x] Clarified failure modes (added exit code for “needs render / JS-only”)
- [x] Clarified Firecrawl endpoint auto-selection vs explicit opt-in (privacy surface)
- [x] Expanded roadmap to include wrappers + eval harness

#### Decisions
- **[D6]** Add `--plain` as a stable piping mode (URLs one-per-line for search).
- **[D7]** Gate remote/high-privacy-surface providers in `auto` by default; require explicit opt-in for remote/cloud endpoints.

#### Next Steps
1. Add Python package + CLI scaffold (uv, ruff, pyright, pytest)
2. Implement baseline providers (keyless search + HTTP fetch + readability extraction)
3. Decide the “good enough” keyless search baseline + default extraction shape (reader-mode vs doc-mode)

---

### Session 3 | 2026-01-06 | Commits: ea363cd..f43a39d

#### Metadata
- **Features**: py-setup-001 (completed), cli-001 (completed), providers-001 (progressed), fetch-001 (progressed), extract-001 (progressed)
- **Files Changed**:
  - `pyproject.toml` - Python package metadata + tooling deps (ruff/pyright/pytest)
  - `uv.lock` - locked dependencies
  - `src/wstk/*` - core implementation (CLI, cache, fetch, search, extract)
  - `tests/*` - unit tests
- **Commit Summary**: `feat: add v0.1.0 python CLI scaffold`

#### Goal
Build a runnable v0.1.0 reference implementation

#### Accomplished
- [x] Added `wstk` CLI with `providers`, `search`, `fetch`, `extract`
- [x] Implemented keyless search (`ddgs`) and optional Brave API search (`BRAVE_API_KEY`)
- [x] Implemented HTTP fetch with basic caching (TTL + size budget) and block/JS-only detection heuristics
- [x] Implemented readability-based extraction to markdown/text
- [x] Added tests + `ruff` + `pyright` and verified locally

#### Decisions
- **[D8]** Prefer a minimal built-in baseline (ddgs + httpx + readability) and iterate extraction quality with eval later.

#### Next Steps
1. Add a proper `render` command (Playwright optional dependency) and plumb `extract --method browser`
2. Implement a `docs` extraction strategy (better headings/code handling) and decide default “doc mode” output
3. Add wrappers/skills for agent runtimes (Codex/Claude/Droid) and a tiny eval harness (`eval-001`)

---

### Session 4 | 2026-01-06 | Commits: 9b50a36..5fbe3a6

#### Metadata
- **Features**: docs-001 (progressed), render-001 (started), pipeline-001 (started)
- **Files Changed**:
  - `docs/spec.md` - record v0.1.0 implementation status and `--plain` semantics
  - `.long-task-harness/features.json` - add `render-001` and `pipeline-001`
- **Commit Summary**: `docs: align spec and roadmap with v0.1.0`

#### Goal
Align the spec and roadmap to what’s now implemented

#### Accomplished
- [x] Documented current implementation status (v0.1.0) and remaining gaps
- [x] Clarified `--plain` semantics for `fetch` and `extract`
- [x] Added explicit roadmap items for browser rendering and pipeline helper

#### Next Steps
1. Decide how we want `render-001` to behave in strict vs standard vs permissive policy
2. Implement `render` as an optional dependency (Playwright) and plumb `extract --method browser`
3. Define a small `pipeline` output schema that’s maximally agent-friendly

---

### Session 5 | 2026-01-06 | Commits: 376bdd0..e18fac8

#### Metadata
- **Features**: py-setup-001 (progressed), cli-001 (progressed)
- **Files Changed**:
  - `docs/test-plan.md` - explicit test plan for CLI + behaviours
  - `tests/test_cli_contract.py` - contract tests for output modes, exit codes, policy gating
  - `src/wstk/cli.py` - fix argparse global flag precedence (global flags now work before or after subcommands)
- **Commit Summary**: `test: add test plan and CLI contract tests`

#### Goal
Make the agent-facing contract testable and verify real-world search behaviour

#### Accomplished
- [x] Defined a test plan focused on contract stability and safe failure modes
- [x] Added contract tests for JSON envelope, `--plain` output, and strict policy gating
- [x] Fixed CLI parsing bug where global flags before the subcommand were being overwritten
- [x] Compared `wstk search` output against a separate “manual” DuckDuckGo HTML scrape for the same query

#### Notes
- `wstk search` defaulted to `brave_api` in this environment (because `BRAVE_API_KEY` is configured).
- Manual DuckDuckGo HTML results differed from Brave API results (more blog/SEO hits), while the top results overlapped.

#### Next Steps
1. Decide policy semantics for `render` (especially `strict` vs `standard`) and implement `render-001`
2. Add a minimal `pipeline` command contract (even if it’s just `search` + `extract` for top-1)

### Session 6 | 2026-01-06 | Commits: e18fac8..bfcac44

#### Metadata
- **Features**: eval-001 (progressed), docs-001 (progressed), cli-001 (progressed)
- **Files Changed**:
  - `src/wstk/cli.py` - add `eval` command + typed summaries
  - `src/wstk/eval/*` - suite parsing + scoring utilities
  - `suites/search-basic.jsonl` - sample dev-docs suite
  - `tests/test_cli_eval_contract.py`, `tests/test_eval_*` - eval contract + unit tests
  - `docs/spec.md`, `docs/test-plan.md`, `README.md` - document eval behavior
  - `.long-task-harness/*` - record eval feature progress
- **Commit Summary**: `feat: add eval harness`

#### Goal
Add a small, cache-backed eval harness to compare search providers and track basic quality over time

#### Accomplished
- [x] Implemented `wstk eval --suite ...` with a suite parser (JSON/JSONL), hit@k + MRR scoring, and URL overlap
- [x] Added a sample suite and unit/contract tests for determinism and envelope stability

#### Next Steps
1. Extend eval to cover fetch/extract metrics (blocked rate, extraction heuristics)
2. Implement `pipeline` and `render` escalation paths

---

### Session 7 | 2026-01-06 | Commits: bfcac44..eafe5aa

#### Metadata
- **Features**: docs-001 (progressed)
- **Files Changed**:
  - `README.md` - public-facing overview, usage examples, safety notes
  - `docs/spec.md`, `docs/research.md` - small public-facing edits
  - `CONTRIBUTING.md`, `SECURITY.md` - contribution and reporting guidelines
- **Commit Summary**: `docs: prep repo for public release`

#### Goal
Prepare the repo for public release (docs + hygiene)

#### Accomplished
- [x] Added contributor-facing docs and clarified usage
- [x] Removed environment-specific references from research notes

---

### Session 8 | 2026-01-06 | Commits: eafe5aa..4a4ef83

#### Metadata
- **Features**: cli-001 (progressed)
- **Files Changed**:
  - `src/wstk/cli.py` - slimmed down and delegated command logic
  - `src/wstk/cli_support.py` - shared CLI helpers
  - `src/wstk/commands/*` - split command implementations into modules
  - `tests/test_cli_contract.py`, `tests/test_cli_eval_contract.py` - adjust patch targets
  - `.long-task-harness/*` - record feature progress
- **Commit Summary**: `refactor: split CLI into command modules`

#### Goal
Refactor for code cleanliness (smaller modules, clearer responsibilities)

#### Accomplished
- [x] Split CLI command logic into `src/wstk/commands/*` and reduced `cli.py` size
- [x] Preserved CLI contract (output modes, exit codes) with updated tests

---

### Session 9 | 2026-01-06 | Commits: 4a4ef83..50176f8

#### Metadata
- **Features**: cli-001 (progressed), eval-001 (progressed)
- **Files Changed**:
  - `src/wstk/cli.py` - subcommands register their own args; dispatch via `_handler`
  - `src/wstk/cli_support.py` - add output helpers and centralized URL policy gating
  - `src/wstk/commands/*` - use shared output/policy helpers; co-locate arg registration
  - `src/wstk/eval/runner.py` - extract eval runner
- **Commit Summary**: `refactor: streamline CLI dispatch and eval runner`

#### Goal
Further reduce duplication and keep command modules self-contained

#### Accomplished
- [x] Co-located argparse registration with each command via `register(...)` and `_handler` dispatch
- [x] Centralized domain/policy URL gating (`enforce_url_policy`) and output selection helpers (`wants_json`, `wants_plain`)
- [x] Extracted eval logic into `src/wstk/eval/runner.py` to keep CLI code thin

#### Next Steps
1. Decide policy semantics for `render` (especially `strict` vs `standard`) and implement `render-001`
2. Add a minimal `pipeline` command contract (even if it’s just `search` + `extract` for top-1)

---

### Session 10 | 2026-01-06 | Commits: e4fc7a3..82e84b6

#### Metadata
- **Features**: docs-001 (progressed)
- **Files Changed**:
  - `LICENSE` - add MIT license text
  - `README.md` - record license choice
- **Commit Summary**: `docs: add MIT license`

#### Goal
Make the repository publishable with a clear OSS license

#### Accomplished
- [x] Added MIT `LICENSE`
- [x] Updated README license section

---

### Session 11 | 2026-01-06 | Commits: 3bdcba9..b1d5b04

#### Metadata
- **Features**: wrappers-001 (progressed)
- **Files Changed**:
  - `SKILL.md` - agent skill definition for Claude Code / pi-coding-agent

#### Goal
Add agent skill wrapper for Claude Code integration

#### Accomplished
- [x] Created `SKILL.md` with proper frontmatter (name + description)
- [x] Documented setup, commands (search/extract/fetch/providers), common patterns
- [x] Included output formats, exit codes, global flags, and when-to-use guidance
- [x] Symlinked to `~/.claude/skills/web-search` for local availability

#### Notes
- Skill uses `{baseDir}/.venv/bin/wstk` paths for portability
- Description tuned for skill triggering: "web search", "content extraction", "documentation lookup"

#### Next Steps
1. Test skill in fresh Claude Code session
2. Consider adding `references/` for advanced troubleshooting (403s, JS-only pages)

### Session 12 | 2026-01-12 | Commits: none

#### Metadata
- **Features**: providers-001 (completed)
- **Files Changed**:
  - `src/wstk/search/registry.py` - add provider metadata + warnings helpers
  - `src/wstk/commands/search_cmd.py` - append provider privacy warnings
  - `src/wstk/commands/eval_cmd.py` - propagate provider warnings
  - `src/wstk/commands/providers_cmd.py` - include privacy_warning metadata
  - `docs/spec.md` - document `privacy_warning` in providers output
  - `.long-task-harness/features.json` - mark providers-001 complete
  - `.long-task-harness/long-task-progress.md` - add session 12 entry
- **Commit Summary**: none (not committed)

#### Goal
Surface provider privacy warnings and metadata for search providers

#### Accomplished
- [x] Added provider metadata registry with privacy warnings
- [x] Wired search/eval to emit provider warnings in JSON envelopes
- [x] Included privacy warnings in `wstk providers` output and spec

#### Decisions
- None.

#### Surprises
- None.

#### Context & Learnings
- Tests not run (not requested).

#### Next Steps
1. Fill remaining gaps in `fetch-001` and `extract-001`
2. Define policy behavior for `render-001` and implement `wstk render`

---

### Session 13 | 2026-01-12 | Commits: none

#### Metadata
- **Features**: fetch-001 (completed)
- **Files Changed**:
  - `src/wstk/fetch/http.py` - add content-type sniffing + diagnostics helpers
  - `tests/test_fetch_http.py` - add content-type and diagnostics tests
  - `docs/spec.md` - document blocked/JS-only next steps
  - `.long-task-harness/features.json` - mark fetch-001 complete
  - `.long-task-harness/long-task-progress.md` - add session 13 entry
- **Commit Summary**: none (not committed)

#### Goal
Complete fetch pipeline diagnostics and content-type detection

#### Accomplished
- [x] Added content-type sniffing fallback and normalized types
- [x] Added structured blocked/needs_render diagnostics with next-step guidance
- [x] Added tests covering sniffing and diagnostics
- [x] Documented blocked/JS-only next-step guidance in the spec

#### Decisions
- None.

#### Surprises
- **[S1]** `uv run pytest` omits dev extras; `uv run --extra dev` is required for `respx`.

#### Context & Learnings
- Tests: `uv run --extra dev pytest tests/test_fetch_http.py` (passed).

#### Next Steps
1. Finish `extract-001` (doc-mode output + provenance + truncation)
2. Define policy behavior for `render-001` and implement `wstk render`

---

### Session 14 | 2026-01-12 | Commits: none

#### Metadata
- **Features**: extract-001 (completed)
- **Files Changed**:
  - `docs/spec.md` - document doc-mode output and truncation flags
  - `src/wstk/commands/extract_cmd.py` - add docs strategy, provenance for file inputs, max-tokens
  - `src/wstk/extract/docs_extractor.py` - implement docs-mode extraction + heuristics
  - `src/wstk/models.py` - add structured doc extraction data
  - `tests/test_extract_docs.py` - add docs + truncation tests
- **Commit Summary**: none (not committed)

#### Goal
Complete extract-001 (docs mode + provenance + truncation)

#### Accomplished
- [x] Implemented docs-mode extraction with sections and links
- [x] Returned Document provenance for file/stdin inputs
- [x] Added `--max-tokens` truncation and section-aware limits
- [x] Added extraction tests and updated spec

#### Decisions
- None.

#### Surprises
- None.

#### Context & Learnings
- Tests: `uv run --extra dev pytest tests/test_extract_docs.py` (passed).

#### Next Steps
1. Start safety-001 (prompt injection detection + `--redact`).
2. Add advanced troubleshooting docs for wrappers-001 or design render-001 policy.

---

### Session 15 | 2026-01-12 | Commits: none

#### Metadata
- **Features**: safety-001 (completed)
- **Files Changed**:
  - `docs/spec.md` - document prompt-injection warnings + redaction posture
  - `src/wstk/cli.py` - redact verbose error details when `--redact`
  - `src/wstk/cli_support.py` - apply redaction to JSON envelopes + update flag help
  - `src/wstk/commands/extract_cmd.py` - add injection warnings and redacted plain output
  - `src/wstk/commands/fetch_cmd.py` - redact URLs in non-JSON output
  - `src/wstk/commands/search_cmd.py` - redact text/snippets + raw payloads
  - `src/wstk/safety.py` - add redaction + prompt injection helpers
  - `src/wstk/urlutil.py` - strip userinfo in redacted URLs
  - `tests/test_extract_docs.py` - add prompt injection + redaction tests
  - `tests/test_urlutil.py` - add userinfo redaction coverage
  - `.long-task-harness/features.json` - mark safety-001 complete
  - `.long-task-harness/long-task-progress.md` - add session 15 entry
- **Commit Summary**: none (not committed)

#### Goal
Implement safety warnings and redaction support

#### Accomplished
- [x] Added prompt-injection detection with warnings surfaced in JSON output
- [x] Implemented redaction helpers for URLs/secrets and applied them across outputs
- [x] Added tests for injection warnings and redaction behavior

#### Decisions
- None.

#### Surprises
- None.

#### Context & Learnings
- Tests: `uv run --extra dev pytest tests/test_extract_docs.py tests/test_urlutil.py` (passed).

#### Next Steps
1. Finish wrappers-001 by adding advanced troubleshooting references.
2. Define policy behavior for render-001 and implement `wstk render`.

---

### Session 16 | 2026-01-12 | Commits: none

#### Metadata
- **Features**: wrappers-001 (completed)
- **Files Changed**:
  - `SKILL.md` - add decision guide, agent defaults, references
  - `README.md` - link wrapper docs and references
  - `docs/claude-code.md` - Claude Code wrapper usage
  - `references/providers.md` - provider selection and flags
  - `references/troubleshooting.md` - blocked/JS-only troubleshooting
  - `.long-task-harness/features.json` - mark wrappers-001 complete
  - `.long-task-harness/long-task-progress.md` - add session 16 entry
- **Commit Summary**: none (not committed)

#### Goal
Finish wrapper docs and references for agent runtimes

#### Accomplished
- [x] Added troubleshooting/provider reference docs for advanced flags
- [x] Documented Claude Code wrapper usage and linked wrapper docs in README
- [x] Clarified SKILL decision guide and JSON-first agent defaults

#### Decisions
- None.

#### Surprises
- None.

#### Context & Learnings
- Tests not run (docs-only changes).

#### Next Steps
1. Define policy behavior for render-001 and implement `wstk render`.
2. Expand eval-001 with extraction metrics or suite coverage.

---

### Session 17 | 2026-01-12 | Commits: none

#### Metadata
- **Features**: eval-001 (completed)
- **Files Changed**:
  - `src/wstk/eval/runner.py` - add fetch/extract metrics and summaries
  - `src/wstk/commands/eval_cmd.py` - wire fetch settings and strict-policy handling
  - `tests/test_cli_eval_contract.py` - stub fetch and assert new summaries
  - `docs/spec.md` - mark eval metrics implemented and document target selection
  - `docs/test-plan.md` - update eval coverage note
  - `README.md` - update eval status
  - `.long-task-harness/features.json` - mark eval-001 complete
  - `.long-task-harness/long-task-progress.md` - add session 17 entry
- **Commit Summary**: none (not committed)

#### Goal
Complete eval-001 by adding fetch/extract metrics and summaries

#### Accomplished
- [x] Added fetch/extract evaluation path with blocked/needs_render counts and extraction heuristics
- [x] Updated eval summaries, docs, and tests for new metrics
- [x] Recorded eval-001 completion in harness tracking

#### Decisions
- None.

#### Surprises
- None.

#### Context & Learnings
- Tests: `uv run --extra dev pytest tests/test_cli_eval_contract.py tests/test_eval_suite.py` (passed).

#### Next Steps
1. Define policy behavior for render-001 and implement `wstk render`.
2. Implement the `pipeline-001` command surface.

---

### Session 18 | 2026-01-13 | Commits: none

#### Metadata
- **Features**: render-001 (completed)
- **Files Changed**:
  - `src/wstk/render/browser.py` - add Playwright rendering pipeline
  - `src/wstk/render/__init__.py` - add render package
  - `src/wstk/commands/render_cmd.py` - add render command
  - `src/wstk/commands/extract_cmd.py` - support browser method + auto fallback
  - `src/wstk/commands/providers_cmd.py` - surface browser provider availability
  - `src/wstk/models.py` - add render metadata to Document
  - `src/wstk/cli.py` - register render command
  - `tests/test_cli_render_contract.py` - add render/extract contract tests
  - `README.md` - document render usage and install steps
  - `SKILL.md` - update render guidance
  - `docs/spec.md` - update implementation status
  - `docs/test-plan.md` - refresh JS-only guidance note
  - `references/troubleshooting.md` - refresh JS-only escalation guidance
  - `.long-task-harness/features.json` - mark render-001 complete
  - `.long-task-harness/long-task-progress.md` - add session 18 entry
- **Commit Summary**: none (not committed)

#### Goal
Implement local browser rendering and browser extraction path

#### Accomplished
- [x] Added Playwright-backed `wstk render` command with evidence capture and error modes
- [x] Wired `wstk extract --method browser` and `--method auto` fallback to renderer
- [x] Added render contract tests and updated docs to reflect render availability

#### Decisions
- None.

#### Surprises
- None.

#### Context & Learnings
- Tests: `uv run --extra dev pytest tests/test_cli_render_contract.py` (passed).

#### Next Steps
1. Implement the `pipeline-001` command surface.
2. Tune docs-heavy extraction formatting and code blocks.

---

### Session 19 | 2026-01-13 | Commits: none

#### Metadata
- **Features**: pipeline-001 (completed)
- **Files Changed**:
  - `src/wstk/commands/pipeline_cmd.py` - add pipeline command implementation
  - `src/wstk/cli.py` - register pipeline command
  - `tests/test_cli_pipeline_contract.py` - pipeline contract tests
  - `README.md` - document pipeline usage
  - `SKILL.md` - add pipeline guidance
  - `docs/spec.md` - mark pipeline implemented
  - `.long-task-harness/features.json` - mark pipeline-001 complete
  - `.long-task-harness/long-task-progress.md` - update progress log
- **Commit Summary**: none (not committed)

#### Goal
Implement the `pipeline-001` command surface

#### Accomplished
- [x] Added `wstk pipeline` command with plan mode and domain preference selection
- [x] Wired pipeline extraction via HTTP/browser with policy gating
- [x] Added pipeline contract tests and updated docs

#### Decisions
- None.

#### Surprises
- None.

#### Context & Learnings
- Tests: `uv run --extra dev pytest tests/test_cli_pipeline_contract.py` (passed).

#### Next Steps
1. Tune docs-heavy extraction formatting and code blocks.
2. Evaluate whether pipeline output needs additional selection metadata.

---

### Session 20 | 2026-01-12 | Commits: none

#### Metadata
- **Features**: docs-001 (progressed), harness-001 (progressed)
- **Files Changed**:
  - `.long-task-harness/long-task-progress.md` - record post-ralph status + spec check
- **Commit Summary**: none (not committed)

#### Goal
Document post-ralph status and spec alignment

#### Accomplished
- [x] Captured spec status (v0.1.0 features implemented; open questions remain)
- [x] Recorded that a code review/refactor pass is still needed before new work

#### Decisions
- None.

#### Surprises
- None.

#### Context & Learnings
- Feature checklist reports 12/12 complete; spec lists all core commands implemented.
- A cleanup/refactor pass is still required before proceeding.

#### Next Steps
1. Review code for clarity/refactors and remove temporary artifacts.
2. Reconcile spec gaps (e.g., `--site`, `--accept`, robots enforcement) or update spec.

---

### Session 21 | 2026-01-13 | Commits: none

#### Metadata
- **Features**: cli-001 (progressed), extract-001 (progressed), pipeline-001 (progressed)
- **Files Changed**:
  - `src/wstk/extract/utils.py` - centralize extraction helpers + truncation
  - `src/wstk/commands/support.py` - shared fetch/render settings builders
  - `src/wstk/commands/extract_cmd.py` - use shared helpers + doc assembly
  - `src/wstk/commands/pipeline_cmd.py` - use shared helpers + dedup warnings
  - `src/wstk/commands/fetch_cmd.py` - shared fetch settings
  - `src/wstk/commands/render_cmd.py` - shared render settings
  - `src/wstk/commands/eval_cmd.py` - shared fetch settings
  - `src/wstk/eval/runner.py` - shared extraction strategy
  - `src/wstk/models.py` - add `with_extracted`
  - `src/wstk/cli_support.py` - add `append_warning`
- **Commit Summary**: none (not committed)

#### Goal
Refactor shared extraction + settings logic

#### Accomplished
- [x] Centralized extraction strategy, truncation, and output selection helpers
- [x] Centralized fetch/render settings creation across commands
- [x] Manual CLI checks for search/fetch/extract/pipeline using real docs URL

#### Decisions
- None.

#### Surprises
- None.

#### Context & Learnings
- Tests: `uv run --extra dev pytest` (passed).
- Manual checks: `wstk providers`, `wstk search`, `wstk pipeline --plan`, `wstk fetch`, `wstk extract` against `docs.python.org` (passed).

#### Next Steps
1. Continue spec-alignment cleanup (e.g., `--site`, `--accept`, robots enforcement).
2. Consider docs extraction cleanup for large TOCs/nav content.

---

### Session 22 | 2026-01-13 | Commits: none

#### Metadata
- **Features**: spec-001 (implemented)
- **Files Changed**:
  - `src/wstk/commands/search_cmd.py` - add `--site` query augmentation + allow-domain filter
  - `tests/test_cli_contract.py` - cover `--site` behavior
  - `README.md` - add `--site` usage example
  - `.long-task-harness/spec-gaps.json` - mark spec-001 implemented
- **Commit Summary**: none (not committed)

#### Goal
Implement `--site` flag for search

#### Accomplished
- [x] Added `--site` parsing with query augmentation and allow-domain filtering.
- [x] Added CLI contract test for `--site` behavior.
- [x] Documented `--site` usage and updated spec gap status.

#### Decisions
- None.

#### Surprises
- None.

#### Context & Learnings
- Tests: `uv run --extra dev pytest tests/test_cli_contract.py` (passed).

#### Next Steps
1. Triage remaining spec gaps (spec-002/003/004).

---

### Session 23 | 2026-01-13 | Commits: none

#### Metadata
- **Features**: cli-001 (verified)
- **Files Changed**:
  - `.long-task-harness/long-task-progress.md` (+lines/-lines) - record E2E CLI run
- **Commit Summary**: none

#### Goal
Run E2E CLI usage loop for search/fetch/extract/pipeline

#### Accomplished
- [x] Ran E2E CLI commands for search/fetch/extract/pipeline

#### Decisions
- None.

#### Surprises
- None.

#### Context & Learnings
- `uv run wstk search "openai codex cli" --plain -n 5` → returned 5 OpenAI/Codex URLs.
- `uv run wstk fetch https://example.com/ --plain` → wrote body to cache path.
- `uv run wstk extract https://example.com/ --plain --text | head -n 20` → extracted "Example Domain" text.
- `uv run wstk pipeline "openai codex cli" --plain --top-k 3 --extract-k 1 | head -n 20` → extracted content from `https://developers.openai.com/codex/cli/`.

#### Next Steps
1. Continue spec-gap triage (spec-002/003/004).

---

### Session 24 | 2026-01-13 | Commits: none

#### Metadata
- **Features**: spec-001 (completed)
- **Files Changed**:
  - `src/wstk/urlutil.py` - add domain normalization helpers
  - `src/wstk/cli_support.py` - normalize allow/block domain inputs
  - `src/wstk/commands/search_cmd.py` - reuse normalization for `--site`
  - `tests/test_cli_contract.py` - exercise URL-style `--site` input
  - `.long-task-harness/spec-gaps.json` - mark spec-001 done
  - `.long-task-harness/long-task-progress.md` - record cleanup session
- **Commit Summary**: none

#### Goal
Cleanup `--site` handling and close spec-001 gap

#### Accomplished
- [x] Normalized domain inputs for `--site`, `--allow-domain`, `--block-domain`.
- [x] Adjusted CLI contract test to cover URL-style `--site` input.
- [x] Marked spec-001 gap as done with a final note.

#### Decisions
- None.

#### Surprises
- None.

#### Context & Learnings
- Domain normalization now accepts full URLs (scheme/path/port) and dedupes entries.

#### Next Steps
1. Triage remaining spec gaps (spec-002/003/004).
2. Deferred: add coverage for allow/block normalization in fetch/extract flows.

---

### Session 25 | 2026-01-13 | Commits: none

#### Metadata
- **Features**: spec-002 (implemented)
- **Files Changed**:
  - `src/wstk/cli_support.py` - allow `--accept` header override
  - `src/wstk/commands/fetch_cmd.py` - add `--accept` flag
  - `src/wstk/commands/extract_cmd.py` - add `--accept` flag
  - `tests/test_cli_contract.py` - assert `--accept` header propagation
  - `.long-task-harness/spec-gaps.json` - mark spec-002 implemented
- **Commit Summary**: none

#### Goal
Implement `--accept` override for HTTP fetch/extract

#### Accomplished
- [x] Added `--accept` flag for fetch/extract and header parsing support.
- [x] Added CLI contract test for accept header override.
- [x] Updated spec gap status to implemented.

#### Decisions
- None.

#### Context & Learnings
- Tests: `uv run --extra dev pytest tests/test_cli_contract.py` (passed).

#### Next Steps
1. Triage remaining spec gaps (spec-003/004).

---

### Session 26 | 2026-01-13 | Commits: none

#### Metadata
- **Features**: cli-001 (verified)
- **Files Changed**:
  - `.long-task-harness/long-task-progress.md` (+lines/-lines) - record E2E CLI run
- **Commit Summary**: none

#### Goal
Run E2E CLI usage loop for search/fetch/extract/pipeline

#### Accomplished
- [x] Ran CLI commands for search/fetch/extract/pipeline.

#### Decisions
- None.

#### Context & Learnings
- `uv run wstk search "openai codex cli" --plain -n 5` → returned 5 Codex-related URLs.
- `uv run wstk fetch https://example.com/ --plain` → wrote cached body path.
- `uv run wstk extract https://example.com/ --plain --text | head -n 20` → extracted Example Domain text.
- `uv run wstk pipeline "openai codex cli" --plain --top-k 3 --extract-k 1 | head -n 20` → extracted content from Codex CLI page.

#### Next Steps
1. Continue spec-gap triage (spec-003/004).

---

### Session 27 | 2026-01-13 | Commits: none

#### Metadata
- **Features**: spec-002 (completed)
- **Files Changed**:
  - `tests/test_cli_contract.py` - add fetch/extract accept override coverage
  - `docs/spec.md` - document `--accept` for extract
  - `docs/test-plan.md` - add `--accept` contract coverage
  - `.long-task-harness/spec-gaps.json` - mark spec-002 done
  - `.long-task-harness/long-task-progress.md` - record cleanup session
- **Commit Summary**: none

#### Goal
Cleanup `--accept` work and close spec-002 gap

#### Accomplished
- [x] Added CLI contract coverage for extract `--accept` plus shared fetch result helper.
- [x] Documented extract `--accept` and test-plan coverage for header overrides.
- [x] Marked spec-002 gap as done with a final note.

#### Decisions
- None.

#### Surprises
- None.

#### Context & Learnings
- Deferred: consider aligning extract header flags with fetch (`--header`, `--headers-file`, `--user-agent`) if needed.

#### Next Steps
1. Continue spec-gap triage (spec-003/004).

---

### Session 28 | 2026-01-13 | Commits: none

#### Metadata
- **Features**: spec-003 (implemented)
- **Files Changed**:
  - `src/wstk/robots.py` - add robots.txt checker
  - `src/wstk/cli_support.py` - enforce robots policy helper
  - `src/wstk/commands/fetch_cmd.py` - apply robots policy before fetch
  - `src/wstk/commands/extract_cmd.py` - enforce robots policy for URL extraction
  - `src/wstk/commands/render_cmd.py` - enforce robots policy before render
  - `src/wstk/commands/pipeline_cmd.py` - enforce robots policy for candidates
  - `tests/test_cli_contract.py` - add robots warn/respect coverage
  - `docs/test-plan.md` - document robots policy tests
  - `.long-task-harness/spec-gaps.json` - mark spec-003 implemented
  - `.long-task-harness/long-task-progress.md` - record session
- **Commit Summary**: none

#### Goal
Implement robots policy handling for network ops.

#### Accomplished
- [x] Added robots.txt checker and CLI enforcement with warn/respect behaviors.
- [x] Added CLI contract tests for robots warnings/blocking.
- [x] Updated spec gap status and test plan coverage.

#### Decisions
- None.

#### Context & Learnings
- Tests not run (not requested).

#### Next Steps
1. Continue spec-gap triage (spec-004).

---

### Session 29 | 2026-01-13 | Commits: none

#### Metadata
- **Features**: cli-001 (verified)
- **Files Changed**:
  - `.long-task-harness/long-task-progress.md` (+lines/-lines) - record E2E CLI usage loop
- **Commit Summary**: none

#### Goal
Run E2E CLI usage loop for search/fetch/extract/pipeline

#### Accomplished
- [x] Ran CLI commands for search/fetch/extract/pipeline.

#### Decisions
- None.

#### Context & Learnings
- `uv run wstk search "openai codex cli" --plain | head -n 5` → returned OpenAI Codex CLI URLs.
- `uv run wstk fetch https://example.com/ --plain` → wrote cached body path.
- `uv run wstk extract https://example.com/ --plain --text | head -n 20` → extracted Example Domain text.
- `uv run wstk pipeline "openai codex cli" --plain | head -n 20` → extracted Codex CLI page content.

#### Next Steps
1. Continue spec-gap triage (spec-004).

---

### Session 30 | 2026-01-13 | Commits: none

#### Metadata
- **Features**: spec-004 (completed)
- **Files Changed**:
  - `src/wstk/commands/providers_cmd.py` (+lines/-lines) - add helper and list extract providers (readability/docs)
  - `tests/test_cli_contract.py` (+lines/-lines) - assert docs provider appears in plain output
  - `docs/spec.md` (+lines/-lines) - note docs extractor in providers output
  - `docs/test-plan.md` (+lines/-lines) - document providers plain output expectations
  - `.long-task-harness/spec-gaps.json` (+lines/-lines) - mark spec-004 done
  - `.long-task-harness/long-task-progress.md` (+lines/-lines) - record session
- **Commit Summary**: none

#### Goal
Close spec-004 and cleanup providers output.

#### Accomplished
- [x] Added docs extractor to providers list with shared helper.
- [x] Updated contract expectations and docs for providers output.
- [x] Marked spec-004 gap as done with final note.

#### Decisions
- None.

#### Surprises
- None.

#### Context & Learnings
- Deferred: normalize `--prefer-domain` inputs with `normalize_domains` if consistency issues show up.

#### Next Steps
1. Optional: align `--prefer-domain` normalization with allow/block rules.

---

### Session 31 | 2026-01-13 | Commits: none

#### Metadata
- **Features**: cli-001 (verified)
- **Files Changed**:
  - `.long-task-harness/long-task-progress.md` (+lines/-lines) - record E2E CLI usage loop
- **Commit Summary**: none

#### Goal
Run E2E CLI usage loop for search/fetch/extract/pipeline.

#### Accomplished
- [x] Ran CLI commands for search/fetch/extract/pipeline.

#### Decisions
- None.

#### Context & Learnings
- `uv run wstk search "openai codex cli" --plain | head -n 5` → returned OpenAI Codex CLI URLs.
- `uv run wstk fetch https://example.com/ --plain` → wrote cached body path.
- `uv run wstk extract https://example.com/ --plain --text | head -n 20` → extracted Example Domain text.
- `uv run wstk pipeline "openai codex cli" --plain | head -n 20` → extracted Codex CLI page content.

#### Next Steps
1. None.

---

### Session 32 | 2026-01-13 | Commits: none

#### Metadata
- **Features**: spec-003 (completed)
- **Files Changed**:
  - `.long-task-harness/spec-gaps.json` (+lines/-lines) - mark spec-003 done after tests
  - `.long-task-harness/long-task-progress.md` (+lines/-lines) - record session
- **Commit Summary**: none

#### Goal
Verify robots policy tests and close spec-003.

#### Accomplished
- [x] Ran CLI contract tests for robots policy coverage.
- [x] Marked spec-003 as done after test pass.

#### Decisions
- None.

#### Context & Learnings
- `uv run --extra dev pytest tests/test_cli_contract.py` passed (12 tests).

#### Next Steps
1. Commit and push spec-gap updates + docs/tests.

---

### Session 33 | 2026-01-13 | Commits: none

#### Metadata
- **Features**: extract-baselines (started)
- **Files Changed**:
  - `tests/data/extract/docs-sample.html` (+lines/-lines) - synthetic docs fixture
  - `tests/data/extract/docs-sample.docs.md` (+lines/-lines) - docs strategy markdown snapshot
  - `tests/data/extract/docs-sample.docs.txt` (+lines/-lines) - docs strategy text snapshot
  - `tests/data/extract/docs-sample.readability.md` (+lines/-lines) - readability markdown snapshot
  - `tests/data/extract/docs-sample.readability.txt` (+lines/-lines) - readability text snapshot
  - `tests/data/extract/README.md` (+lines/-lines) - snapshot regeneration notes
  - `docs/test-plan.md` (+lines/-lines) - link to fixture snapshots
  - `.long-task-harness/long-task-progress.md` (+lines/-lines) - record session
- **Commit Summary**: none

#### Goal
Create extraction baseline snapshots for comparison.

#### Accomplished
- [x] Added a synthetic docs fixture with nav/toc/sidebars.
- [x] Captured docs + readability outputs (markdown + text) for baseline diffs.
- [x] Documented regeneration commands and fixture location.

#### Decisions
- None.

#### Context & Learnings
- Baselines are local-only and deterministic (no network dependency).

#### Next Steps
1. Decide whether to add additional fixtures from real-world docs.

---

### Session 34 | 2026-01-13 | Commits: none

#### Metadata
- **Features**: extract-baselines (progressed)
- **Files Changed**:
  - `tests/data/e2e/README.md` (+lines/-lines) - snapshot inventory
  - `tests/data/e2e/commands.sh` (+lines/-lines) - regeneration script
  - `tests/data/e2e/*.json` (+lines/-lines) - real-world outputs
  - `docs/test-plan.md` (+lines/-lines) - link to E2E snapshots
  - `.long-task-harness/long-task-progress.md` (+lines/-lines) - record session
- **Commit Summary**: none

#### Goal
Capture real-world E2E snapshots for extraction regression checks.

#### Accomplished
- [x] Captured search/pipeline/fetch/extract outputs for stable docs and articles.
- [x] Added tough-task snapshots (JS-only, bot walls, login/auth gates, non-HTML).
- [x] Documented commands + expected outcomes in `tests/data/e2e`.

#### Decisions
- None.

#### Context & Learnings
- Some snapshots intentionally record non-zero exits (`needs_render`, `blocked`).

#### Next Steps
1. Commit E2E snapshot dataset and proceed with extraction tuning.

---

### Session 35 | 2026-01-13 | Commits: none

#### Metadata
- **Features**: extract-baselines (progressed)
- **Files Changed**:
  - `tests/data/e2e/README.md` (+lines/-lines) - comparison guidance for snapshot integrity
- **Commit Summary**: none

#### Goal
Document snapshot comparison guidance without mutating ground truth.

#### Accomplished
- [x] Added stable vs volatile field guidance for E2E snapshot comparisons.
- [x] Clarified that raw JSON snapshots remain canonical ground truth.

#### Decisions
- None.

#### Context & Learnings
- Comparisons should use derived summaries and report volatile-field deltas for context.

#### Next Steps
1. Add an optional summary/diff helper for snapshots.

<!--
=============================================================================
SESSION TEMPLATE - Copy below this line for new sessions
=============================================================================

### Session N | YYYY-MM-DD | Commits: abc123..def456

#### Metadata
- **Features**: feature-id (started|progressed|completed|blocked)
- **Files Changed**: 
  - `path/to/file.ts` (+lines/-lines) - brief description
- **Commit Summary**: `type: message`, `type: message`

#### Goal
[One-liner: what you're trying to accomplish this session]

#### Accomplished
- [x] Completed task
- [ ] Incomplete task (carried forward)

#### Decisions
- **[DN]** Decision made and rationale (reference in features.json)

#### Context & Learnings
[What you learned, gotchas, context future sessions need to know.
Focus on WHAT and WHY, not the struggle/errors along the way.]

#### Next Steps
1. [Priority 1] → likely affects: feature-id
2. [Priority 2]

=============================================================================
GUIDELINES FOR GOOD SESSION ENTRIES
=============================================================================

1. METADATA is for machines (subagent lookup)
   - Always list features touched with status
   - Always include commit range or hashes

2. DECISIONS are for continuity
   - Number them [D1], [D2] so they can be referenced
   - Copy key decisions to features.json history
   - Include rationale, not just the choice

3. CONTEXT is for future you/agents
   - Capture the WHY behind non-obvious choices
   - Note gotchas and edge cases discovered
   - Omit error-correction loops - just document resolution

4. COMMIT SUMMARY style
   - Use conventional commits: feat|fix|refactor|test|docs|chore
   - Keep to one-liners that scan quickly

5. Keep sessions BOUNDED
   - One session = one work period (not one feature)
   - If session runs long, split into multiple entries
   - Target: scannable in <30 seconds

-->
