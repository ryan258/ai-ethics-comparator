# Tech Stack — Hard Constraints

## Runtime
- Python 3.11+ (uses `datetime.fromisoformat` with tz, `Path.is_relative_to`, `type[X] | Y` unions)
- No Docker, k8s, or Terraform — bare-metal / venv only
- No React or build-step frontend — server-rendered Jinja2 + HTMX
- OS: POSIX assumed for atomic file creation (`open(..., 'x')` in `storage.py:78`)

## Pinned Dependencies (`requirements.txt`)
- `fastapi` — ASGI framework, app-factory pattern
- `uvicorn` — ASGI server (`main.py:654`)
- `pydantic` — validation layer (`lib/validation.py`), config (`lib/config.py`)
- `openai` — AsyncOpenAI client targeting OpenRouter (`lib/ai_service.py:36`)
- `weasyprint==61.2` — preferred HTML-to-PDF renderer when native GTK/Pango libs are available
- `pydyf==0.12.1` — native PDF fallback renderer used when WeasyPrint cannot load system libraries
- `jinja2` + `markupsafe` — template rendering + XSS-safe markup
- `markdown` — server-side markdown rendering in `safe_markdown` (`lib/view_models.py:16`)
- `python-dotenv` — `.env` loading at import time (`main.py:39`)
- `httpx` — transitive (used by FastAPI test client and openai SDK)
- `python-multipart` — form data parsing for HTMX POST endpoints

## Storage
- Flat JSON files in `results/` — one file per run (`<run_id>.json`)
- Experiment files in `experiments/` — one file per experiment
- No database, no ORM, no migrations beyond `migrate_legacy_run_ids`

## UI Palette (Candlelight) — use ONLY these for user-facing colors
- `#121212` (bg), `#EBD2BE` (text), `#A6ACCD` (accent), `#98C379` (success), `#E06C75` (error)

## External APIs
- Single external dependency: OpenRouter (`OPENROUTER_BASE_URL`)
- Uses OpenAI-compatible chat completions API via `AsyncOpenAI`
- All model IDs are OpenRouter-format: `provider/model-name`

## Test Runner
- `pytest` with `pythonpath = ["."]` (`pyproject.toml`)
- No coverage enforcement, no CI pipeline in repo

## Config Source Priority (models)
1. `models.json` (file) → 2. `OPENROUTER_MODELS` (env) → 3. `AVAILABLE_MODELS_JSON` (env)

## Secrets — NEVER hardcode
- `OPENROUTER_API_KEY`, `APP_BASE_URL`, `OPENROUTER_BASE_URL` — required, validated at startup
- `ANALYST_MODEL`, `DEFAULT_MODEL` — optional, smart-defaults to first available model
