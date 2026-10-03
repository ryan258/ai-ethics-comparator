# Operating handbook

## Run locally

Use Python 3.12 or newer and `uv sync --locked`. Copy `.example.env` to `.env` and configure the provider key, provider URL, and application base URL. Choose available models in `models.json`. Keep `.env` and result files private.

```bash
uv run uvicorn main:app --host 127.0.0.1 --port 8000
```

Use one process. Application reload/restart interrupts background work; startup records interruption instead of automatically spending provider quota to resume it.

## Configuration

| Variable | Meaning |
| --- | --- |
| `OPENROUTER_API_KEY` | Required provider credential |
| `OPENROUTER_BASE_URL` | Required provider API endpoint |
| `APP_BASE_URL` | Required application URL and trusted browser origin |
| `APP_HOST` | Host used by the Python entrypoint; uvicorn CLI uses its own `--host` flag |
| `APP_NAME` | Environment-backed application title |
| `DEFAULT_MODEL`, `ANALYST_MODEL` | Configured model IDs; default to the first configured model when unset |
| `REPORT_THEME` | `dark` or `light` |
| `MAX_ITERATIONS` | Maximum requested iterations per run; default 50 |
| `AI_CONCURRENCY_LIMIT` | Shared provider-call limit, including analysis; default 2 |
| `AI_MAX_RETRIES` | Transport retries after the first attempt; default 2 |
| `AI_RETRY_DELAY` | Base backoff delay in seconds; default 2 |
| `AI_REQUEST_TIMEOUT` | Whole provider-call deadline including waiting/backoff; default 120 seconds |
| `AI_CHOICE_INFERENCE_ENABLED` | Enables additional model-based classification; default false |

A configured model may become unavailable. The app shows a safe failure reason rather than silently selecting a different model.

## Runs and recovery

`POST /api/query` accepts JSON or the HTMX form's encoded JSON. Required fields are `modelName` and `paradoxId`; optional fields include `iterations`, `systemPrompt`, `params`, `shuffleOptions`, and `shuffleSeed`.

A successful JSON request returns `202` and a reserved record. Provider failures happen in background execution and appear in the saved `status` / `lastError`; they are not retroactive HTTP 401/402 responses to the initial request.

```bash
# Replace RUN_ID with the ID returned by creation, or use the run card controls.
curl --fail-with-body http://localhost:8000/api/runs/RUN_ID
curl --fail-with-body -X POST http://localhost:8000/api/runs/RUN_ID/resume
```

Resume is allowed for failed, interrupted, or cancelled runs. It preserves recorded outcomes, including undecided responses, and uses the saved scenario. Cancellation preserves checkpoints and records attempts whose completion/usage is unknown. Individual condition resume is blocked while its matrix is actively executing.

Counts have distinct meanings: requested iterations; recorded terminal outcomes; decided choices; undecided outcomes; missing iterations; outcomes with output errors. Errors and undecided may overlap. Percentages use recorded outcomes as the denominator.

## Analysis

Use the analyst selector in a stopped run's dialog. Empty and active runs are rejected. Analysis is optional and costs calls; rubric assessment may add a second call when a rubric is present. Draft rubrics are not validated scores. Regenerate preserves the selected analyst. Concurrent identical requests are coalesced and persisted once.

The fingerprint includes only completed, full-length, error-free runs with a current schema-valid analysis tied to the exact evidence hash. Missing legacy status or stale analysis remains an explicit exclusion. No automatic re-analysis is performed.

## Experiments

Choose scenarios and models with checkboxes, set iterations, then create the manifest. Creation does not execute it. Execute launches bounded condition batches. Continue unfinished conditions skips completed runs and resumes saved incomplete conditions. A manifest derives its state from linked runs. Saved device presets do not include API credentials.

## Reports and exports

| Route | Result |
| --- | --- |
| `/reports/runs/{run_id}` | Printable HTML brief |
| `/reports/runs/{run_id}?theme=light` | Light brief; `dark` is also supported |
| `/reports/runs/{run_id}?view=slides` | Square HTML insight slides |
| `/reports/compare?run_ids=ID1,ID2` | Same-stimulus comparison of two to four distinct runs |
| `/reports/counterfactuals/{run_id}` | Descriptive child/parent comparison |
| `/api/runs/{run_id}/export?format=json` | Complete stored JSON record |
| `/api/runs/{run_id}/export?format=pptx` | PowerPoint deck |

Reports use saved evidence without model calls. Save an HTML response as `.html`; to obtain PDF, open it in the browser and use Print / Save as PDF. Check pagination, backgrounds, paper size, and clipping in the export preview. JSON includes recorded attempts; historical transport/accounting facts may be missing.

Small-sample statistical warnings suppress an unqualified significance conclusion. Pairwise p-values are exploratory and unadjusted for multiple comparisons. Keyword rationale labels and model-written analysis are not observed internal reasoning.

## Remaining API routes

- `GET /health`, `GET /api/paradoxes`, `GET /api/fragments/paradox-details`
- `GET /api/runs`, `GET /api/runs/{run_id}`
- `POST /api/runs/{run_id}/cancel`, `POST /api/runs/{run_id}/counterfactual`
- `POST /api/runs/{run_id}/analyze`, `POST /api/insight`
- `GET/POST /api/experiments`, `GET /api/experiments/{exp_id}`, `POST /api/experiments/{exp_id}/execute`
- `GET /api/models/{model_id}/fingerprint`, `GET /fragments/fingerprint`

## Invalid or historical files

```bash
uv run python scripts/preview_legacy_runs.py
```

This reads files and emits per-file issues and missing provenance without changing anything. Invalid records are rejected individually and preserved on disk. Back up originals before any deliberate manual repair. Missing historical status, scenario snapshots, or call histories cannot be reconstructed reliably from current library content.

## Verification and troubleshooting

Run `bash scripts/verify_local.sh` and send its output. Tests block unmocked provider calls. This command performs no GitNexus indexing. The October remediation is pending this verification; older passing results do not validate it.

If browser changes are rejected, open the configured local application URL and check `APP_BASE_URL`. Do not disable the origin/host guard. Headerless local CLI clients remain supported.
