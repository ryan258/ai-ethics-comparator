# AI Ethics Comparator

A local-first research tool for measuring how LLMs respond to trolley-style ethical dilemmas across repeated iterations. Built with FastAPI + HTMX.

## What It Does

Run any OpenRouter model against ethical paradoxes (2-4 options each), repeat across many iterations, then analyze the patterns: which moral frameworks dominate, how consistent is the model, and what happens when you inject counterfactual evidence.

## Stack

- **Backend:** FastAPI (app-factory pattern)
- **Templates:** Jinja2 + HTMX (no build step)
- **AI provider:** OpenRouter via AsyncOpenAI
- **Reports:** WeasyPrint PDF, native PDF fallback, PowerPoint export
- **Storage:** flat JSON files (no database)
- **Python:** 3.11+

## Quick Start

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Create `.env` (or copy `.example.env`):

```env
OPENROUTER_API_KEY=sk-or-your-key-here
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
APP_BASE_URL=http://localhost:8000
```

Optional settings:

```env
# DEFAULT_MODEL and ANALYST_MODEL are derived from models.json when unset
DEFAULT_MODEL=provider/model-name
ANALYST_MODEL=provider/model-name
REPORT_PDF_THEME=dark
MAX_ITERATIONS=50
AI_CONCURRENCY_LIMIT=2
AI_MAX_RETRIES=5
AI_RETRY_DELAY=2
AI_CHOICE_INFERENCE_ENABLED=true
```

Run:

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Open [http://localhost:8000](http://localhost:8000).

## Features

### Runs
Execute a model against a paradox for N iterations. Each iteration captures the model's decision token, explanation, and raw output. Results are stored as `results/<run_id>.json` with aggregate statistics.

### Analysis
LLM-powered insight generation identifies moral complexes, decision quality, paradox severity, and the model's ethical strategy. Results are cached in the run file. Analyst model is configurable per request.

### Counterfactuals
Take an existing run and inject evidence ("what would change your mind?") to produce a new run. Preserves option shuffle order for comparison validity.

### Experiments
Define a matrix of paradoxes and conditions (different models, parameters, system prompts), then execute them in parallel. Track status, errors, and per-condition results.

### Fingerprinting
Aggregate all runs for a given model to build an ethics profile: moral complex frequencies with Wilson confidence intervals across all paradoxes tested.

### Reporting
- **PDF** — single-run reports with distribution charts, insight analysis, and AI narrative
- **Comparison PDF** — 2-4 runs side-by-side on the same paradox
- **JSON export** — structured data (distribution, responses, metadata)
- **PowerPoint** — slide deck with title, distribution, and analysis

## API Surface

### Pages
| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Main UI (run history, paradox selector, model picker) |
| GET | `/experiments` | Experiment laboratory |

### Runs
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/query` | Execute a new run |
| GET | `/api/runs` | List run metadata |
| GET | `/api/runs/{run_id}` | Fetch complete run data |
| POST | `/api/runs/{run_id}/counterfactual` | Generate counterfactual run |

### Analysis & Insights
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/runs/{run_id}/analyze` | Generate/regenerate ethical insights (optional analyst model override) |
| POST | `/api/insight` | Generate insight (non-persistent) |

### Paradoxes
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/paradoxes` | List all paradox definitions |
| GET | `/api/fragments/paradox-details` | HTMX fragment for paradox detail |

### Experiments
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/experiments` | Create experiment |
| GET | `/api/experiments` | List experiments |
| GET | `/api/experiments/{exp_id}` | Fetch experiment |
| POST | `/api/experiments/{exp_id}/execute` | Execute experiment |

### Fingerprinting
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/models/{model_id}/fingerprint` | Model ethics profile (JSON) |
| GET | `/fragments/fingerprint` | Fingerprint HTMX fragment |

### Export
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/runs/{run_id}/pdf` | PDF report (single run) |
| GET | `/api/compare/pdf` | Comparison PDF (2-4 runs) |
| GET | `/api/runs/{run_id}/export` | JSON or PPTX export (`?format=json\|pptx`) |

### System
| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check (version, status, timestamp) |

## Test Suite

```bash
pytest
```

73 tests across 13 modules:

| Module | Covers |
|--------|--------|
| `test_startup.py` | App initialization, health endpoint |
| `test_query_processor.py` | Option rendering, strict single-choice contract |
| `test_reporting.py` | PDF generation, native fallback |
| `test_experiment_runner.py` | Condition config, experiment execution |
| `test_counterfactual.py` | Shuffle-aware option reconstruction |
| `test_config.py` | Environment variable parsing |
| `test_ai_service.py` | Model response handling, refusal detection |
| `test_analysis_scoring.py` | Reasoning quality scoring |
| `test_analysis_error_render.py` | Error HTML escaping |
| `test_view_models.py` | View model building, markdown safety |
| `test_model_fingerprint_routes.py` | Fingerprint endpoint validation |
| `test_run_id_validation.py` | Run ID format enforcement |
| `test_run_id_migration.py` | Legacy-to-strict ID migration |

## Repository Layout

```
main.py                  App factory, startup wiring, routes
lib/
  ai_service.py          OpenRouter client with retry/backoff
  query_processor.py     Run execution, iteration loop, option parsing
  analysis.py            LLM insight generation engine
  storage.py             Filesystem persistence (runs + experiments)
  validation.py          Pydantic request models
  config.py              App configuration (env + models.json)
  paradoxes.py           Paradox loader + validation
  view_models.py         Template-safe view models
  stats.py               Statistical functions (chi-square, Wilson CI, Cohen's h)
  counterfactual.py      Evidence-based run reconstruction
  experiment_runner.py   Parallel experiment execution
  fingerprint.py         Model ethics profiling
  reporting.py           PDF report orchestration
  pdf_native.py          Pure-Python PDF fallback
  pdf_charts.py          Chart rendering for reports
  comparison_report.py   Multi-run PDF layout
  report_models.py       Typed report context schemas
  report_writer.py       AI narrative generation
  export_data.py         JSON export formatter
  export_pptx.py         PowerPoint generation
  query_errors.py        Typed exception hierarchy
templates/               Jinja2 views and partials
static/                  Candlelight theme CSS
tests/                   pytest suite (73 tests)
paradoxes.json           Scenario library (47 paradoxes)
models.json              Available model definitions
docs/architecture/       Boundary, state, and tech-stack contracts
results/                 Persisted run output (gitignored)
experiments/             Persisted experiments (gitignored)
```

## Run Data Shape

Each run file (`results/<run_id>.json`) includes:

- **Identity:** `runId`, `timestamp`, `modelName`, `paradoxId`, `paradoxType`
- **Config:** `prompt`, optional `systemPrompt`, `iterationCount`, `params`
- **Options:** `options[]` with id, description, and shuffle mapping
- **Responses:** `responses[]` with decision token, explanation, raw output per iteration
- **Stats:** `summary.options[]` (counts, percentages) + `summary.undecided`
- **Analysis:** optional `insights[]` (cached from analyst model)

## Security Notes

- Required secrets validated at startup — app crashes if missing
- Strict run ID regex (`<base>-NNN`) blocks path traversal
- Path resolution validated with `is_relative_to()` before filesystem access
- Markdown rendering escapes HTML before render, strips `<a>`/`<img>` post-render
- Input validation via Pydantic at all HTTP boundaries
- Model names regex-validated: `^[a-z0-9\-_/:.]+$`

## Config Source Priority (models)

1. `models.json` (file) → 2. `OPENROUTER_MODELS` (env) → 3. `AVAILABLE_MODELS_JSON` (env)
