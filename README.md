# AI Ethics Comparator

A personal, local research workbench for exploring model responses to authored ethical dilemmas. FastAPI serves Jinja2 pages enhanced with vendored HTMX. Runs and experiment manifests are JSON files; no database or frontend build is required.

This measures responses under a particular prompt and configuration. It does not certify moral correctness, a model's internal reasoning, deployment suitability, or a general ethical trait.

## Start

```bash
uv sync --locked
cp .example.env .env
```

Edit `.env` with your provider credentials and endpoints. Model identifiers come from `models.json`, then environment fallbacks. Their presence in configuration does not verify provider availability.

```bash
uv run uvicorn main:app --host 127.0.0.1 --port 8000
```

Open [the local workbench](http://localhost:8000). Keep one application process: run tasks, analysis deduplication, and file locks are local to that process. Development reload interrupts active work; resume it deliberately after restart.

## Workflow

1. Choose a scenario, configured model, iteration count, and optional persona.
2. Create the run. The JSON API returns `202` with a run ID; poll the saved record for completion. The page updates progress without restarting the form.
3. Inspect recorded choices, undecided outcomes, raw responses, and failures. Resume executes only missing iterations and preserves terminal undecided outcomes.
4. Optionally request analyst interpretation of a stopped run. This makes additional provider calls. Simultaneous identical requests share one analysis operation.
5. Open a saved-evidence report or export JSON/PPTX. HTML reports support browser Print / Save as PDF. Report generation makes no model calls.

History supports search and pagination. Comparison checkboxes constrain selection to matching stored scenario revisions and option meanings. Laboratory checkboxes avoid modifier-key multiselect, and Save setup / Restore saved setup retain one experiment preset on the current device.

## Evidence contracts

- New scenarios use one JSON output contract from `lib/prompt_contract.py`. Historical saved prompts are preserved. The scenario library revision changed on 2026-10-03.
- New runs record `schemaVersion`, `protocolVersion`, a scenario snapshot, `shuffleSeed`, and per-response option mappings. `shuffleSeed` controls option order; generation `params.seed` is a separate provider setting.
- `responses` contains terminal outcomes. Undecided is an outcome, not an unexecuted iteration. Interrupted attempts are retained separately and never counted as completed responses.
- `build_run_measurements()` computes percentages from all recorded outcomes, including undecided. Requested-but-missing iterations are reported separately.
- Attempts retain prompts, raw output, available usage, provider metadata, and inference details. Failed transport usage and older call histories may be unavailable; JSON export is the complete **stored record**, not a guarantee of complete provider accounting.
- Heuristic report labels use response text only. Analyst judgments are separately identified, schema-checked, versioned, and tied to an evidence hash.
- Fingerprints list their included cohort and exclusions. They describe the sampled scenarios, personas, configurations, and evaluators, not a population-wide model rating.

## Features and limits

**Experiments:** create a bounded matrix, execute it, cancel individual runs, and continue unfinished conditions. Completed outcomes are retained. Ambiguous legacy condition identities require individual run recovery.

**Counterfactuals:** a linked child run injects hypothetical evidence drawn from a response. Its dedicated descriptive report shows both prompts and configurations. This is not verified new evidence or a causal test: stimulus and option-order conditions may differ. Ordinary comparisons still require identical stored stimuli.

**Reports:** single-run briefs, comparison reports, square insight slides, JSON, and PPTX. Partial/failed/unknown run status is visible. Light/dark choices propagate through the brief renderer. Browser PDF pagination and slide layout require inspection in the browser used to export.

**Content:** the library contains 197 scenarios. `scenario_packs.json` identifies a bounded governance starter pack. Categories aid navigation; dimension tags and authored rubrics are explicitly unvalidated. Historical literary/adapted framings remain part of the exploratory library. See [the content codebook](docs/content-codebook.md).

## Configuration

Required: `OPENROUTER_API_KEY`, `OPENROUTER_BASE_URL`, `APP_BASE_URL`.

Optional: `APP_NAME`, `DEFAULT_MODEL`, `ANALYST_MODEL`, `REPORT_THEME`, `MAX_ITERATIONS`, `AI_CONCURRENCY_LIMIT`, `AI_MAX_RETRIES`, `AI_RETRY_DELAY`, `AI_REQUEST_TIMEOUT`, `AI_CHOICE_INFERENCE_ENABLED`.

Defaults: shared provider concurrency 2, transport retries 2, total provider-call deadline 120 seconds, choice classifier disabled. The SDK does not add retries. Query execution does not retry an exhausted transport operation. Output correction permits two reasks. Structured-format negotiation can add one fallback request. Analysis and classifier calls use the same provider limiter.

## API and operation

See [HANDBOOK.md](HANDBOOK.md) for current routes, asynchronous examples, recovery, and configuration. Start with loopback binding. Browser mutation requests validate Host, Origin, Referer, and cross-site fetch context; local headerless CLI requests remain supported. This is a personal single-process tool, not an internet-facing authenticated service.

## Verification

The first owner-run verification reported 210 passed and 5 failed; focused typing and documentation checks passed. The failing fixtures and lint invocation have been corrected, with the follow-up run pending. Run the complete local command below and retain its output:

```bash
bash scripts/verify_local.sh
```

This runs pinned lint, focused static typing, pytest, and documentation contracts, with a guard against unmocked provider calls. It does not rebuild GitNexus or call live providers. A read-only historical-data preview is separate:

```bash
uv run python scripts/preview_legacy_runs.py
```

The preview does not rewrite files, fill in unknown facts, or generate paid analyses.

## Architecture

`main.py` wires request handling and task lifecycles. `lib/query_processor.py` executes iterations; `lib/ai_service.py` owns provider limits and retries; `lib/run_executor.py` checkpoints runs; `lib/experiment_state.py` reconciles manifests. `lib/measurements.py` provides the typed read boundary and shared counts. Analysis and rendering consume saved evidence through explicit adapters.

Core logic does not import application routes or the presentation layer. Jinja rendering, report composition, and Markdown formatting live under `presentation/`; they consume the reusable core. The internal imports formerly under `lib.reporting`, `lib.view_models`, and `lib.executive_reporting` now use `presentation`. See [architecture boundaries](docs/architecture/boundaries.md).
