# Architectural Decisions — ETC (Easier to Change)

## D1: App Factory + AppServices Dataclass
- **Why ETC**: tests inject `config_override`; adding a service = one field + one init line
- **Rule**: NEVER create module-level service instances — all wiring in `lifespan()` (`main.py:99`)
- **Rule**: all service access goes through `_get_services(request)` (`main.py:76`)

## D2: Arsenal Module Pattern (`lib/`)
- **Why ETC**: each module is framework-agnostic and copy-paste portable
- **Rule**: `lib/` MUST NOT import `fastapi`, `Request`, `HTTPException`, or template engines
- **Rule**: dependencies enter via constructor — no hidden coupling to `main.py`

## D3: Flat JSON Storage + Strict Run IDs
- **Why ETC**: zero migration tooling, human-readable, filesystem-safe, sortable
- **Trade-off**: no transactions, no indexing — atomic create only (`storage.py:78`)
- **Rule**: all storage ops MUST be idempotent; run IDs match `^[A-Za-z0-9_-]+-\d{3}$`
- **Migration**: `migrate_legacy_run_ids()` at startup — idempotent (`storage.py:88`)

## D4: N-Way Paradox Support (2-4 Options)
- **Why ETC**: `{{OPTIONS}}` placeholder — adding option 5 = config change only
- **Rule**: option IDs are sequential ints from 1; legacy `{{GROUP1}}`/`{{GROUP2}}` still works
- **Reference**: `query_processor.py:209-254`

## D5: HTMX Dual-Response Pattern
- **Why ETC**: same endpoint serves JSON or HTML partial based on `HX-Request` header
- **Rule**: partials in `templates/partials/`, full pages in `templates/`

## D6: AI Choice Inference Fallback Chain
- **Chain**: JSON → brace tokens → re-ask → heuristic NLP → AI classifier → undecided
- **Config**: `AI_CHOICE_INFERENCE_ENABLED` toggles the AI classifier layer
- **Reference**: `query_processor.py:437-463`

## D7: Analysis Prompt as External File
- **Why ETC**: `templates/analysis_prompt.txt` editable without code changes
- **Rule**: uses `string.Template.safe_substitute` — NOT f-strings or `.format()`

## D8: Composition Over Inheritance
- `ExperimentRunner` and `CounterfactualEngine` compose `QueryProcessor` + storage
- **Rule**: NEVER subclass service classes — compose via constructor injection
