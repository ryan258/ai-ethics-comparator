# Architectural Decisions — ETC (Easier to Change)

## D1: App Factory + AppServices Dataclass
- **Why ETC**: tests inject `config_override`; adding a service = one field + one init line
- **Rule**: NEVER create module-level service instances — all wiring in `lifespan()` (`main.py`)
- **Rule**: all service access goes through `_get_services(request)` (`main.py`)

## D2: Arsenal Module Pattern (`lib/`)
- **Why ETC**: each module is framework-agnostic and copy-paste portable
- **Rule**: `lib/` MUST NOT import `fastapi`, `Request`, `HTTPException`, or template engines
- **Rule**: dependencies enter via constructor — no hidden coupling to `main.py`

## D3: Flat JSON Storage + Strict Run IDs
- **Why ETC**: zero migration tooling, human-readable, filesystem-safe, sortable
- **Trade-off**: no transactions, no indexing — atomic create only (`RunStorage.create_run()`, `storage.py`)
- **Rule**: all storage ops MUST be idempotent; run IDs match `^[A-Za-z0-9_-]+-\d{3}$`
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

## D10: No Native PDF Fallback
- HTML-to-PDF is WeasyPrint only. When its native GTK/Pango libraries are unavailable the
  route returns 503, it does not degrade to a second renderer.
- **Why**: the previous pure-Python fallback was 1445 untested lines reimplementing PDF layout
- **Rule**: do not reintroduce a second rendering backend; fix the WeasyPrint install instead
- **Rule**: the same reasoning governs report LAYOUT. Single-run PDFs render as a strategic
  brief and nothing else; a failure raises and the route maps it to 503. The former
  `pdf_report.html` (790 lines) was reachable only through an `except Exception`, so a broken
  renderer silently handed the user a structurally different document — the exact failure mode
  this decision exists to prevent. Deleted.

## D11: Run-Level Scenario Snapshot + Three-Tier Paradox Resolution
- **Why ETC**: a run's `paradoxId` is a foreign key into `paradoxes.json`, a file that is edited
  freely. Before this, editing or replacing the scenario library orphaned every stored run:
  report routes returned 404 and the UI rendered an empty paradox.
- **Rule**: `initialize_run_data()` snapshots the scenario into the run record — `paradoxTitle`
  plus a deep copy of the whole definition under `paradox` (`query_processor.py`). A run is
  self-describing and never depends on the live library staying unchanged.
- **Rule**: every consumer resolves the paradox via `resolve_paradox(run_data, paradoxes)`
  (`lib/paradoxes.py`) — the SINGLE implementation of all three tiers:
  1. live library — `get_paradox_by_id(paradoxes, run_data["paradoxId"])`
  2. the run's own snapshot — `run_data["paradox"]`
  3. reconstruction from the run's `prompt`, `options`, and `paradoxTitle`
- **Rule**: do NOT hand-roll the tiers at a call site. They were duplicated inline in two PDF
  routes and skipped entirely in three others (export, counterfactual fragment, home-page run
  list), which silently produced null-paradox exports and "Unknown Paradox" cards. An invariant
  enforced by convention is not enforced — `tests/test_paradox_resolution.py` now pins it by
  deleting a scenario from the library and asserting every surface still names it.
- **Why tier 3**: runs created before D11 carry no snapshot. Tier 3 rebuilds a usable paradox
  from what every run has always stored, so legacy records stay exportable.
- **Where**: `resolve_paradox()` (`lib/paradoxes.py`). Callers: both PDF routes, the export
  route, the counterfactual fragment, the index route, `_resume_run_by_id`, and
  `fetch_recent_run_view_models()`. Every consumer that starts from a stored RUN uses it.
- **Not** a caller: `get_paradox_by_id()` is still correct where the input is a paradox ID
  rather than a run — the paradox-details fragment and new-run creation should 404 on an
  unknown ID rather than invent a scenario.
- **Rule**: this also makes a run reproducible. The exact stimulus text is part of the record,
  so a result can be audited after the library moves on.
- **Trade-off**: run files are larger, and a snapshot can drift from a corrected live definition.
  Tier 1 wins precisely so corrections take effect for scenarios that still exist.

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
