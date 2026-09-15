# Architectural Decisions — ETC (Easier to Change)

## D1: App Factory + AppServices Dataclass
- **Why ETC**: tests inject `config_override`; adding a service = one field + one init line
- **Rule**: NEVER create module-level service instances — all wiring in `lifespan()` (`main.py`)
- **Rule**: all service access goes through `_get_services(request)` (`main.py`)

## D2: Arsenal Module Pattern (`lib/`)
- **Why ETC**: each module is framework-agnostic and copy-paste portable
- **Rule**: `lib/` MUST NOT import `fastapi`, `Request`, `HTTPException`, or web/router layers. Rendering adapters may import Jinja2 and document renderers; core measurement and execution modules may not
- **Rule**: dependencies enter via constructor — no hidden coupling to `main.py`

## D3: Flat JSON Storage + Strict Run IDs
- **Why ETC**: zero migration tooling, human-readable, filesystem-safe, sortable
- **Trade-off**: no transactions, no indexing — atomic create only (`RunStorage.create_run()`, `storage.py`)
- **Rule**: all storage ops MUST be idempotent; run IDs match `^[A-Za-z0-9_-]+-\d{3,}$`
- **Migration**: `migrate_legacy_run_ids()` at startup — idempotent (`storage.py`)

## D4: N-Way Paradox Support (2-4 Options)
- **Why ETC**: `{{OPTIONS}}` placeholder — adding option 5 = config change only
- **Rule**: option IDs are sequential ints from 1; legacy `{{GROUP1}}`/`{{GROUP2}}` still works
- **Reference**: `render_options_template()` (`query_processor.py`)

## D5: HTMX Dual-Response Pattern
- **Why ETC**: same endpoint serves JSON or HTML partial based on `HX-Request` header
- **Rule**: partials in `templates/partials/`, full pages in `templates/`

## D6: AI Choice Inference Fallback Chain
- **Chain**: JSON → brace tokens → re-ask → heuristic NLP → AI classifier → undecided
- **Config**: `AI_CHOICE_INFERENCE_ENABLED` toggles the AI classifier layer
- **Reference**: `_infer_option_id_with_fallback()` (`query_processor.py`)

## D7: Analysis Prompt as External File
- **Why ETC**: `templates/analysis_prompt.txt` editable without code changes
- **Rule**: uses `string.Template.safe_substitute` — NOT f-strings or `.format()`

## D8: Composition Over Inheritance
- `ExperimentRunner` and `CounterfactualEngine` compose `QueryProcessor` + storage
- **Rule**: NEVER subclass service classes — compose via constructor injection

## D9: Scenario Prose as Data
- **Why ETC**: per-paradox executive prose lives in `report_overrides.json`; theme guidance in
  `report_themes.json`. Adding a scenario touches no Python.
- **Rule**: `lib/reporting.py` MUST NOT branch on a specific paradox ID
- **Where**: `lib/report_prose.py` owns the rationale-theme taxonomy and all override resolution;
  `lib/reporting.py` composes report context and never reads the JSON itself
- **Rule**: tests that assert on report prose MUST pass `ReportGenerator(overrides_path=...)` a
  fixture, never the shipped file — otherwise editing the paradox library breaks the test suite
- **Trade-off**: prose templates use `str.format`, so literal braces must be doubled

## D10: Browser-Native Reports
- Single-run and comparison reports are self-contained HTML documents built with Jinja2.
- Print styles and browser Print / Save as PDF handle pagination and PDF export. Download HTML saves a portable copy.
- No server PDF engine or native font/GTK dependencies. Do not add a second rendering backend.
- Opening a report uses saved evidence and does not generate paid narrative calls.
- Single-run documents use the executive brief adapter; comparisons use their own typed context.

## D11: Immutable Historical Execution Evidence
- New runs snapshot their scenario and persist rendered stimulus, canonical options, configuration and per-response order mappings.
- `resolve_paradox()` uses the saved snapshot first, then reconstructs legacy records from their saved prompt/options. It never replaces history with the live library.
- Display, analysis, reporting, resume and counterfactuals use that same resolver.
- Resume keeps the original scenario and stimulus. Applying a corrected scenario requires a new run; record `predecessorRunId` to identify the prior experiment.
- Counterfactuals record their source iteration and explicitly use a new fixed-order design based on that iteration. They do not claim a matched replay of a shuffled source run.
- Legacy runs without sufficient stored stimulus cannot be reconstructed for counterfactual execution. Missing historical evidence must not be guessed from current content.

## D12: Per-Iteration Option Permutation
- **Why**: LLMs favour first- and last-listed options. A permutation drawn once per RUN
  randomises that bias across runs but never averages it out within one — and the run is the
  unit the reported distribution is computed over.
- **Rule**: `shuffle_options` draws a fresh ordering for EVERY iteration (`run_iteration()`,
  `query_processor.py`), before the re-ask loop so a re-ask shows the same list.
- **Rule**: every response records the `optionOrder` mapping it was shown. A run that cannot
  be audited back to what the model actually saw is not reproducible.
- **Rule**: the run-level `prompt` stays the CANONICAL rendering. It is the record of the
  stimulus design, not of any one iteration.
- **Rule**: permute ONLY when the template can express the reordering —
  `template_supports_option_rendering()` checks for `{{OPTIONS}}` / `{{GROUP1}}`. A paradox
  reconstructed under D11 tier 3 carries the run's already-rendered prompt as its template, so
  re-rendering is a no-op: the model keeps seeing one fixed order while the mapping claims a
  shuffle, and every answer is then translated through a permutation that never happened.
  When the check fails the run degrades to a fixed order and records no `optionOrder` —
  a known-biased ordering is far better than silently mis-mapped data.
- **Default**: ON. `QueryRequest.shuffle_options` defaults `True` — unbiased is the path of
  least resistance, and the UI exposes it as a select (an unchecked checkbox is omitted by
  `json-enc`, which would silently fall back to the server default).
- **Legacy**: runs carrying a run-level `shuffleMapping` keep their single fixed ordering on
  resume; newer runs carry `shufflePerIteration` so resume preserves the mode.

## D13: Closed Vocabulary for Scenario Dimensions
- **Why ETC**: `category` is free-text provenance ("Aesop", "Authored: Epistemic Ethics") —
  47 of 197 scenarios had none and 77 distinct values covered 197 items, so nothing could be
  stratified by the ethical tension a scenario stresses.
- **Rule**: `dimensions` draws from `ETHICAL_DIMENSIONS` (`lib/paradoxes.py`) — deliberately
  the SAME seven labels the analyst prompt scores, so scenario design and fingerprint output
  are directly comparable.
- **Rule**: membership is validated at load. An unknown value raises — a typo must not
  silently create an eighth dimension nothing aggregates on.
- **Rule**: no dimension may cover >85% of the library. A saturated tag stratifies nothing;
  `tests/test_paradox_dimensions.py` enforces this.
- **Trade-off**: current assignments are a lexicon-based first pass
  (`scripts/backfill_dimensions.py`) and want human review. Re-running preserves hand edits.
