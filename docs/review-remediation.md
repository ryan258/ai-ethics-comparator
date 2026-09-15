# September review remediation

Updated 2026-09-14. Changes are local working-tree edits; the pre-existing index is preserved. No commits, pushes or publication.

## Reports now use the browser

Open **Report** on a run card, or enter 2–4 run IDs in the comparison form. Reports are self-contained HTML with Candlelight colors, readable metadata, responsive layout, and print styles.

- **Print / Save as PDF** invokes the browser print dialog.
- **Download HTML** saves a portable report snapshot with inline styles and controls.
- **JSON export** remains the complete reproducibility record. HTML is a presentation document.
- Opening a report makes no model calls. Previously stored narratives are used only when their evidence hash matches.
- Server PDF routes, native runtime code, smoke script, CI native packages and dependencies were removed. PowerPoint export remains available.
- `REPORT_THEME` replaces `REPORT_PDF_THEME`; update a local environment override if needed. Launch defaults to loopback; `APP_HOST` is an explicit exposure choice.

## Required findings mapped to changes

| Review | Implementation |
|---|---|
| 1 | Both analyst templates use `$data`; outgoing context includes saved stimulus, options, configuration and responses. New insights record evidence, template and analyst provenance. Old insights require revalidation. |
| 2 | Override files can supply static context only. Titles, outcomes and metrics derive from measured selections. Ties and all-undecided runs are covered. |
| 3 | Snapshot-first historical resolution and resume; live library edits cannot replace the execution snapshot. D11 was corrected. |
| 4 | Counterfactuals use stored scenarios and canonical options. The evidence-source iteration is recorded. The explicit protocol is a new fixed-order experiment using that response's ordering, not a matched whole-run replay. |
| 5 | Shared run executor reserves before work, checkpoints each iteration, records failure/interruption, enforces limits, and supports tracked cancellation/resume. |
| 6 | Comparison checks distinct run IDs, stored scenario text and canonical option meanings. Experimental factors are displayed per run. |
| 7 | Jointly empty categories are removed before degrees-of-freedom calculation; malformed counts fail validation. Insufficient categories return unavailable. Wilson margin is the half-width. |
| 8 | Counts mean responses exhibiting each of seven allowed labels, including zero. Fingerprints use completed runs with current evidence provenance and expose the included cohort. Intervals describe that sampled corpus/evaluator mix. |
| 9 | Experiment claims serialize pending-to-running transitions. Reservations immediately attach run IDs and states to manifests. Interrupted manifests reconcile at startup, including recoverable run-to-experiment links. |
| 10 | Allocator, validation and migration accept numeric suffixes of at least three digits, including 1000 and beyond. |
| 11 | Shared store lock serializes field-level updates. Execution snapshots preserve independently generated artifacts and cannot discard a longer persisted response sequence. |
| 12 | Typed nested response/summary/analyst validation; unique sequential option IDs and unique scenario IDs; query return annotation added. |
| 13 | Launch defaults to `127.0.0.1`. |
| 14 | Superseded for PDFs by browser HTML. HTML briefs, insight slides, comparisons and PowerPoint share a two-render concurrency limit outside the event loop. Cancelling a request retains its slot until the rendering thread finishes. |
| 15 | Laboratory exposes iterations and shuffling, uses consistent defaults, and shows planned runs and primary iteration totals. |
| 16 | JSON export includes the selected current insight and a complete persisted record containing stimulus, parameters, mappings and raw outputs. |
| 17 | Query/counterfactual/experiment launch returns promptly. Run cards show status/progress, poll while active, and expose cancel/resume. Laboratory links include failed/interrupted runs. |
| 18 | Readiness claims replaced with bounded evidence, persistence docs corrected, rendering-adapter exception documented, D11 and report integration aligned, trailing whitespace fixed in the working tree. |

## Verification

Focused tests exercise the reviewed evidence, storage, execution, reporting and boundary changes. The final focused batch passed 66 tests; two additional regressions for historical shuffled resume and interrupted-experiment recovery also passed. Ruff, working-tree whitespace, offline lock validation and documentation claims checks passed. After the LinkedIn slide addition and render-limit follow-up, the seven focused workflow tests passed, including a mixed-format concurrency regression that queues a third report while health checks remain responsive. Ryan subsequently ran `uv run pytest -q` locally and supplied the terminal result on 2026-09-14: **192 passed in 2.60s**. This records user-reported execution of the full suite after these changes; the assistant did not repeat it.

Desktop single-run and comparison previews and a 390px-wide single-run preview were inspected in the browser using constructed fixture data. Print/download controls were exercised; the downloaded HTML file was checked for complete content, inline print styles and absence of external script/style dependencies. The in-app browser did not expose a native print preview, so saved-PDF pagination and physical output remain unverified. No clinical or model-behavior conclusions follow from the synthetic preview.

Ruff and whitespace/lock/document checks are local checks. The original staged whitespace remains in the unchanged index; the working-tree fixes are intentionally unstaged.

## Operational limits

Use one application process for local store locks and task tracking. Keep a filesystem backup of results and experiment manifests; stop the application before restoring both directories together. Resume interrupted individual runs from their cards. An interrupted matrix exposes reserved runs; unstarted conditions require a new manifest.

Existing results and derived artifacts have not been deleted or automatically re-analyzed. Regeneration can use paid provider calls and remains a user action. The workbench measures responses under specified prompt conditions, not a validated general ethics score.
