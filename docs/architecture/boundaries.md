# Boundaries — Design by Contract

## Seam 1: HTTP Layer ↔ Business Logic
- **Contract**: `main.py` routes are THIN — validate input, delegate to `lib/`, format response
- Routes MUST call `_get_services(request)` to access initialized services — never import lib singletons
- Pydantic models in `lib/validation.py` are the SOLE input gate for `POST` JSON bodies
- `lib/validation.py` validates SHAPE ONLY — it MUST NOT import `lib/query_processor` or build
  business objects. `ConditionConfig` → `RunConfig` conversion lives in
  `experiment_runner.condition_to_run_config()`
- Query-parameter endpoints (`/api/compare/pdf`) validate inline in the route
- `QueryRequest` → `RunConfig` conversion happens in the route, not in `lib/`
- HTMX requests (`HX-Request` header) return template partials; JSON clients get raw dicts
- Routes MUST NOT contain business logic, aggregation, or AI calls directly

## Seam 2: Business Logic ↔ External AI API
- **Contract**: `AIService.get_model_response()` is the ONLY function that calls OpenRouter
- Inputs: `(model_name: str, prompt: str, system_prompt: str, params: dict)`
- Outputs: `Tuple[str, Dict[str, int]]` — `(response_text, usage_dict)` — always
- AIService handles retries internally — callers MUST NOT implement retry logic
- Error contract: raises a typed exception from `lib/query_errors`. Anything deriving from
  `RetryableQueryError` may be retried by the caller; everything else is terminal.
  Callers MUST branch on the exception type, never on the message text.
- All `lib/` modules receive `AIService` via constructor injection — never instantiate it

## Seam 3: Business Logic ↔ Storage
- **Contract**: `RunStorage` and `ExperimentStorage` are the ONLY filesystem writers
- `RunStorage` path: `results/<run_id>.json` — strict pattern `^[A-Za-z0-9_-]+-\d{3}$`
- `ExperimentStorage` path: `experiments/<exp_id>.json` — pattern `^[A-Za-z0-9_-]+$`
- All storage methods are `async` — blocking I/O wrapped in `run_in_executor`
- `create_run()` prefers POSIX atomic `os.link`; if hard links are unavailable it falls back to `open('x')` reservation + replace
- `get_run()` validates path traversal before reading — callers MUST NOT build paths

## Seam 4: Query Processor ↔ Response Parsing
- **Contract**: `parse_trolley_response(text, option_count)` returns `{decisionToken, optionId, explanation}`
- `optionId` is `int | None` — never a string — callers MUST handle `None` (undecided)
- Fallback chain: JSON parse → brace-token regex → heuristic NLP → AI classifier → `None`
- Re-ask loop: hard-capped at `max_reasks_per_iteration` (enforced in `run_iteration()`, `query_processor.py`).
  On exhaustion the iteration is recorded as undecided with an `error` key.
- JSON recovery is shared: `lib/json_extract.extract_json_object()` is the single
  implementation — do NOT add a per-module copy
- `render_options_template()` always appends `_strict_single_choice_contract` to prompts

## Seam 5: Analysis Engine ↔ Insight Schema
- **Contract**: `generate_insight()` returns `{timestamp, analystModel, content}`
- `content` is `dict` — either structured JSON or `{"legacy_text": raw_string}`
- Required structured keys: `dominant_framework`, `moral_complexes`, `justifications`, `consistency`, `key_insights`
- Missing keys → automatic fallback to `{"legacy_text": ...}` — templates handle both

## Seam 5b: Report Context ↔ Scenario Prose
- **Contract**: scenario-specific report prose lives in `report_overrides.json`, keyed by paradox ID
- Theme deployment guidance lives in `report_themes.json`, keyed by rationale-theme label
- **Rule**: NEVER add `if paradox_id == "..."` branches to `lib/reporting.py` — adding a
  scenario is a data change
- Resolution lives in `lib/report_prose.py`, not `lib/reporting.py`. Both file paths are
  parameters (`ReportGenerator(overrides_path=..., themes_path=...)`) so the module stays
  portable — do NOT reach for repo layout from inside a resolver
- Placeholders available to override templates: `response_count`, `temperature_value`,
  `reliability_label`, `option_<1-4>_count`, `option_<1-4>_share`, `cluster_count`, `cluster_share`

## Seam 5c: Stored Run ↔ Paradox Definition
- **Contract**: a run record is self-describing. `paradoxTitle` and a full `paradox` deep copy
  are written by `initialize_run_data()` and are the run's own property, not a live lookup
- **Rule**: routes MUST resolve a paradox as live library → `run_data["paradox"]` →
  reconstruction from `prompt`/`options`. Returning 404 because tier 1 missed is a regression
  (see D11)
- **Rule**: report builders receive a resolved paradox dict — they MUST NOT read
  `paradoxes.json` themselves

## Seam 6: View Models ↔ Templates
- **Contract**: `RunViewModel.build(run_data, paradox)` → flat dict with pre-rendered HTML
- Templates MUST NOT access raw run data — the view model is the only surface
- `safe_markdown()` escapes HTML BEFORE rendering markdown — `|safe` is NEVER used on user input
- PDF report templates rely on `autoescape=True` plus a blocking WeasyPrint `url_fetcher`
- View models strip `<a>` and `<img>` tags post-render for XSS hardening
