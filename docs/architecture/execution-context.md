# Execution Context — Pragmatic Paranoia

## Startup: Fail Fast
- `validate_secrets()` → crash if `OPENROUTER_API_KEY`, `APP_BASE_URL`, or `OPENROUTER_BASE_URL` missing
- `AIService.__init__` and `ReportGenerator.__init__` validate their own preconditions
- **Rule**: missing required resource at startup = crash immediately — never serve partial state

## Route Error Mapping (`main.py`)
- `FileNotFoundError` → 404, `ValueError` → 400, `HTTPException` → re-raise, `Exception` → 500 (generic msg)
- **Rule**: NEVER expose internal error messages in 500 responses, error partials, or persisted
  run records. `query_errors.safe_error_message()` is the single mapper — `lastError` is served
  verbatim by `GET /api/runs/{run_id}`, so it takes the category, never `str(exc)`
- `analyze_run` returns error partial with `status_code=200` (HTMX compat); the partial shows a
  category message from `safe_error_message()` (`query_errors.py`), never `str(exc)`
- `/api/query` maps typed `lib/query_errors` exceptions, NOT error strings:
  `AuthenticationError` → 401, `QuotaError` → 402, `ModelNotFoundError` → 404,
  `QueryExecutionError` → 502

## AI Service Retry/Backoff (`lib/ai_service.py`)
- Retries on: HTTP 429 (rate limit), HTTP 5xx (server error), timeouts, `json.JSONDecodeError`,
  and connection/network errors
- NO retry on: 401, 402, 403, 404 — these are terminal
- NO retry on `InvalidModelOutputError` — unusable output is a parsing concern, not transport.
  The caller catches it explicitly in `run_iteration()` (`query_processor.py`) and spends the **re-ask** budget on a
  corrected prompt. It must never fall through to the provider-retry branch: that re-sends the same
  prompt and its exhaustion raises, failing the whole run instead of recording one undecided iteration.
- Backoff: `_backoff_delay()` (`ai_service.py`) — exponential with jitter so concurrent
  iterations do not retry in lockstep
- **Rule**: classify errors by exception type, not by substring-matching the message
- Max attempts: `config.AI_MAX_RETRIES` (default 5)
- **Rule**: callers MUST NOT add their own retry loops around `get_model_response`

## Iteration Bounds (`lib/query_processor.py`)
- There is NO wall-clock timeout on a run. Every loop is bounded by an explicit attempt budget:
  - re-asks for unusable output — including an empty provider response: `max_reasks_per_iteration`
    (default 2), enforced in `run_iteration()` (`query_processor.py`)
  - provider retries inside one iteration: `max_provider_retries_per_iteration` (default 3)
  - transport retries inside one call: `config.AI_MAX_RETRIES` (default 5)
- **Rule**: every retry loop MUST have a counter checked against a cap. An unbounded
  re-ask loop bills the provider forever.
- Exhausting the re-ask budget records a structured response with `optionId: None` and an
  `error` key; it counts as undecided in the summary
- `gather(..., return_exceptions=True)` (`query_processor.py`) so one terminal failure
  cannot orphan sibling iterations; the first exception is re-raised after all tasks settle
- **Rule**: a failed iteration produces a structured error dict or a raised exception — never silently dropped

## Run Progress Persistence
- `record_result()` persists after EACH accepted iteration, via `progress_callback`
- **Rule**: never batch persistence to the end of a run — a crash or cancel would discard
  every completed iteration and the resume path would have nothing to resume from
- The snapshot is taken while holding `state_lock` so concurrent iterations cannot
  persist a state that never existed

## Blocking I/O Discipline
- All filesystem access from async code goes through `run_in_executor` (`storage.py`) or a
  process-lifetime cache (`prompt_templates.py`, `paradoxes.py`)
- **Rule**: never call `open()` in an async function body. `F,E9` does not catch this; the
  gate selects `ASYNC` as well, which does

## Path Traversal Defense (`lib/storage.py`)
- `save_run()` (`storage.py`) validates the run ID BEFORE building a path — an
  unvalidated ID there is an arbitrary-file-write primitive
- `get_run()` resolves both flat and legacy paths, then asserts `is_relative_to(results_root)`
- `get_experiment()` performs same check against `experiments_root`
- Run ID regex validation happens BEFORE any filesystem access
- **Rule**: always validate the ID pattern THEN resolve+check the path — never trust input paths

## Input Validation Gates
- Model names: `^[a-z0-9\-_/:.]+$`, paradox IDs: `^[a-z0-9_-]+$`, run IDs: `^[A-Za-z0-9_-]+-\d{3,}$`
- Experiment IDs: `^exp_[0-9]+_[a-f0-9]+$`, option IDs: ints 1-4 sequential
- Iterations: Pydantic `ge=1, le=1000`, further capped by `config.MAX_ITERATIONS` in the route and
  re-checked when resuming a stored run (`main.py:_build_run_config_from_saved_run`)
- Numeric env limits are range-checked at startup by `_env_int(..., minimum=)`. `AI_CONCURRENCY_LIMIT`
  and `MAX_ITERATIONS` require >= 1: `Semaphore(0)` hangs every run with no error and no log line
- **Rule**: Pydantic validates shape, routes validate business limits

## Concurrency Safety
- `QueryProcessor.semaphore` limits AI calls (default 2); `ExperimentRunner` batches (max 4)
- `create_run` prefers POSIX atomic `os.link` with 20-attempt retry; filesystems without hard links fall back to `open('x')` reservation + replace
- `ExperimentRunner` reserves each condition's run file up front and streams progress into it,
  so a crash mid-matrix leaves resumable runs
- **Rule**: never set `AI_CONCURRENCY_LIMIT` above provider rate limits

## XSS Defense + Defensive Data Handling
- Web UI: `safe_markdown()` escapes HTML → renders markdown → strips `<a>`/`<img>` tags
- HTML reports use autoescaping in both Jinja environments. Model text must remain text, never executable markup. Report pages are self-contained and opening them performs no model calls.
