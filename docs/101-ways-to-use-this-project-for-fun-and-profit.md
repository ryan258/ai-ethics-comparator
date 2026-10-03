# Practical uses and current operating recipes

The earlier “101 ways” guide is retired. It mixed speculative commercial uses with obsolete synchronous API and server-PDF examples. Its original text is preserved in [the historical idea catalogue](historical/101-ways-original.md) and Git history. Use this project's personal, local workflow and the current [handbook](../HANDBOOK.md).

Useful bounded experiments:

- Compare configured models on the same saved scenario revision.
- Compare personas while holding scenario, generation parameters, and ordering policy constant.
- Compare recorded option-order settings using an explicit shuffle seed.
- Inspect undecided and malformed output alongside decided responses.
- Explore a linked hypothetical evidence intervention using the dedicated counterfactual report.
- Revisit a saved experiment setup without retyping models and scenarios.
- Export saved evidence without requesting another model interpretation.

Run on loopback:

```bash
uv run uvicorn main:app --host 127.0.0.1 --port 8000
```

Use the UI to create a run and select its report. Creation returns before execution is finished; progress/status comes from the saved run. Download HTML as `.html`, or use browser Print / Save as PDF to create a PDF. The project does not provide the removed server-PDF smoke script.

For old records, use `uv run python scripts/preview_legacy_runs.py`. It preserves originals and exposes missing facts. Model analysis is optional and costs calls; exports and previews do not.
