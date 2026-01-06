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

## Practical implications for tooling

Observed failure drivers that should influence toolkit design:

- **Search ambiguity → long-horizon failure**: agents waste steps browsing irrelevant results; need query refinement, domain scoping, and “result usefulness” signals.
- **JS-rendered pages**: plain HTTP fetch returns empty shells; need a browser-render fallback that can run locally and optionally reuse the user’s profile.
- **Anti-bot/403/CAPTCHA**: “bypass” is often TOS-hostile; instead the toolkit should (a) improve polite fetch defaults, (b) detect blocks, (c) fall back to interactive/local browser when appropriate.
- **Extraction quality variance**: Readability-style extraction is often better for articles; docs sites and reference pages may need different heuristics.
- **Prompt/task injection**: tool outputs are untrusted input; agents need clear separation between instructions vs content, plus safe defaults (allowlists, confirmation gates).
