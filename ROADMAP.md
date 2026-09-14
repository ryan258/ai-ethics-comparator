# AI Ethics Comparator — Project Roadmap

**Current Version:** v6.1.0 (Audit Remediation)  
**Architecture Baseline:** Local-First FastAPI + Jinja2 + HTMX  
**Verification Baseline:** 164 tests passing, zero ruff F/E9/ASYNC errors, Candlelight palette compliant  
**Last Updated:** September 14, 2026 (post-audit)  

---

## 1. Executive Summary

AI Ethics Comparator is a research workbench designed to measure, analyze, and profile how Large Language Models resolve complex ethical dilemmas across repeated iterations. It moves beyond single-turn anecdotal prompting by combining statistical rigor (Wilson confidence intervals, Cohen's h, Chi-square tests), counterfactual evidence injection, automated multi-condition experiments, and executive decision briefings.

Version 6.0.0 marks the consolidation from an earlier multi-framework prototype into a hardened, dependency-minimal Python architecture following the *No-Bloat*, *Arsenal Portability*, and *Candlelight* design guidelines.

---

## 2. Completed Milestones

### Milestone 1: Multi-Option Dilemma Engine (Completed)
- **N-Way Dilemmas (2–4 Options):** Expanded beyond binary trolley problems with dynamic `{{OPTIONS}}` prompt templating.
- **Position-Bias Mitigation:** Random per-iteration option permutation with a recorded
  shuffle-unshuffle mapping to neutralize token ordering bias. (Corrected in v6.1: the
  permutation is random, not cyclic, and was previously unreachable from the main run path —
  see Milestone 5.5 / D-04.)
- **Structured Extraction with Defensive Fallback:** Enforced structured JSON output with 7-layer extraction fallback chain (JSON parse → brace regex → heuristic NLP → AI classifier fallback → undecided).
- **Independent Re-Ask Budget:** Separated provider transport retries from model reasoning re-asks, preventing runaway billing on unparseable outputs.

### Milestone 2: Scenario Library Consolidation (Completed)
- **197 Dilemmas in `paradoxes.json`:** Consolidated all archived classic and literary scenarios (70 2-option, 2 3-option, 125 4-option).
- **Run-Level Scenario Snapshotting:** Every run record permanently preserves the exact scenario title and option definitions tested, ensuring older run files never 404 or desynchronize.
- **Strict Data Validation:** Full schema enforcement in `lib/paradoxes.py` validating options, labels, descriptions, and prompt placeholders.

### Milestone 3: Executive Briefing & WeasyPrint PDF Pipeline (Completed)
- **Strategic Brief Architecture:** Standardized reporting around a 5-part consulting brief pipeline (`EvidencePackage` → `ExecutiveBriefComposer` → `ExecutiveBrief` → `ExecutiveBriefPlugin` → `ExecutiveBriefRenderer`).
- **Elimination of Fragile PDF Fallback (Decision D10):** Replaced 1,445 lines of unmaintained pure-Python PDF layout code with an uncompromising WeasyPrint engine; endpoints fail with clear 503 HTTP status when system GTK/Pango dependencies are missing.
- **Decoupled Scenario Prose:** Per-paradox executive framing and theme guidance moved to declarative data files (`report_overrides.json`, `report_themes.json`).
- **Multi-Format Export:** Supported single-run and side-by-side comparison WeasyPrint PDFs, structured JSON data export, and slide-ready PowerPoint decks (`.pptx`).

### Milestone 4: Security, Resilience & Bounds Hardening (Completed)
- **SSRF & Local File Read Prevention:** Customized WeasyPrint URL fetcher to refuse all external protocols (`http://`, `https://`, `file://`), neutralizing server-side request forgery risks during PDF generation.
- **Strict HTML Autoescaping:** Configured Jinja2 autoescape across all report generation environments.
- **Filesystem Traversal Defenses:** Strict regex validation (`^[A-Za-z0-9_-]+-\d{3}$`) and `is_relative_to()` resolution checks for all storage operations.
- **Bounded In-Memory Caching:** Capped `RunStorage._metadata_cache` at 5,000 entries with FIFO eviction, preventing memory leaks during high-throughput scanning.
- **Atomic File Creation:** POSIX atomic `os.link` reservation with safe `open('x')` fallback to guarantee concurrent execution safety without a relational database.

### Milestone 5: Statistical Rigor & Profiling (Completed)
- **Statistical Suite (`lib/stats.py`):** Pure-Python implementations of normal CDF, Wilson score intervals, Cohen's h effect size interpretations, and Chi-square goodness-of-fit / contingency tests.
- **Model Fingerprinting:** Cross-paradox aggregation mapping model moral tendencies and consistency with confidence intervals.
- **Counterfactual Experimentation:** Evidence injection pipelines that re-test models against original choices while holding option ordering fixed.
- **Automated Matrix Runner:** Batch execution across parameter grids (temperatures, system prompts, models, scenarios).

### Milestone 5.5: Audit Remediation (Completed)

A full architecture and code audit found seven defects, three critical. All are fixed and
each is pinned by a regression test, because the common root cause was invariants asserted
in prose but never enforced in code.

- **DOM injection closed (D-01):** `GET /api/runs/{id}` serves unescaped model output, and
  HTMX swaps with `innerHTML` regardless of `Content-Type`. The JSON-dump trigger now uses
  `hx-swap="textContent"`; a test fails if that attribute is removed.
- **Fingerprint made discriminating (D-02):** the analyst returns a per-complex intensity
  `count` that the aggregator discarded, counting mere presence instead. Presence saturates
  near 100% for every model, so every profile looked identical. Dominance (argmax per run,
  Wilson interval) plus intensity share replaced it — measured separation went from a flat
  0.87–1.00 band to a real shape (0.71 / 0.35 / 0.06).
- **D11 enforced in one place (D-03):** three consumers stopped at a live-library lookup,
  silently exporting null paradoxes and rendering "Unknown Paradox". All five call sites now
  use `resolve_paradox()`; two of them had been duplicating the tiers inline.
- **Position bias actually mitigated (D-04):** `QueryRequest` had no shuffle field at all, so
  the primary UI workflow never shuffled despite the roadmap claiming the feature shipped.
  Shuffling is now exposed, defaults on, and draws a fresh ordering **per iteration** rather
  than once per run (see D12).
- **Scenario vocabulary (D-05):** `dimensions` added from a closed seven-label set matching
  the analyst prompt, validated at load, backfilled across all 197 scenarios (see D13).
- **One report layout (D-06):** D10's "no silent second backend" principle applied to layout
  as well as engine; the 790-line legacy template is deleted and failures surface as 503.
- **Hygiene (D-07):** blocking `open()` removed from three async paths, dead view-model field
  deleted, CI added, lint gate widened to include `ASYNC`, doc claims asserted in CI.

A review pass over the remediation itself caught two further defects, both fixed:

- **Mis-mapped answers when the prompt cannot express a permutation (D-08).** The D-04 change
  re-rendered the prompt per iteration, but a paradox reconstructed under D11 tier 3 carries
  the run's already-rendered prompt as its template — there is no placeholder left, so the
  reorder was a no-op while the mapping still claimed a shuffle. Every answer was then
  translated through a permutation that never happened; a repro recorded option 2 where the
  model had chosen option 1. Per-iteration shuffle now requires
  `template_supports_option_rendering()` and degrades to a fixed order otherwise (see D12).
- **Report profile pointed at a wrong-context template (D-09).** Repointing
  `single_template_name` at `strategic_analysis_brief.html` would have let the engine's
  single path render brief markup against a `SingleRunReport`. The profile now declares no
  direct single path at all (see Seam 5c-2).

`_resume_run_by_id` was also moved onto `resolve_paradox()` for consistency: a run whose
scenario left the library is now resumable rather than raising, because the run carries its
own prompt and options.

---

## 3. Accepted Architectural Constraints & Risks

In accordance with our architectural decisions (`docs/architecture/arch-decisions.md`):

1. **Local-First Trust Boundary:**
   - *Design Choice:* The application is designed for local-first single-researcher execution on bare metal.
   - *Accepted Trade-off:* HTTP endpoints lack user authentication, session roles, or rate limiting. Public deployment requires an external reverse proxy (e.g., Caddy/Nginx) with basic auth and TLS termination.
2. **Cooperative Task Cancellation:**
   - *Design Choice:* Experiment and run cancellation relies on `asyncio` cancellation flags checked between iterations.
   - *Accepted Trade-off:* An in-flight HTTP request to OpenRouter will complete before the worker halts.
3. **Strict Color Palette Enforcement:**
   - *Design Choice:* The user interface is strictly bound to the 5-color Candlelight palette (`#121212`, `#EBD2BE`, `#A6ACCD`, `#98C379`, `#E06C75`).
   - *Accepted Trade-off:* Third-party CSS themes and uncurated palettes are rejected.
4. **Trolley-Contract Primacy:**
   - *Design Choice:* Scenarios are structured around discrete option tokens (`{1}`–`{N}`) with accompanying explanatory rationale.
   - *Accepted Trade-off:* Freeform unconstrained dialogue scenarios are deferred to future major releases.

---

## 4. Future Milestones

### Milestone 6 (v6.2): Interactive Significance Testing in Web UI
- **Objective:** Surface statistical comparison metrics directly in the browser comparison dashboard.
- **Planned Capabilities:**
  - Dynamic HTMX-driven 2-run and 4-run Chi-square test calculator.
  - Cohen's h effect size indicators highlighting statistically significant shifts in moral choice distributions.
  - Interactive contingency tables showing observed vs. expected choice counts.

### Milestone 7 (v6.3): Real-Time Server-Sent Events (SSE) Streaming
- **Objective:** Provide granular, real-time feedback during long-running batch iterations.
- **Planned Capabilities:**
  - Replace polling with an SSE stream (`/api/runs/{run_id}/stream`) emitting iteration completion events, token usage, and live distribution updates.
  - Streaming visualization in the HTMX results card with zero page refreshes.

### Milestone 8 (v6.4): Advanced Model Fingerprint Visualizations
- **Objective:** Deepen model-to-model comparative profiling across ethical dimensions.
- **Now unblocked by:** D13's closed `dimensions` vocabulary gives the radar chart a stable
  categorical axis, and D-02's dominance metric gives it values that actually differ between
  models. Both were prerequisites this milestone previously lacked.
- **Planned Capabilities:**
  - SVG radar / spider charts comparing model alignment scores across paradox categories (e.g., Deontology vs. Utilitarianism, AI Safety vs. Autonomy).
  - Cross-model fingerprint comparison matrices comparing multiple providers side-by-side.

### Milestone 9 (v7.0): Multi-Turn Socratic Deliberation
- **Objective:** Test the resilience and depth of moral commitments under adversarial dialogue.
- **Planned Capabilities:**
  - Multi-turn interrogator agent that challenges initial model rationales with edge-case counter-arguments.
  - Measurement of moral malleability: quantifying how easily a model abandons its stated framework under pushback.

---

## 5. Known Follow-Ups

Carried forward from the audit; none are defects, all are improvements.

1. **Review the dimension backfill.** `scripts/backfill_dimensions.py` produced the current
   assignments from a keyword lexicon scored by corpus-relative lift. Distribution is healthy
   (Consequence 69%, Purity 10%) and spot checks read sensibly, but these are heuristic and
   want a human pass. Re-running preserves hand edits.
2. **Widen the lint gate further.** `F,E9,ASYNC` is clean. `S`, `UP`, and `I` report ~470
   findings, almost all mechanical (223 are `UP006` annotation style). Needs a `--fix` pass
   plus noqa curation for the handful that are deliberate (`S311` jitter, `S104` local bind,
   `S704` the documented `safe_markdown` path).
3. **Split `main.py` into routers.** All 22 routes live inside one 816-line `create_app`.
   `APIRouter` handles this without disturbing D1's lifespan wiring.
4. **Run index file.** `list_runs()` parses every file in `results/` on each request, and the
   fingerprint then re-reads each match. Fine at 136 runs; not at 5,000.
5. **Cost accounting.** `tokenUsage` is already captured and summed per run. Surfacing
   spend-per-run and projected experiment cost is close to free and is the first question
   anyone asks before launching a large matrix.
