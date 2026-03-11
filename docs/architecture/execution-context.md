# Execution Context — Pragmatic Paranoia

## Startup: Fail Fast
- `validate_secrets()` → crash if `OPENROUTER_API_KEY`, `APP_BASE_URL`, or `OPENROUTER_BASE_URL` missing
- `AIService.__init__` and `ReportGenerator.__init__` validate their own preconditions
- **Rule**: missing required resource at startup = crash immediately — never serve partial state

## Route Error Mapping (`main.py`)
- `FileNotFoundError` → 404, `ValueError` → 400, `HTTPException` → re-raise, `Exception` → 500 (generic msg)
- **Rule**: NEVER expose internal error messages in 500 responses
- `analyze_run` returns error partial with `status_code=200` (HTMX compat)
- `/api/query` sniffs error strings: `"401"` → 401, `"429"` → 429, `"quota"` → 402

## AI Service Retry/Backoff (`lib/ai_service.py`)
- Retries on: HTTP 429 (rate limit), HTTP 5xx (server error), network/JSON errors
- NO retry on: 401, 402, 403, 404 — these are terminal
- Backoff: `retry_delay * (2 ** retry_count)` — exponential
- Max attempts: `config.AI_MAX_RETRIES` (default 5)
- **Rule**: callers MUST NOT add their own retry loops around `get_model_response`

## Query Execution Timeout (`lib/query_processor.py:614`)
- `asyncio.wait_for(..., timeout=300)` wraps the entire iteration batch
- On timeout: raises `asyncio.TimeoutError` with descriptive message
- Individual iteration failures from `gather(return_exceptions=True)` are captured as error responses
- **Rule**: a failed iteration produces a structured error dict — never silently dropped

## Path Traversal Defense (`lib/storage.py`)
- `get_run()` resolves both flat and legacy paths, then asserts `is_relative_to(results_root)`
- `get_experiment()` performs same check against `experiments_root`
- Run ID regex validation happens BEFORE any filesystem access
- **Rule**: always validate the ID pattern THEN resolve+check the path — never trust input paths

## Input Validation Gates
- Model names: `^[a-z0-9\-_/:.]+$`, paradox IDs: `^[a-z0-9_-]+$`, run IDs: `^[A-Za-z0-9_-]+-\d{3}$`
- Experiment IDs: `^exp_[0-9]+_[a-f0-9]+$`, option IDs: ints 1-4 sequential
- Iterations: Pydantic `ge=1, le=1000`, further capped by `config.MAX_ITERATIONS` in route
- **Rule**: Pydantic validates shape, routes validate business limits

## Concurrency Safety
- `QueryProcessor.semaphore` limits AI calls (default 2); `ExperimentRunner` batches (max 4)
- `generate_run_id` uses POSIX atomic `open('x')` with 20-attempt retry
- **Rule**: never set `AI_CONCURRENCY_LIMIT` above provider rate limits

## XSS Defense + Defensive Data Handling
- `safe_markdown()`: escape HTML → render markdown → strip `<a>`/`<img>` tags
- **Rule**: NEVER use `|safe` on user/model content; always pass through `safe_markdown` or `html.escape`
- AI response extraction: 7-layer fallback; insight parsing: brace-match → fence-strip → validate → legacy
- **Rule**: never assume AI output matches requested schema — always degrade gracefully
