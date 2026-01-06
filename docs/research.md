# Research notes (browsing/search agents)

This project is motivated by common failure modes in real-world “agentic browsing”, and by the practical pain of a fragmented toolchain for:

- web search (API vs keyless vs opaque built-ins)
- fetching content (403s, JS-rendered pages, paywalls)
- extracting readable text (HTML → markdown/text)
- doing the above safely (prompt/task injection, data exfiltration risk)

## Key benchmarks / systems work

- WebArena (realistic, reproducible web environment; error analysis; “real web” challenges like CAPTCHAs/content drift): https://webarena.dev/ and paper: https://arxiv.org/html/2307.13854v4
- WebVoyager (open-web navigation with multimodal models; clear error taxonomy): https://arxiv.org/html/2401.13919v4
- BrowserGym (ecosystem to standardize web-agent evaluation across multiple benchmarks): https://arxiv.org/abs/2412.05467 and https://github.com/ServiceNow/BrowserGym
- OSWorld (real OS/web tasks; highlights GUI grounding + operational knowledge gaps): https://arxiv.org/abs/2404.07972 and https://os-world.github.io/
- Agent‑E (design principles from building a web navigation agent): https://arxiv.org/html/2407.13032v1
- BrowserArena (user-submitted real-web tasks; head-to-head comparisons; surfacing failure modes): https://arxiv.org/html/2510.02418v1

## Security / safety references

- OpenAI: “Understanding prompt injections: a frontier security challenge” (why browsing+tools changes the threat model): https://openai.com/index/prompt-injections/
- OpenAI: “Continuously hardening ChatGPT Atlas against prompt injection attacks” (agent red-teaming loop): https://openai.com/index/hardening-atlas-against-prompt-injection/
- Google Bug Hunters: “Task Injection – Exploiting agency of autonomous AI agents” (agent-specific injection framing): https://bughunters.google.com/blog/4823857172971520/task-injection-exploiting-agency-of-autonomous-ai-agents
- Brave: “Indirect prompt injection in Perplexity Comet” (browser-agent injection examples): https://brave.com/blog/comet-prompt-injection/
- OWASP GenAI: prompt injection risk overview: https://genai.owasp.org/llmrisk/llm01-prompt-injection/
- OpenAI API docs (Computer use): sandboxing guidance + built-in “pending safety checks” to reduce prompt injection risk: https://platform.openai.com/docs/guides/tools-computer-use
- Anthropic docs:
  - Web search tool (domain allow/block, `max_uses`, citations): https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool
  - Web fetch tool (explicit exfiltration warnings; no dynamic URL construction; domain allow/block; Unicode homograph warning): https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-fetch-tool
  - Search results blocks (structured RAG citations; per-result `cache_control` and `citations` toggles): https://platform.claude.com/docs/en/build-with-claude/search-results
- Model Context Protocol (MCP) security:
  - Security Best Practices (trust boundaries, session hijack + event injection): https://modelcontextprotocol.io/specification/2025-06-18/basic/security_best_practices
  - Prompt security note (validate prompt inputs/outputs): https://modelcontextprotocol.io/specification/draft/server/prompts#security

## Practical implications for tooling

Observed failure drivers that should influence toolkit design:

- **Search ambiguity → long-horizon failure**: agents waste steps browsing irrelevant results; need query refinement, domain scoping, and “result usefulness” signals.
- **JS-rendered pages**: plain HTTP fetch returns empty shells; need a browser-render fallback that can run locally and optionally reuse the user’s profile.
- **Anti-bot/403/CAPTCHA**: “bypass” is often TOS-hostile; instead the toolkit should (a) improve polite fetch defaults, (b) detect blocks, (c) fall back to interactive/local browser when appropriate.
- **Extraction quality variance**: Readability-style extraction is often better for articles; docs sites and reference pages may need different heuristics.
- **Prompt/task injection**: tool outputs are untrusted input; agents need clear separation between instructions vs content, plus safe defaults (allowlists, confirmation gates).

## Notes from existing tools (patterns worth copying / avoiding)

### Anthropic tool design patterns (web search + web fetch)

Observed “agent UX” and safety levers:

- **Separate tools**: web search and web fetch are distinct, forcing an explicit transition from “finding URLs” to “retrieving full content”.
- **Budget controls**: `max_uses` limits repeated searches/fetches per request.
- **Domain restrictions**: `allowed_domains`/`blocked_domains` at request level (and can be further restricted by org-level policies).
- **Exfiltration posture for fetching**:
  - Explicit warning that fetching in mixed-trust contexts can enable data exfiltration.
  - Restriction: model is “not allowed to dynamically construct URLs”; only fetch URLs that already exist in conversation context.
  - Warning about Unicode domain homograph attacks.
- **Citation and cache hints for RAG**:
  - Search results blocks can include `cache_control` (example: `{"type":"ephemeral"}`) and a `citations` toggle.

Implications for this project:

- Provide **allow/block domains** as first-class CLI flags.
- Provide **hard budgets** (max requests, timeouts) so agents can stay predictable.
- Make “privileged/interactive browsing” (user browser session, cookies) an explicit escalation with strong UX cues.

### Brave “indirect prompt injection” mitigations (browser-agent design)

Brave’s recommended mitigations (from their Perplexity Comet write-up):

- Separate **trusted user instruction** from **untrusted page content**.
- Treat the model’s proposed actions as **unsafe by default**; apply action-alignment checks.
- Require explicit user interaction for **security/privacy-sensitive actions**.
- Isolate **agentic browsing** from regular browsing; minimal permissions by default.

Implications for this project:

- Our toolkit should produce outputs that are easy for agents to treat as untrusted (separate “content” from “instructions-like text”, keep provenance).
- “Escalations” should be visible and consented to (especially anything that touches a real browser profile).

### Crawl4AI (popular OSS extraction/crawling library)

This project is broader than our intended scope, but its design choices are informative:

- Provides explicit **cache modes** and per-URL **multi-config** policies (e.g., “docs sites → aggressive caching; news → bypass cache”).
- Supports persistent browser profiles (auth/cookies) and has optional anti-bot/stealth features.

Reference: https://github.com/unclecode/crawl4ai

Implications for this project:

- Cache policy likely needs to be **configurable per domain/pattern** (docs vs news is a common split).
- Any “anti-bot” or “stealth” features are reputationally sensitive; if included at all, keep them optional, explicit, and bounded.

### Firecrawl (API product that collapses search→fetch→extract)

Firecrawl’s offering is service-oriented (API key), but illustrates a “one-shot” workflow:

- “Search the web and get full content from results” is provided as a single capability.
- Emphasizes handling “the hard stuff”: proxies, dynamic content, anti-bot, orchestration, batching.

Reference: https://github.com/mendableai/firecrawl

Implications for this project:

- A `pipeline` command is useful, but defaults matter: collapsing steps increases “one-shot success” but also cost, unpredictability, and policy surface area.
