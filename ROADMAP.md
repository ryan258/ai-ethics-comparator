# Roadmap

## Near Term

- **In-app findings panel:** Surface charts or tables derived from the latest run without leaving the UI.
- **Import previous runs:** Allow users to load existing `results/<model>-NNN/run.json` files back into the interface for review.
- **Result validation:** Flag iterations where the explanation contradicts the `{1}`/`{2}` token or omits a decision entirely.
- **Prompt presets UI:** Provide a lightweight editor to duplicate/edit `paradoxes.json` entries without touching the file manually.

## Upcoming

- **Visualization toolkit:** Generate comparative bar charts/heatmaps that span multiple runs and models (likely driven by a small Node script or in-browser aggregation).
- **CSV / Parquet exports:** Offer alternative output formats so results can flow directly into data tooling.
- **Scenario metadata:** Track categories (e.g. “age vs. role”, “one vs. many”) to enable grouped analytics across prompts.
- **Batch model runs:** Input a list of models and execute the same scenario across all of them automatically.

## Longer Term

- **Side-by-side model comparisons:** Render explanations from multiple models in a single view to examine divergent reasoning.
- **Web-based dashboard mode:** Optional mode that turns the app into an interactive explorer for aggregated data (filters, facets, time-series).
- **Plugin/API integration:** Expose an API endpoint or CLI to trigger runs remotely and push results into external systems.
- **Ethics taxonomy scoring:** Experiment with tagging explanations (e.g., utilitarian, deontological) via secondary classification to quantify ethical framing trends.
