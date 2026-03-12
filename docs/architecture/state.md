# State Management — Orthogonality Rules

## Principle: No module-level mutable state in `lib/`
- All services are instantiated in `create_app()` lifespan and attached to `app.state.services`
- `lib/` modules receive dependencies via constructor injection — NEVER via module globals
- Changing one module MUST NOT require changes in another unless at an explicit seam

## Stateful Objects and Their Owners

### `app.state.services: AppServices` (main.py:52-62)
- **Lifecycle**: created in lifespan `__aenter__`, set to `None` in `__aexit__`
- **Mutability**: frozen after creation — no runtime mutation of service instances
- **Access**: only via `_get_services(request)` — returns 503 if `None`

### `RunStorage.results_root: Path` (storage.py:23)
- **Scope**: filesystem directory `results/`
- **Mutation**: `save_run()`, `create_run()`, `migrate_legacy_run_ids()`
- **Concurrency**: `create_run` prefers POSIX atomic `os.link`; filesystems without hard links fall back to `open('x')` reservation + replace
- **Invariant**: every file MUST match `<strict_run_id>.json` after migration

### `ExperimentStorage.experiments_root: Path` (storage.py:335)
- **Scope**: filesystem directory `experiments/`
- **Mutation**: `save_experiment()` only
- **Concurrency**: no atomic reservation — experiments are user-initiated, low contention

### `QueryProcessor.semaphore: asyncio.Semaphore` (query_processor.py:433)
- **Scope**: limits concurrent AI API calls within a single run
- **Invariant**: semaphore count = `config.AI_CONCURRENCY_LIMIT` (default 2)
- **Rule**: NEVER bypass the semaphore — all AI calls go through `run_iteration()`

### `_load_paradoxes_cached: lru_cache(1)` (paradoxes.py:120)
- **Scope**: caches parsed paradox definitions by file path
- **Mutation**: cache persists for process lifetime — call `clear_paradox_cache()` to invalidate
- **Risk**: if `paradoxes.json` changes at runtime, stale data will be served until restart

### `AppConfig` (config.py:82)
- **Lifecycle**: created once in lifespan, never mutated after `load()` returns
- **Rule**: treat as immutable — do NOT write back to env or modify fields after startup

## Orthogonality Rules
- UI state (templates, view models) MUST NOT import or depend on storage internals
- Storage MUST NOT know about AI service or parsing logic
- Analysis MUST NOT know about routing or HTTP concerns
- `QueryProcessor` owns iteration orchestration — `AnalysisEngine` owns post-run insight generation
- `CounterfactualEngine` and `ExperimentRunner` compose `QueryProcessor` + `RunStorage` — they do NOT subclass or extend them
- `fingerprint.py` and `stats.py` are pure read-only consumers of storage data
- Adding a new `lib/` module MUST NOT require modifying existing `lib/` modules
