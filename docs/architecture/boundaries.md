# Architecture boundaries

## Core and adapters

`lib/measurements.py` is a pure typed read/measurement boundary. Counts come from recorded responses, not cached summaries. `RunRecord` validates shape and semantic relationships; missing historical facts remain missing. Version 2 adds stricter completion and iteration requirements.

`lib/query_processor.py`, analysis, and experiment orchestration consume injected provider/storage adapters. Core modules never import `main.py`, FastAPI, routers, or HTTP request objects. Jinja renderers, report composition, and Markdown view formatting live under `presentation/`; they receive paths/data and depend on the reusable core. Nothing in `lib/` imports this presentation layer. The internal renderer import paths changed from `lib.reporting`, `lib.view_models`, and `lib.executive_reporting` to their `presentation` equivalents; in-repository callers and tests are updated.

`main.py` owns HTTP validation, task wiring, and template responses. Provider JSON and SDK adapter boundaries retain `Any` for variable external extensions; the shared measurement model is narrow and independently type-checked.

## Provider and persistence

`AIService.get_model_response` returns text plus usage/provider metadata. Missing usage is marked explicitly. Retry and deadline policy lives in this adapter, including its shared semaphore. Callers may correct unusable output with a bounded new prompt; they must not restart transport retries.

`RunStorage` and `ExperimentStorage` own writes. Paths are validated before access. Run reads validate the persisted contract without rewriting the source. `experiment_state.reconcile_experiment` updates condition state atomically and derives manifest status. These guarantees assume one process.

## Evidence and interpretation

`prompt_contract.single_choice_contract` is the only current execution/presentation output contract. The library contains scenario text/options; legacy output boilerplate has been removed in a new revision. Existing saved prompts are immutable historical evidence.

Analysis selection requires matching evidence hash, version, and a valid analyst schema. The fingerprint reports exclusions and cohort composition. Ordinary comparisons require identical recorded stimulus and option meanings. Linked counterfactuals use a separate descriptive view.

Report outcome counts, percentages, requested/completed status, and undecided totals come from `build_run_measurements`. Keyword labels use response text only. Model interpretations are labeled and cannot establish deployment suitability. Scenario overrides may add limitations, not measured conclusions.

## Browser output

Both report renderers autoescape external text. `safe_markdown` escapes before rendering and removes links/images. The raw JSON HTMX control must retain `hx-swap="textContent"`; content type alone does not prevent HTMX from interpreting model output as markup.

Run polling pauses while details/dialogs or focused controls are in use. Experiment progress swaps only its fragment. Errors are announced in an alert region, and controls have visible focus styling.
