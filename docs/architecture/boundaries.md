# Boundaries — Design by Contract

## Seam 1: HTTP Layer ↔ Business Logic
- **Contract**: `main.py` routes are THIN — validate input, delegate to `lib/`, format response
- Routes MUST call `_get_services(request)` to access initialized services — never import lib singletons
- Pydantic models in `lib/validation.py` are the SOLE input gate for `POST` endpoints
- `QueryRequest` → `RunConfig` conversion happens in the route, not in `lib/`
- HTMX requests (`HX-Request` header) return template partials; JSON clients get raw dicts
- Routes MUST NOT contain business logic, aggregation, or AI calls directly

## Seam 2: Business Logic ↔ External AI API
- **Contract**: `AIService.get_model_response()` is the ONLY function that calls OpenRouter
- Inputs: `(model_name: str, prompt: str, system_prompt: str, params: dict)`
- Outputs: `Tuple[str, Dict[str, int]]` — `(response_text, usage_dict)` — always
- AIService handles retries internally — callers MUST NOT implement retry logic
- Error contract: raises `Exception` with `[status_code]` prefix for HTTP errors
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
- Re-ask loop: up to `max_reasks_per_iteration` retries before fallback inference
- `render_options_template()` always appends `_strict_single_choice_contract` to prompts

## Seam 5: Analysis Engine ↔ Insight Schema
- **Contract**: `generate_insight()` returns `{timestamp, analystModel, content}`
- `content` is `dict` — either structured JSON or `{"legacy_text": raw_string}`
- Required structured keys: `dominant_framework`, `moral_complexes`, `justifications`, `consistency`, `key_insights`
- Missing keys → automatic fallback to `{"legacy_text": ...}` — templates handle both

## Seam 6: View Models ↔ Templates
- **Contract**: `RunViewModel.build(run_data, paradox)` → flat dict with pre-rendered HTML
- Templates MUST NOT access raw run data except through `_raw_run` escape hatch
- `safe_markdown()` escapes HTML BEFORE rendering markdown — `|safe` is NEVER used on user input
- View models strip `<a>` and `<img>` tags post-render for XSS hardening
