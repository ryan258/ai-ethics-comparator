# Architectural Decisions — ETC (Easier to Change)

## D1: App Factory + AppServices Dataclass
- **Why ETC**: tests inject `config_override`; adding a service = one field + one init line
- **Rule**: NEVER create module-level service instances — all wiring in `lifespan()` (`main.py:293`)
- **Rule**: all service access goes through `_get_services(request)` (`main.py:102`)

## D2: Arsenal Module Pattern (`lib/`)
- **Why ETC**: each module is framework-agnostic and copy-paste portable
- **Rule**: `lib/` MUST NOT import `fastapi`, `Request`, `HTTPException`, or template engines
- **Rule**: dependencies enter via constructor — no hidden coupling to `main.py`

## D3: Flat JSON Storage + Strict Run IDs
- **Why ETC**: zero migration tooling, human-readable, filesystem-safe, sortable
- **Trade-off**: no transactions, no indexing — atomic create only (`storage.py:151`)
- **Rule**: all storage ops MUST be idempotent; run IDs match `^[A-Za-z0-9_-]+-\d{3}$`
- **Migration**: `migrate_legacy_run_ids()` at startup — idempotent (`storage.py:78`)

## D4: N-Way Paradox Support (2-4 Options)
- **Why ETC**: `{{OPTIONS}}` placeholder — adding option 5 = config change only
- **Rule**: option IDs are sequential ints from 1; legacy `{{GROUP1}}`/`{{GROUP2}}` still works
- **Reference**: `render_options_template()` (`query_processor.py:427`)

## D5: HTMX Dual-Response Pattern
- **Why ETC**: same endpoint serves JSON or HTML partial based on `HX-Request` header
- **Rule**: partials in `templates/partials/`, full pages in `templates/`

## D6: AI Choice Inference Fallback Chain
- **Chain**: JSON → brace tokens → re-ask → heuristic NLP → AI classifier → undecided
- **Config**: `AI_CHOICE_INFERENCE_ENABLED` toggles the AI classifier layer
- **Reference**: `_infer_option_id_with_fallback()` (`query_processor.py:787`)

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
