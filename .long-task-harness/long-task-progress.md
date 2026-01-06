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
- Working CLI: `wstk providers|search|fetch|extract`

### What's Not Working
- No browser rendering path yet (`render`, `--method browser`)
- No `pipeline` and `eval` commands yet
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
