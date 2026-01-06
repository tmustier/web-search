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

**Last Updated**: 2026-01-06

### What's Working
- Spec draft and defaults: `docs/spec.md`
- Research notes and references: `docs/research.md`
- Repo overview: `README.md`
- Session continuity config: `.long-task-harness/*`, `AGENTS.md`, `.claude/settings.json`
- Python reference implementation scaffold: `pyproject.toml`, `src/wstk/*`, `uv.lock`
- Working CLI: `wstk providers|search|fetch|extract|eval`
- Sample eval suite: `suites/search-basic.jsonl`

### What's Not Working
- No browser rendering path yet (`render`, `--method browser`)
- No `pipeline` command yet
- Extraction quality needs tuning for docs-heavy pages (formatting / code blocks)

### Blocked On
- Defining the default “doc mode” extraction output shape (beyond readability)
- Designing explicit escalation for JS-only / blocked pages (render vs remote endpoints)

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
   - Always list files with change magnitude
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
