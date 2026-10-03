# Project roadmap

## Current remediation — implementation pending verification

The October review identified evidence-integrity, recovery, presentation, documentation, and accessibility defects. Changes now address shared measurement denominators; terminal-outcome preservation; conservative parsing; one prompt contract; bounded provider retries/deadlines/concurrency; manifest reconciliation; analysis coalescing; provenance; explicit report limitations; compatible-run selection; stable polling; and historical-record diagnostics.

Run `bash scripts/verify_local.sh` before treating this work as verified. See `COMPLETION_STATE.md` for the evidence boundary. Nothing in this file authorizes publication, paid analysis, or rewriting historical results.

## Next acceptance work

1. Resolve local verification failures from the remediation command.
2. Exercise one short run, cancellation/resume, one matrix continuation, and optional analysis with Ryan's chosen provider only when he wants to spend those calls.
3. Inspect browser printing and PPTX output with representative long responses, dark/light themes, and incomplete runs.
4. Use the keyboard/voice workflow to assess focus, history selection, and saved experiment setup. Automated checks are not assistive-technology acceptance.

## Bounded enhancements

- Improve scenario packs from observed use; keep authored dimension/rubric annotations distinguishable from validation. Do not require manual review of the entire library before personal use.
- Add alternate framing experiments as explicit new scenario revisions, preserving originals and reporting changed variables.
- Extend cohort filters when scenario/persona/evaluator mixtures obstruct interpretation.
- Consider splitting HTTP route registration only if it improves a specific maintenance task. The shared measurement boundary has priority over a broad framework restructure.
- Add provider cost estimates only with current price sources and explicit unknown-usage handling. Token counts alone are not a bill.

The personal workflow remains local, one process, Jinja2/HTMX, JSON storage. Additional infrastructure and commercial packaging are outside the current scope.
