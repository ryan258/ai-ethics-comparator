# Tech Stack — Hard Constraints

## Runtime
- Python 3.12+ managed with `uv`
- No Docker, k8s, or Terraform — bare-metal / uv-managed virtualenv only
- No React or build-step frontend — server-rendered Jinja2 + HTMX
- OS: POSIX assumed for atomic file creation (`os.link` / `open(..., 'x')` in `storage.py:151`)

## Dependency Source Of Truth (`pyproject.toml` + `uv.lock`)
- `fastapi` — ASGI framework, app-factory pattern
- `uvicorn` — ASGI server (`main.py:1066`)
- `pydantic` — validation layer (`lib/validation.py`), config (`lib/config.py`)
- `openai` — AsyncOpenAI client targeting OpenRouter (`lib/ai_service.py:71`)
- `weasyprint==61.2` — the ONLY HTML-to-PDF renderer. No fallback backend exists; if its native
  GTK/Pango libs are missing, PDF routes return 503 (see D10)
- `pydyf>=0.8,<0.11` — pinned below 0.11 because WeasyPrint 61.2 is incompatible with newer `pydyf` releases
- `jinja2` + `markupsafe` — template rendering + XSS-safe markup
- `markdown` — server-side markdown rendering in `safe_markdown` (`lib/view_models.py:16`)
- `python-dotenv` — `.env` loading at import time (`main.py:48`)
- `httpx` — explicit runtime dependency used by the OpenAI SDK and test client stack
- `python-multipart` — form data parsing for HTMX POST endpoints
- `python-pptx` — PowerPoint export for run data (`lib/export_pptx.py`)
- `pytest-asyncio` — async test support for `pytest` (`tests/conftest.py`)

## Environment Workflow
- `uv sync` installs the runtime and dev environment into `.venv`
- `uv run <command>` is the standard invocation path for app and tests
- `uv lock` updates the committed lockfile after dependency changes

## Data Files (repo root)
- `paradoxes.json` — scenario definitions
- `models.json` — available model list (source of truth, see priority below)
- `report_overrides.json` — per-paradox executive report prose
- `report_themes.json` — per-theme deployment guidance

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
- `uv run pytest` with `pythonpath = ["."]` (`pyproject.toml`)
- No coverage enforcement, no CI pipeline in repo
- Lint gate: `uvx ruff check --select F,E9 .` must be clean

## Config Source Priority (models)
1. `models.json` (file) → 2. `OPENROUTER_MODELS` (env) → 3. `AVAILABLE_MODELS_JSON` (env)

## Secrets — NEVER hardcode
- `OPENROUTER_API_KEY`, `APP_BASE_URL`, `OPENROUTER_BASE_URL` — required, validated at startup
- `ANALYST_MODEL`, `DEFAULT_MODEL` — optional, smart-defaults to first available model
