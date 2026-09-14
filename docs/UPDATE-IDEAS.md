# UPDATE-IDEAS — Turning AI Ethics Comparator into a Comprehensive Tool for AI Professionals

Last updated: 2026-09-14
Based on: full project review at v6.0.0 consolidation.

> **Status note:** items marked **[DONE — v6.0.0]** shipped in the consolidation release.
> They are kept here so the reasoning behind each change stays on record.

All proposals respect the hard constraints in `docs/architecture/tech-stack.md`:
Python 3.12 + uv, FastAPI + HTMX (no build step), flat JSON storage, OpenRouter
as the AI provider, no Docker/React/heavy auth.

---

## Current State Assessment

**What works well**

- Clean seams: thin routes → `lib/` services → storage, enforced by architecture docs and 123 passing tests (~4s runtime).
- Strong parsing pipeline: JSON → brace-token regex → heuristic → AI classifier fallback chain, with re-ask logic and refusal detection.
- Real statistical grounding exists (`lib/stats.py`: Wilson CI, chi-square, Cohen's h) and is now **wired into the comparison report**. The unused `bootstrap_consistency()` was deleted rather than left to rot.
- Fingerprinting + counterfactuals + experiment matrix are genuinely differentiating features most eval tools don't have.
- Security posture is above average for a local tool (strict run IDs, path traversal checks, escaped markdown, Pydantic at boundaries).

**Main gaps holding it back as a professional tool**

1. Findings aren't comparable across models at a glance — no leaderboard, no cross-model matrix, no drift tracking.
2. Statistical rigor is implemented but not surfaced — comparisons show percentages without significance.
3. Not scriptable — everything requires the web UI; no CLI, no CI story.
4. Two parallel reporting systems (`lib/reporting.py`, ~1470 lines, + `lib/executive_reporting/` package) duplicate effort.
5. ~~Documentation drift~~ **[FIXED]** — doc claims are now asserted by `scripts/check_doc_claims.py` in CI, so stale counts fail the build rather than surviving a review pass.
6. Flat-JSON listing will degrade as `results/` grows (135 files already; every list operation scans and parses all of them).

---

## Ideas by Theme

Each idea: **Problem → Proposal → Effort** (S = hours, M = days, L = week+).

### Theme 1: Cross-Model Insight (highest product value)

#### 1.1 Model × Paradox matrix (leaderboard view)
- **Problem**: Fingerprints are per-model. To compare 5 models across 197 scenarios you must open 5 pages and eyeball.
- **Proposal**: New page `GET /matrix` — an HTMX-rendered heatmap table: rows = models with any runs, columns = paradoxes, cell = dominant choice + consistency % (color-coded via the Candlelight palette). Data source: a single aggregation pass over `results/` reusing `lib/fingerprint.py` logic. No new dependencies — plain `<table>` with CSS backgrounds.
- **Effort**: M

#### 1.2 Fingerprint diff (2+ models side by side)
- **Problem**: The fingerprint fragment shows one model. Professionals want "how does model A differ from model B ethically?"
- **Proposal**: `GET /fragments/fingerprint/compare?models=a,b` — reuse fingerprint aggregation, render moral-complex frequencies side by side, and flag rows where the Wilson CIs don't overlap (that's a defensible "real difference" signal, and the CI code already exists in `lib/stats.py`).
- **Effort**: S–M

#### 1.3 Model drift tracking (same model over time)
- **Problem**: Providers silently update models. A model's July fingerprint may not match its March fingerprint.
- **Proposal**: Runs already carry timestamps. Add a "timeline" mode to the fingerprint view: bucket runs by month, compute per-bucket choice distribution, and run `chi_square_test()` between adjacent buckets. Flag significant shifts. This is a pure read-side feature — no storage changes.
- **Effort**: M

#### 1.4 Refusal rate as a first-class metric
- **Problem**: Refusals/undecided are tracked per run (`summary.undecided`) but never aggregated. For AI-safety professionals, *which dilemmas a model refuses* is often the headline finding.
- **Proposal**: Add refusal rate to fingerprints and to the matrix view (1.1), broken down by paradox category. Zero new data collection needed — it's already in the run files.
- **Effort**: S

### Theme 2: Statistical Rigor (credibility for professionals)

#### 2.1 Wire the unused stats into comparison reports — **[DONE — v6.0.0]**
- **Was**: `lib/stats.py` chi-square, bootstrap, and Cohen's h were unused. Comparison PDFs showed raw percentages, inviting over-reading of noise.
- **Shipped**: `lib/comparison_report.py` now calls `chi_square_test()`, `cohens_h()`, and `wilson_confidence_interval()`; `templates/reports/comparison_report.html` renders χ², the p-value, a significance verdict, any small-sample warning, and per-option effect sizes. `bootstrap_consistency()` was deleted instead of wired.
- **Still open**: the same numbers are not in the `?format=json` export, and the single-run brief does not show confidence intervals.

#### 2.2 Iteration-count guidance (power analysis)
- **Problem**: Users guess iteration counts. 10 iterations gives ±30% CIs; conclusions drawn from that are weak.
- **Proposal**: On the run form, show expected CI width for the selected iteration count (Wilson interval width at p=0.5 is a one-line formula). After a run, show the actual CI next to each percentage. Cheap, honest, and immediately makes output publication-grade.
- **Effort**: S

#### 2.3 Prompt-perturbation robustness testing
- **Problem**: A model's "ethics" measured on one phrasing may be phrasing artifacts. Professionals need to know if conclusions survive rewording.
- **Proposal**: New experiment condition type: "paraphrase" — the analyst model generates N semantically-equivalent rewordings of a paradox prompt (options unchanged), each executed as a normal condition. Report agreement across paraphrases as a robustness score. Fits entirely inside the existing experiment matrix machinery (`lib/experiment_runner.py`).
- **Effort**: M

#### 2.4 Position-bias report
- **Problem**: Options are shuffled per iteration (good), but the shuffle data is never analyzed. Position bias is a known LLM failure mode and you're already collecting the evidence.
- **Proposal**: Per run, cross-tab chosen-option-id vs. presented-position and chi-square it. Add one line to the run summary: "position bias detected/not detected (p=…)". The shuffle mapping is already stored in `options[]`.
- **Effort**: S

#### 2.5 Temperature/parameter sweeps
- **Problem**: Consistency at temperature 0 vs 1 is a different claim; currently a sweep means manually creating many runs.
- **Proposal**: Experiment condition expansion: allow `"temperature": [0, 0.5, 1.0]` in a condition to fan out into one condition per value. Plot consistency vs. temperature in the experiment report.
- **Effort**: M

### Theme 3: Scriptability & Reproducibility (fits into professional workflows)

#### 3.1 CLI / headless mode
- **Problem**: Everything requires the browser. Professionals want `make eval` in CI, cron-driven drift checks (see 1.3), and batch runs overnight.
- **Proposal**: `python -m lib.cli run --model X --paradox Y --iterations 50`, plus `fingerprint`, `compare`, and `export` subcommands. Implementation: `argparse` (stdlib) + direct calls into the existing services — the seams already support this since services are constructor-injected and don't depend on FastAPI. No new dependency.
- **Effort**: M

#### 3.2 Run bundle export/import
- **Problem**: Results can't be shared or merged. A colleague can't reproduce or extend your fingerprint.
- **Proposal**: `GET /api/export/bundle?runs=...` → a zip of run JSONs + the paradox definitions they reference + a manifest (app version, paradox hashes). `POST /api/import/bundle` validates IDs/paths with the existing strict patterns and refuses collisions. `zipfile` is stdlib.
- **Effort**: M

#### 3.3 CSV export
- **Problem**: JSON export exists, but analysts live in pandas/Excel. One-row-per-iteration CSV is the lingua franca.
- **Proposal**: Add `?format=csv` to the existing export endpoint: columns = run_id, model, paradox, iteration, decision_token, option_id, position, latency, tokens. `csv` module is stdlib; ~40 lines in `lib/export_data.py`.
- **Effort**: S

#### 3.4 Paradox provenance & versioning
- **Problem**: If `paradoxes.json` is edited, old runs silently refer to a paradox that no longer says what it said. That breaks longitudinal claims (1.3).
- **Proposal**: Store a content hash of the paradox definition in each run file at creation. Fingerprint/timeline aggregation groups by (paradox_id, hash) and warns when mixing versions. One field added at write time, backward compatible (missing hash = legacy).
- **Effort**: S

### Theme 4: Scenario Library Growth

#### 4.1 Paradox authoring & validation UX
- **Problem**: Adding a paradox means hand-editing a JSON file with a fragile prompt-template contract (`{1}`…`{4}` tokens, five mandatory output lines).
- **Proposal**: Two parts. (a) A `validate-paradoxes` CLI/pytest check that every entry renders correctly through `lib/query_processor.py`'s option renderer — catches broken templates before runtime. (b) An HTMX form that builds a paradox from structured fields (title, category, context, options) and generates the prompt template from a canonical skeleton, so authors never touch the instruction boilerplate.
- **Effort**: S for (a), M for (b). Do (a) first.

#### 4.2 Paradox packs by domain
- **Problem**: the 197 scenarios now carry `dimensions`, but coverage is uneven (Purity 10%). Professionals evaluating a medical or hiring assistant need domain-relevant dilemmas.
- **Proposal**: Split `paradoxes.json` into loadable packs (`paradoxes/core.json`, `paradoxes/medical.json`, …) with a manifest; `lib/paradoxes.py` loads all packs in the directory. Grow packs over time: medical triage, content moderation, hiring fairness, autonomous vehicles, privacy vs. safety.
- **Effort**: S (loader) + ongoing content work

#### 4.3 Multi-turn / pressure-testing scenarios
- **Problem**: Single-shot answers miss how models behave under pushback — a key professional concern ("does it cave when the user argues?").
- **Proposal**: Extend the counterfactual machinery (which already does one evidence-injection turn) into a scripted follow-up sequence per paradox: initial choice → scripted challenge → measure flip rate. Store as `followUps[]` in the paradox definition; report a "conviction score" (% of iterations where the choice survives the challenge).
- **Effort**: L — this is the most valuable large feature in this doc.

### Theme 5: Analysis Quality

#### 5.1 Structured analyst schema validation (Roadmap M4, still open)
- **Problem**: Malformed analyst JSON degrades to weak fallbacks.
- **Proposal**: Define the insight schema as a Pydantic model, validate analyst output against it, and re-ask once with the validation errors embedded in the retry prompt (the query processor already has re-ask machinery to copy).
- **Effort**: S–M

#### 5.2 Analyst ensemble / judge agreement
- **Problem**: All insight generation trusts one analyst model — single-judge bias is a known LLM-as-judge weakness.
- **Proposal**: Optional `analyst_models: [a, b, c]` on the analyze endpoint; run all judges, report per-field agreement, and flag low-agreement insights as unreliable in the UI and PDF. Reuses the existing per-request analyst-override plumbing.
- **Effort**: M

#### 5.3 Choice-inference audit trail
- **Problem**: When the AI-classifier fallback infers the choice from a rambling answer, that inference is itself an LLM output — professionals need to audit it.
- **Proposal**: Mark inferred decisions in the run file (`"decisionSource": "parsed" | "inferred"`), show the rate in the run summary, and let the report exclude inferred decisions as a sensitivity check.
- **Effort**: S

### Theme 6: Operations & Scale

#### 6.1 Run index file
- **Problem**: `GET /api/runs` reads and parses every file in `results/` on each request. At 135 files it's fine; at 5,000 it won't be.
- **Proposal**: Maintain `results/_index.json` (metadata-only: id, model, paradox, timestamp, status, summary counts), updated by `RunStorage.save_run()`, rebuilt on startup if missing/stale. Keeps the "flat JSON, no database" constraint while making listing O(1) file reads. If it ever falls short, SQLite (stdlib) is the escalation path — but don't start there.
- **Effort**: S–M

#### 6.2 Finish the resume/cancel work — **[PARTIALLY DONE — v6.0.0]**
- **Shipped**: interrupted-run marking (fixes the boot-loop bug), `POST /api/runs/{id}/resume`, `POST /api/runs/{id}/cancel`, provider retry caps, and `ProviderRefusedError` are all committed and documented in the README API table.
- **Still open**: neither route has a dedicated test — `tests/test_query_processor.py::test_query_processor_resumes_from_existing_run` covers the processor's resume path, not the HTTP routes. And `cancel` still has no UI affordance; `templates/partials/result_item.html` has no cancel button, so the endpoint is API-only.
- **Proposal**: add route tests following the `tests/test_startup.py` TestClient pattern, and wire a cancel button into `result_item.html` for runs in `running` state.
- **Effort**: S

#### 6.3 Cost & token accounting
- **Problem**: Token usage is captured per iteration but never rolled up. Professionals budgeting eval runs need "this fingerprint cost $X."
- **Proposal**: Sum usage per run (already possible), and optionally price it via a `costPer1kTokens` field in `models.json` entries. Display in run summary and experiment reports. Skip live price fetching — a static optional field is enough.
- **Effort**: S

#### 6.4 Minimal exposure hardening (only if ever shared beyond localhost)
- **Problem**: ROADMAP's accepted risks (no rate limiting, localhost CORS) are fine locally but will be forgotten the day someone tunnels the port to show a colleague.
- **Proposal**: A single `APP_SHARED=true` env flag that (a) requires a bearer token on `/api/*` mutating endpoints and (b) applies a simple in-memory per-IP counter on `/api/query` and `/api/insight`. Both implementable in one small middleware, stdlib only. Off by default; local-first stays frictionless.
- **Effort**: S–M

### Theme 7: Codebase Health

#### 7.1 Consolidate the two reporting systems
- **Problem**: `lib/reporting.py` (2,166 lines) and `lib/executive_reporting/` (a full package with its own engine, composer, plugins, adapters) coexist; the package README itself notes the "older profile-driven report engine that this repo still uses in parallel." Two systems means every report change is decided twice.
- **Proposal**: Pick one direction: either migrate the run/comparison PDFs onto `executive_reporting` via its adapter layer, or acknowledge `executive_reporting` as an extracted library and delete the parallel engine (`engine.py`) from it. Decide before the next reporting feature — that's when the fork tax gets paid.
- **Effort**: L (or S if the answer is "delete the duplicate engine")

#### 7.2 Split `main.py` into routers
- **Problem**: 1,052 lines, 25+ routes in one file. New routes (resume/cancel, matrix, compare) will push it past readability.
- **Proposal**: FastAPI `APIRouter` per domain — `routes/runs.py`, `routes/experiments.py`, `routes/reports.py`, `routes/fragments.py` — with `main.py` keeping factory, lifespan, and wiring. Mechanical refactor; the `_get_services(request)` pattern carries over unchanged.
- **Effort**: M

#### 7.3 Fix documentation drift
- **Problem**: ~~README and ROADMAP quoted stale counts.~~ **[FIXED]** `scripts/check_doc_claims.py` derives the test and scenario counts from the repo and fails CI on any doc that disagrees. Alignment is now asserted, not reviewed.
- **Proposal**: Correct the counts now; better, remove exact counts from prose (they rot) and state "run `uv run pytest` for the current suite." Refresh ROADMAP against this document.
- **Effort**: S

#### 7.4 Repo hygiene
- **Problem**: `COMPLETION_STATE.md`, `verify_moral_complexes.py`, `quick_verify.py`, `verify_persistence.py`, `.aider.*` files, and `.DS_Store` live at repo root — scratch artifacts mixed with the product.
- **Proposal**: Delete or move verify scripts into `tests/` if still meaningful; `.aider*` is already newly gitignored — remove tracked leftovers; add `.DS_Store` to `.gitignore`.
- **Effort**: S

---

## Suggested Priority Order

Ranked by (professional value ÷ effort), respecting dependencies:

| # | Idea | Why first |
|---|------|-----------|
| 1 | 6.2 Commit resume/cancel work | Unshipped work is the cheapest win; unblocks everything |
| 2 | 2.1 + 2.2 + 2.4 Wire existing stats (significance, CIs, position bias) | Days of work, transforms credibility; code already exists |
| 3 | 1.4 Refusal-rate metric | Data already collected, headline-worthy output |
| 4 | 7.3 + 7.4 Doc drift + hygiene | Hours; trust surface |
| 5 | 3.3 CSV export | Hours; meets analysts where they are |
| 6 | 1.1 Model × Paradox matrix | The flagship "professional tool" screen |
| 7 | 3.4 Paradox provenance hashes | Small now, impossible to retrofit honestly later |
| 8 | 3.1 CLI / headless mode | Unlocks CI, cron drift checks, batch workflows |
| 9 | 1.2 + 1.3 Fingerprint diff + drift timeline | Builds on 1.1 + 3.4 |
| 10 | 4.1a Paradox validation check | Prerequisite for library growth |
| 11 | 2.3 + 2.5 Perturbation & parameter sweeps | Deepens rigor once matrix exists |
| 12 | 5.1–5.3 Analyst hardening | Quality-of-insight tier |
| 13 | 6.1 Run index | Do when `results/` listing measurably lags |
| 14 | 7.1 + 7.2 Reporting consolidation + router split | Pay before the next big reporting/route feature |
| 15 | 4.3 Multi-turn pressure testing | Biggest feature, best saved until the measurement core above is solid |

**Explicitly deferred (YAGNI for now)**: SQLite/database migration (index file covers it), multi-provider adapters (OpenRouter + OpenAI-compatible base URL already reaches ~every model including local Ollama), user accounts/auth beyond the shared-mode token, Docker, any frontend framework — all consistent with the project's stated non-goals.
