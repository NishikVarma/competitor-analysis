# Decisions: what we chose and why

| # | Decision | Why | Trade-off / upgrade path |
|---|---|---|---|
| 1 | **One LLM call for all five sections** | The page content is sent once, so input tokens are paid once; one round trip is also faster than five | One big output (~1.6–2.3k tokens) means one failure retries everything |
| 2 | **Send cleaned text, not raw HTML** | Raw HTML is mostly scripts, styles and markup, often ~10x more tokens. We keep title, meta description, headings and de-duplicated text, capped at ~9k chars (`max_content_chars`) | A JavaScript-only site yields little text; a headless browser would fix that but is far heavier |
| 3 | **Homepage + at most 2 key pages** (about/services/product links, same host) | The services section needs more than the homepage, but more pages means more tokens | Raise `max_pages` for richer sites |
| 4 | **Ollama primary, Gemini 2.5 Flash fallback** | You chose it: Ollama is free and local; Gemini is cheap (~$0.005/analysis measured) and ~2.5x faster (21 s vs 55 s measured). Falls back automatically if one fails or returns invalid JSON | Local Mistral 7B is slow; set `LLM_PROVIDER=gemini` for speed |
| 5 | **Schema-constrained JSON** (Ollama `format`, Gemini `responseJsonSchema`) generated from the Pydantic model | Reliable structure without retries or long "return JSON like this" prompts; field descriptions live in the schema, not the prompt | Schemas must be inlined (`$ref` removed) for backend compatibility: see `_flat_schema` |
| 6 | **Pydantic validates the LLM output** (5 queries, 5 services, >=3 competitors) | The spec requires validated, structured JSON; bad output triggers the fallback provider, then HTTP 503 | |
| 7 | **Competitors: LLM suggests, we verify with plain HTTP** | LLMs can't browse, so names are AI suggestions. Fetching each homepage's title/meta/headings (~300 tokens, no extra LLM call) lets us label `verified_from_website` vs `ai_suggested`, which the spec asks for | Verification only proves the site exists and shows its title, not that it's a true competitor. A search API (Tavily/Serper) would be a stronger upgrade |
| 8 | **No search volumes anywhere** | The spec forbids inventing them; the schema has no such field, so the model can't make them up | |
| 9 | **Services carry `inferred: bool`** | The spec wants services taken from real content and inferred ones labelled | Depends on the LLM being honest about the flag |
| 10 | **SSRF guard: resolve DNS, require every IP to be public (`is_global`), follow redirects manually and re-check each hop** | A user-supplied URL must not reach localhost, cloud metadata (169.254.x), or private networks. Auto-redirects would bypass a one-time check | DNS rebinding window remains (we resolve, then httpx resolves again); fix by pinning the IP. Marked `shortcut:` in `validators.py` |
| 11 | **2 MB body cap, 10 s timeout** | Stops huge or slow responses from tying up the server | |
| 12 | **In-memory per-URL cache, 1 h TTL** | Repeat requests cost zero tokens | Lost on restart, single process only; use Redis if scaled |
| 13 | **Custom `AppError(status, message)` mapped to JSON `{"success": false, "error": ...}`** | One place for 400/422/502/503/504 responses | |
| 14 | **Competitor/benchmark honesty in README** | The spec says to separate measured results from estimates. Ollama and Gemini rows are measured; OpenAI/Anthropic prices come from aggregators and speeds are estimates; no accuracy benchmark was run | Add a key and rerun `scripts/benchmark.py` to measure more |
| 15 | **Screenshots via headless Edge + text logs** | The spec allows "screenshots or logs"; the browser tool can't save images to disk, so headless Edge captured `/docs` | The Swagger "Try it out" response isn't shown as an image; the curl logs cover it |
| 16 | **Commit locally only** | Your instruction: never push | |

## Things deliberately not built
- No frontend: the spec only requires the API and `/docs`.
- No database, auth, rate limiting or queue: not in the spec.
- No headless browser / JS rendering: heavy and not required.
- No separate model per task: a single small model for one call keeps it simple.
