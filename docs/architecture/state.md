# State Management — Orthogonality Rules

## Principle: No module-level mutable state in `lib/`
- All services are instantiated in `create_app()` lifespan and attached to `app.state.services`
- `lib/` modules receive dependencies via constructor injection — NEVER via module globals
- Changing one module MUST NOT require changes in another unless at an explicit seam

## Stateful Objects and Their Owners

### `app.state.services: AppServices` (main.py)
- **Lifecycle**: created in lifespan `__aenter__`, set to `None` in `__aexit__`
- **Mutability**: frozen after creation — no runtime mutation of service instances
- **Access**: only via `_get_services(request)` (`main.py`) — returns 503 if `None`

### `RunStorage.results_root: Path` (storage.py)
- **Scope**: filesystem directory `results/`
- **Mutation**: `save_run()`, `create_run()`, `migrate_legacy_run_ids()`
- **Concurrency**: `create_run` prefers POSIX atomic `os.link`; filesystems without hard links fall back to `open('x')` reservation + replace
- **Invariant**: every file MUST match `<strict_run_id>.json` after migration

### `ExperimentStorage.experiments_root: Path` (storage.py)
- **Scope**: filesystem directory `experiments/`
- **Mutation**: `save_experiment()` only
- **Concurrency**: no atomic reservation — experiments are user-initiated, low contention

### `QueryProcessor.semaphore: asyncio.Semaphore` (query_processor.py)
- **Scope**: limits concurrent AI API calls within a single run
- **Invariant**: semaphore count = `config.AI_CONCURRENCY_LIMIT` (default 2)
- **Rule**: NEVER bypass the semaphore — all AI calls go through `run_iteration()`

### `_load_paradoxes_cached: lru_cache(1)` (paradoxes.py)
- **Scope**: caches parsed paradox definitions by file path
- **Mutation**: cache persists for process lifetime — call `clear_paradox_cache()` to invalidate
- **Risk**: if `paradoxes.json` changes at runtime, stale data will be served until restart
- `load_paradoxes()` returns a DEEP COPY — callers must never receive the cached dicts,
  or one caller mutating a paradox poisons every later request

### `RunStorage._metadata_cache: dict` (storage.py)
- **Scope**: per-instance `path -> (mtime_ns, size, metadata)` for `list_runs()`
- **Invalidation**: automatic — any write changes mtime/size; missing files are evicted
- **Bound**: bounded by `MAX_METADATA_CACHE_ENTRIES = 5000` with FIFO eviction to prevent unbounded memory growth
- **Why**: `list_runs()` runs on every page load and every fingerprint request

### `AIService.structured_output_support: dict` (ai_service.py)
- **Scope**: per-instance `model_name -> bool`, learned from provider rejections
- **Mutation**: set to `False` when a provider rejects `response_format`, then reused
- **Risk**: a provider that gains structured-output support mid-process stays downgraded until restart

### `read_prompt_template`: `lru_cache(8)` (prompt_templates.py)
- **Scope**: caches prompt-template file contents by path for the process lifetime
- **Why**: `analysis.py` and `report_writer.py` re-read their templates inside async request
  handlers on EVERY call, putting blocking disk I/O on the event loop
- **Risk**: editing a prompt template requires a restart — call `clear_prompt_template_cache()`
- **Rule**: `analysis.py` and `report_writer.py` both depend on this module and NOT on each
  other; the shared helper exists so neither imports the other

### `lib/report_prose` caches: `lru_cache(1)`
- `_load_report_overrides()` and `_load_theme_guidance()` cache their JSON for the process lifetime
- **Risk**: editing `report_overrides.json` / `report_themes.json` requires a restart

### `AppConfig` (config.py)
- **Lifecycle**: created once in lifespan, never mutated after `load()` returns
- **Rule**: treat as immutable — do NOT write back to env or modify fields after startup

## Known Import-Time Side Effect
