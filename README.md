
# AI Ethics Comparator

## Purpose

This project examines how modern large language models handle impossible ethical choices. Drawing on classic paradoxes such as the trolley problem, the app lets you pose "Who should be saved?"-style dilemmas—older man vs. younger man, two people vs. one person, irreplaceable art vs. human life—and watch the justifications different models produce.

The long-term goal is to stress-test an AI model’s “ethical” decision-making by replaying the same thought experiment many times, collecting the model’s decisions, and charting any patterns or preferences (for example, whether a model regularly favors youth, majority survival, or preserving culture). Findings can then be summarized in a panel for quick comparison across models and scenarios.

## Current Experience

* **Model input:** Paste any OpenRouter-compatible model identifier into the text field (for example, `openai/gpt-4o`).
* **Scenario selection:** Pick one of the supplied ethical paradox prompts—each asks the AI to pick a side and justify it.
* **Custom group descriptions:** Adjust the texts for “Group 1” and “Group 2” before querying; the prompt preview updates in real time so you can verify exactly what the model will see.
* **Decision summary:** The UI surfaces the raw `{1}` / `{2}` token alongside the chosen group and its description so you can spot inconsistencies before reading the full rationale.
* **Iteration control:** Choose how many times to run the dilemma (default `10`). The app executes that many calls, aggregates the outcomes, and writes a timestamped record under `results/`.
* **Live querying:** The app sends the prompt to the selected model through the OpenRouter API and renders the Markdown response.
* **Modular prompts:** Dilemmas live in `paradoxes.json`; add or edit entries to explore new “impossible choice” setups.

> **Note:** Each batch run is saved locally—perfect for building your own analyses or dashboards on top of the captured JSON output.

## Tech Stack

* **Front end:** Vanilla HTML, CSS, and JavaScript (with `marked` for Markdown rendering).
* **Server:** Node.js + Express.
* **AI access:** OpenRouter using the `openai` SDK.
* **Config:** `.env` for the API key via `dotenv`.

## Getting Started

1. **Install dependencies**
   ```bash
   npm install
   ```
2. **Add your credentials** (`.env`)
   ```env
   OPENROUTER_API_KEY=sk-or-your-key
   ```
   Optional overrides:
   ```env
   OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
   APP_BASE_URL=http://localhost:3000
   APP_NAME="AI Ethics Comparator"
   ```
3. **Run the app**
   ```bash
   npm start
   ```
   _or_
   ```bash
   npm run dev
   ```
   Visit `http://localhost:3000`.

## Folder Overview

```
ai-ethics-comparator/
├── public/
│   ├── index.html        # UI layout
│   ├── style.css         # Minimal styling + Markdown rhythm controls
│   └── app.js            # Client logic, fetches, Markdown rendering
├── server.js             # Express server + API routes
├── aiService.js          # OpenRouter client wrapper
├── paradoxes.json        # Thought experiments / prompts
├── package.json          # Scripts and dependencies
└── ...
```

## Results Output

Every batch run creates a new folder under `results/` named `<model>-NNN` (for example, `openai-gpt-4o-001`). Each folder contains a `run.json` file with:

* The prompt that was sent (with your group text substitutions)
* The iteration count and per-group decision totals (counts + percentages)
* An array of iteration-level responses, including the raw `{1}` / `{2}` token, explanation, and timestamps

`results/` is already in `.gitignore`, so local experiments won’t clutter your commits.

## Extending Toward Batch Testing

The groundwork for multi-run analysis is in place. To take it further:

1. Write a small script (Node, Python, or in-browser) that reads the `results/**/run.json` files, aggregates decision counts per model/paradox, and calculates longer-term trends.
2. Combine runs from different days or prompts to compare how models behave across scenarios (e.g., heatmaps of `{1}` vs `{2}` rates).
3. Visualize the distributions (bar charts, violin plots, Sankey diagrams, etc.) to surface consistent preferences or anomalies.
4. Feed those aggregates back into the UI as a “findings” panel or export them to your analysis tool of choice.

Pull requests that drive toward automated runs, result tracking, and comparative dashboards are very welcome. Let's see which ethical instincts our models really have.
