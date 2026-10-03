# Execution contracts

- `AIService` owns transport retry, disables SDK retries, limits provider concurrency, and applies a total provider-call deadline. Query code never retries an exhausted transport operation. Structured-format rejection permits one prompt-only fallback; output correction uses a separate bounded reask budget.
- Authentication, quota, and unavailable-model failures stop queued iterations in that run. Already started work is drained and its successful outcomes remain checkpointed.
- Every terminal outcome, including undecided, is retained across resume. Interrupted attempt records are separate from terminal outcomes. Primary/reask/classifier and analyst/rubric calls retain available provenance; unknown usage remains unknown.
- `record_result` serializes snapshots and persistence under the run state lock. Storage uses atomic replacement. Manifests use serialized updates and derive statuses from linked run state.
- Shared provider limits include queries, classification, analysis, and rubric scoring. Identical in-flight analyses share a task. Shutdown drains run tasks and cancels/drains analysis before closing the client.
- The initial run request returns `202`; subsequent background failures are saved and shown on run cards. HTTP validation failures use proper error responses and a global HTMX error display.
- Browser changes require trusted Host/origin/fetch context. Headerless local CLI requests are supported. Bind to loopback and use one process.
- No startup auto-resume or automatic legacy re-analysis. Historical unknowns are preserved.
