# How it works: request walkthrough and file guide

## Request flow
```
POST /link-analysis {"url": ...}
  main.py            Pydantic HttpUrl check (bad URL -> 422); calls analyze()
  analysis_service   cache hit? return it
  website_extractor  validate_public_url (SSRF) -> fetch homepage (manual redirects, size cap)
                     -> parse (strip noise, de-dupe) -> pick up to 2 about/services links, repeat
                     -> join and cap at ~9k chars
  llm_service        build schema from LLMResult -> call Ollama or Gemini -> validate with Pydantic
                     -> on error/invalid JSON try the other provider -> else AppError 503
  competitor_service fetch each suggested competitor homepage in parallel (title/meta/headings)
                     -> mark verified_from_website or leave ai_suggested
  analysis_service   build AnalysisResponse, cache it, return
```

## File guide
| File | Job |
|---|---|
| `app/main.py` | FastAPI app, the one endpoint, `AppError` -> JSON handler |
| `app/config.py` | Settings from env / `.env` (provider, models, key, caps, timeouts) |
| `app/schemas.py` | All Pydantic models. `LLMResult` is exactly what the LLM must return; `AnalysisResponse` is what the API returns |
| `app/utils/validators.py` | `AppError` and `validate_public_url` (the SSRF guard) |
| `app/services/website_extractor.py` | `fetch_html` (safe fetch), `parse` (clean page facts), `extract_site` (homepage + key pages) |
| `app/services/llm_service.py` | `generate()`: schema-constrained call, provider fallback, returns token/latency meta |
| `app/services/analysis_service.py` | The prompt, the cache and the orchestration |
| `app/services/competitor_service.py` | Homepage verification of suggested competitors |
| `scripts/benchmark.py` | Measures real tokens and latency per provider (feeds the README table) |
| `tests/test_link_analysis.py` | SSRF cases, parser, endpoint with mocked LLM |
| `docs/` | Screenshot and request/error logs for submission; these notes |

## How each spec requirement was met
- **Five sections:** fields in `LLMResult`, one per section, in the same shape as the spec's example response.
- **Real content only:** the prompt says to use only the website content; services have `inferred`; competitors have `source`.
- **Graceful failures:** `AppError` codes: 422 invalid, 400 private, 502 unreachable/blocked, 504 timeout, 503 LLM failure.
- **Keys protected:** env vars only; `.env` is in `.gitignore`.
- **Token economy:** see decisions 1–3, 5, 7 and 12.

## Useful commands
```bash
.venv\Scripts\python -m uvicorn app.main:app --host 0.0.0.0 --port 4000   # run (docs at /docs)
.venv\Scripts\python -m pytest -q                                          # tests
.venv\Scripts\python -m scripts.benchmark https://www.python.org           # measure models
```
Switch model/provider in `.env`: `LLM_PROVIDER`, `OLLAMA_MODEL`, `GEMINI_MODEL`.

## Known limits
- JavaScript-rendered sites give the LLM little to read.
- Competitor names are AI suggestions; "verified" only means the homepage loaded.
- DNS rebinding gap in the SSRF check (marked `shortcut:`).
- Accuracy has not been benchmarked; OpenAI and Anthropic were not run.
