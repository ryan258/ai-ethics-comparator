# AI Ethics Comparator — Project Roadmap

**Current Version:** v6.0.0 (Consolidation Complete)  
**Architecture Baseline:** Local-First FastAPI + Jinja2 + HTMX  
**Verification Baseline:** 123 tests passing, zero ruff F/E9 errors, Candlelight palette compliant  
**Last Updated:** September 14, 2026  

---

## 1. Executive Summary

AI Ethics Comparator is a research workbench designed to measure, analyze, and profile how Large Language Models resolve complex ethical dilemmas across repeated iterations. It moves beyond single-turn anecdotal prompting by combining statistical rigor (Wilson confidence intervals, Cohen's h, Chi-square tests), counterfactual evidence injection, automated multi-condition experiments, and executive decision briefings.

Version 6.0.0 marks the consolidation from an earlier multi-framework prototype into a hardened, dependency-minimal Python architecture following the *No-Bloat*, *Arsenal Portability*, and *Candlelight* design guidelines.

---

## 2. Completed Milestones

### Milestone 1: Multi-Option Dilemma Engine (Completed)
- **N-Way Dilemmas (2–4 Options):** Expanded beyond binary trolley problems with dynamic `{{OPTIONS}}` prompt templating.
- **Position-Bias Mitigation:** Implemented cyclic option permutation and deterministic shuffle-unshuffle mapping to neutralize token ordering bias.
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

### Milestone 6 (v6.1): Interactive Significance Testing in Web UI
- **Objective:** Surface statistical comparison metrics directly in the browser comparison dashboard.
- **Planned Capabilities:**
  - Dynamic HTMX-driven 2-run and 4-run Chi-square test calculator.
  - Cohen's h effect size indicators highlighting statistically significant shifts in moral choice distributions.
  - Interactive contingency tables showing observed vs. expected choice counts.

### Milestone 7 (v6.2): Real-Time Server-Sent Events (SSE) Streaming
- **Objective:** Provide granular, real-time feedback during long-running batch iterations.
- **Planned Capabilities:**
  - Replace polling with an SSE stream (`/api/runs/{run_id}/stream`) emitting iteration completion events, token usage, and live distribution updates.
  - Streaming visualization in the HTMX results card with zero page refreshes.

### Milestone 8 (v6.3): Advanced Model Fingerprint Visualizations
- **Objective:** Deepen model-to-model comparative profiling across ethical categories.
- **Planned Capabilities:**
  - SVG radar / spider charts comparing model alignment scores across paradox categories (e.g., Deontology vs. Utilitarianism, AI Safety vs. Autonomy).
  - Cross-model fingerprint comparison matrices comparing multiple providers side-by-side.

### Milestone 9 (v7.0): Multi-Turn Socratic Deliberation
- **Objective:** Test the resilience and depth of moral commitments under adversarial dialogue.
- **Planned Capabilities:**
  - Multi-turn interrogator agent that challenges initial model rationales with edge-case counter-arguments.
  - Measurement of moral malleability: quantifying how easily a model abandons its stated framework under pushback.
