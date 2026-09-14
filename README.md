# AI Ethics Comparator

A local-first research tool for measuring how LLMs respond to trolley-style ethical dilemmas across repeated iterations. Built with FastAPI + HTMX.

## What It Does

Run any OpenRouter model against ethical paradoxes (2-4 options each), repeat across many iterations, then analyze the patterns: which moral frameworks dominate, how consistent is the model, and what happens when you inject counterfactual evidence.

## Stack

- **Backend:** FastAPI (app-factory pattern)
- **Templates:** Jinja2 + HTMX (no build step)
- **AI provider:** OpenRouter via AsyncOpenAI
- **Reports:** WeasyPrint PDF (no fallback backend — 503 when its native libs are missing), PowerPoint export
- **Storage:** flat JSON files (no database)
- **Python:** >=3.12, managed with `uv`

## Quick Start

```bash
uv sync
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
uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Open [http://localhost:8000](http://localhost:8000).

## Features

### Runs
Execute a model against a paradox for N iterations. Each iteration captures the model's decision token, explanation, and raw output. Results are stored as `results/<run_id>.json` with aggregate statistics.

**Option order is permuted per iteration by default.** Models favour first- and last-listed
options, so a fixed order means the reported distribution carries uncontrolled position bias.
Every response records the exact ordering it was shown under `optionOrder`, and answers are
translated back to canonical option IDs before aggregation. Turn it off per run with
`shuffleOptions: false` when you specifically want to measure ordering effects.

### Analysis
LLM-powered insight generation identifies moral complexes, decision quality, paradox severity, and the model's ethical strategy. Results are cached in the run file. Analyst model is configurable per request.

### Counterfactuals
Take an existing run and inject evidence ("what would change your mind?") to produce a new run. Holds option order fixed so injected evidence is the only variable.

### Experiments
Define a matrix of paradoxes and conditions (different models, parameters, system prompts), then execute them in parallel. Track status, errors, and per-condition results.

### Fingerprinting
Aggregate all runs for a given model to build an ethics profile. Each dimension reports
**dominance** — the share of runs in which that moral complex led the model's reasoning,
with a Wilson confidence interval — plus **intensity share**, its portion of all reasoning
weight the analyst assigned. Dominance is measured, not merely detected: counting a complex
as present saturates near 100% for every model and tells you nothing.

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
| POST | `/api/runs/{run_id}/resume` | Resume an interrupted or failed run |
| POST | `/api/runs/{run_id}/cancel` | Cancel an active run |
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
uv run pytest
```

## Environment Management

- `pyproject.toml` defines the Python version and dependency manifests.
- `uv.lock` is the committed lockfile for reproducible installs.
- `uv sync` is the only supported install workflow.
- `uv run ...` is the supported way to invoke project tools.
- After dependency changes, run `uv lock`.

164 tests across 26 modules:

| Module | Covers |
|--------|--------|
| `test_startup.py` | App initialization, health endpoint |
| `test_query_processor.py` | Option rendering, strict single-choice contract |
| `test_run_execution_limits.py` | Re-ask/provider budgets, progress persistence, failure surfacing |
| `test_reporting.py` | PDF generation, brief-first rendering, scenario prose |
| `test_report_rendering_security.py` | Report autoescape + blocked URL fetcher |
| `test_executive_reporting.py` | Report engine wiring, WeasyPrint runtime |
| `test_executive_briefing.py` | Brief composition and rendering |
| `test_executive_component.py` | Reusable brief component contract |
| `test_experiment_runner.py` | Condition config, experiment execution |
| `test_counterfactual.py` | Shuffle-aware option reconstruction |
| `test_config.py` | Environment variable parsing and bounds |
| `test_ai_service.py` | Model response handling, refusal detection |
| `test_analysis_scoring.py` | Reasoning quality scoring |
| `test_analysis_error_render.py` | Error HTML escaping |
| `test_view_models.py` | View model building, markdown safety |
| `test_model_fingerprint_routes.py` | Fingerprint endpoint validation |
| `test_run_id_validation.py` | Run ID format enforcement |
| `test_run_id_migration.py` | Legacy-to-strict ID migration |
| `test_storage_guards.py` | Run ID write validation, metadata cache |
| `test_stats.py` | Statistical functions (normal CDF, Wilson CI, Cohen's h, Chi-square) |
| `test_json_extract.py` | JSON recovery from model output (direct, fenced, wrapped prose) |
| `test_paradox_resolution.py` | D11 three-tier paradox resolution across every consumer |
| `test_position_bias.py` | Per-iteration option permutation and un-shuffling |
| `test_fingerprint.py` | Intensity-weighted dominance, cross-model separation |
| `test_paradox_dimensions.py` | Closed dimension vocabulary, saturation guard |
| `test_run_json_dump_escaping.py` | Model output never reaches the DOM as markup |

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
  report_prose.py        Rationale themes + scenario prose resolution
  pdf_charts.py          Inline SVG charts for reports
  comparison_report.py   Multi-run PDF layout
  report_models.py       Typed report context schemas
  report_writer.py       AI narrative generation
  export_data.py         JSON export formatter
  export_pptx.py         PowerPoint generation
  json_extract.py        JSON recovery from model output
  prompt_templates.py    Cached prompt-template reader
  query_errors.py        Typed exception hierarchy + safe error messages
  executive_reporting/   Reusable brief engine, renderer, and plugins
templates/               Jinja2 views and partials
static/                  Candlelight theme CSS
tests/                   pytest suite (164 tests)
tests/fixtures/          Frozen paradoxes + overrides for report-rendering tests
paradoxes.json           Scenario library (197 paradoxes, each tagged with `dimensions`)
models.json              Available model definitions
report_overrides.json    Per-paradox executive report prose
report_themes.json       Per-theme deployment guidance
ROADMAP.md               Project roadmap and milestones
scripts/                 Doc-claim checker, dimension backfill, PDF smoke test
.github/workflows/ci.yml Lint + tests + doc-claim gate
docs/architecture/       Boundary, state, and tech-stack contracts
results/                 Persisted run output (gitignored)
experiments/             Persisted experiments (gitignored)
```

## Run Data Shape

Each run file (`results/<run_id>.json`) includes:

- **Identity:** `runId`, `timestamp`, `modelName`, `paradoxId`, `paradoxType`
- **Scenario snapshot:** `paradoxTitle` + `paradox` (full definition, deep-copied at run
  creation) so reports never depend on `paradoxes.json` staying unchanged — see D11
- **Option order:** `shufflePerIteration` flag; each response carries the `optionOrder`
  mapping it was shown
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

## Report Resilience

Editing or replacing `paradoxes.json` does not orphan stored runs. Paradoxes resolve in three
tiers — live library, then the run's own snapshot, then reconstruction from the run's stored
`prompt` and `options`. Every historical run stays exportable. See `docs/architecture/arch-decisions.md` D11.

## Config Source Priority (models)

1. `models.json` (file) → 2. `OPENROUTER_MODELS` (env) → 3. `AVAILABLE_MODELS_JSON` (env)
