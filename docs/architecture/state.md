# State Management — Orthogonality Rules

## Principle: No module-level mutable state in `lib/`
- All services are instantiated in `create_app()` lifespan and attached to `app.state.services`
- `lib/` modules receive dependencies via constructor injection — NEVER via module globals
- Changing one module MUST NOT require changes in another unless at an explicit seam

## Stateful Objects and Their Owners

### `app.state.services: AppServices` (main.py:72-83)
- **Lifecycle**: created in lifespan `__aenter__`, set to `None` in `__aexit__`
- **Mutability**: frozen after creation — no runtime mutation of service instances
- **Access**: only via `_get_services(request)` (`main.py:102`) — returns 503 if `None`

### `RunStorage.results_root: Path` (storage.py:28)
- **Scope**: filesystem directory `results/`
- **Mutation**: `save_run()`, `create_run()`, `migrate_legacy_run_ids()`
- **Concurrency**: `create_run` prefers POSIX atomic `os.link`; filesystems without hard links fall back to `open('x')` reservation + replace
- **Invariant**: every file MUST match `<strict_run_id>.json` after migration

### `ExperimentStorage.experiments_root: Path` (storage.py:431)
- **Scope**: filesystem directory `experiments/`
- **Mutation**: `save_experiment()` only
- **Concurrency**: no atomic reservation — experiments are user-initiated, low contention

### `QueryProcessor.semaphore: asyncio.Semaphore` (query_processor.py:639)
- **Scope**: limits concurrent AI API calls within a single run
- **Invariant**: semaphore count = `config.AI_CONCURRENCY_LIMIT` (default 2)
- **Rule**: NEVER bypass the semaphore — all AI calls go through `run_iteration()`

### `_load_paradoxes_cached: lru_cache(1)` (paradoxes.py:121)
- **Scope**: caches parsed paradox definitions by file path
- **Mutation**: cache persists for process lifetime — call `clear_paradox_cache()` to invalidate
- **Risk**: if `paradoxes.json` changes at runtime, stale data will be served until restart
- `load_paradoxes()` returns a DEEP COPY — callers must never receive the cached dicts,
  or one caller mutating a paradox poisons every later request

### `RunStorage._metadata_cache: dict` (storage.py:33)
- **Scope**: per-instance `path -> (mtime_ns, size, metadata)` for `list_runs()`
- **Invalidation**: automatic — any write changes mtime/size; missing files are evicted
- **Bound**: bounded by `MAX_METADATA_CACHE_ENTRIES = 5000` with FIFO eviction to prevent unbounded memory growth
- **Why**: `list_runs()` runs on every page load and every fingerprint request

### `AIService.structured_output_support: dict` (ai_service.py:69)
- **Scope**: per-instance `model_name -> bool`, learned from provider rejections
- **Mutation**: set to `False` when a provider rejects `response_format`, then reused
- **Risk**: a provider that gains structured-output support mid-process stays downgraded until restart

### `lib/report_prose` caches: `lru_cache(1)`
- `_load_report_overrides()` and `_load_theme_guidance()` cache their JSON for the process lifetime
- **Risk**: editing `report_overrides.json` / `report_themes.json` requires a restart

### `AppConfig` (config.py:115)
- **Lifecycle**: created once in lifespan, never mutated after `load()` returns
- **Rule**: treat as immutable — do NOT write back to env or modify fields after startup

## Known Import-Time Side Effect
### `ensure_weasyprint_runtime_environment()` (weasyprint_runtime.py)
- Mutates `os.environ["DYLD_FALLBACK_LIBRARY_PATH"]` when `lib/reporting` is imported on macOS
- This is a DELIBERATE exception to the no-module-level-state rule: WeasyPrint's CFFI bindings
  cannot locate Homebrew's GTK/Pango without it, and the import must happen before `HTML` is bound
- It is idempotent and additive — it never removes existing entries
- **Rule**: do not add further import-time environment mutation; this one is the only sanctioned case

## Orthogonality Rules
- UI state (templates, view models) MUST NOT import or depend on storage internals
- Storage MUST NOT know about AI service or parsing logic
- Analysis MUST NOT know about routing or HTTP concerns
- `QueryProcessor` owns iteration orchestration — `AnalysisEngine` owns post-run insight generation
- `CounterfactualEngine` and `ExperimentRunner` compose `QueryProcessor` + `RunStorage` — they do NOT subclass or extend them
- `fingerprint.py` and `stats.py` are pure read-only consumers of storage data
- `validation.py` is shape-validation only — it MUST NOT import `query_processor`
- Adding a new `lib/` module MUST NOT require modifying existing `lib/` modules
