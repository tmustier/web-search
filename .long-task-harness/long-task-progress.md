# web-search - Progress Log

## Project Overview

**Started**: 2026-01-06
**Status**: Spec-first (no implementation yet)
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

### What's Not Working
- No implementation yet (no Python package / CLI / providers)
- No end-to-end demo of search → fetch → extract

### Blocked On
- Choosing the initial keyless baseline (search + fetch) that’s reliable enough without being brittle.
- Nailing default extraction outputs (reader-mode vs doc-mode) without overfitting to a single use case.

---

## Session Log

### Session 1 | 2026-01-06 | Commits: b7e2984..f45de12

#### Metadata
- **Features**: docs-001 (completed), harness-001 (completed)
- **Files Changed**:
  - `README.md` - repo overview
  - `docs/spec.md` - spec draft (CLI, providers, policy modes)
  - `docs/research.md` - research + safety references
  - `.long-task-harness/*` - harness init (uncommitted)
- **Commit Summary**: `Add initial web search toolkit spec`, `Document Python tooling: pyright`, `Add additional tooling: uv, pre-commit, CI`

#### Goal
Capture spec + research and set up continuity harness

#### Accomplished
- [x] Wrote spec and research notes
- [x] Documented defaults (policy modes, caching, provider precedence, Firecrawl endpoint provider)
- [x] Initialized long-task-harness
- [x] Replaced placeholder harness features with project plan

#### Decisions
- **[D1]** Fail-fast default with `--policy` bundling (standard/strict/permissive).
- **[D2]** Warn-only robots default; strict mode available.
- **[D3]** Prefer configured reliable providers by default.

#### Context & Learnings
- Local “browser with profile/cookies” tools can be powerful but high privilege; keep them as explicit escalation paths.
- Existing skills often require API keys; the keyless baseline needs careful choice to avoid brittle scraping.

#### Next Steps
1. Replace placeholder feature list in `.long-task-harness/features.json`
2. Add Python package + CLI scaffold (uv, ruff, pyright, pytest)
3. Implement baseline providers (keyless search + HTTP fetch + readability extraction)

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
