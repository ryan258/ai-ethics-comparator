
# AI Ethics Comparator

## Purpose

This project examines how modern large language models handle impossible ethical choices. Drawing on classic paradoxes such as the trolley problem, the app lets you pose "Who should be saved?"-style dilemmas—older man vs. younger man, two people vs. one person, irreplaceable art vs. human life—and watch the justifications different models produce.

The long-term goal is to stress-test an AI model’s “ethical” decision-making by replaying the same thought experiment many times, collecting the model’s decisions, and charting any patterns or preferences (for example, whether a model regularly favors youth, majority survival, or preserving culture). Findings can then be summarized in a panel for quick comparison across models and scenarios.

## Current Experience

* **Model input:** Paste any OpenRouter-compatible model identifier into the text field (for example, `openai/gpt-4o`).
* **Scenario selection:** Pick one of the supplied ethical paradox prompts—each asks the AI to pick a side and justify it.
* **Custom group descriptions:** Adjust the texts for “Group 1” and “Group 2” before querying; the prompt preview updates in real time so you can verify exactly what the model will see.
* **Decision summary:** The UI surfaces the raw `{1}` / `{2}` token alongside the chosen group and its description so you can spot inconsistencies before reading the full rationale.
* **Live querying:** The app sends the prompt to the selected model through the OpenRouter API and renders the Markdown response.
* **Modular prompts:** Dilemmas live in `paradoxes.json`; add or edit entries to explore new “impossible choice” setups.

> **Note:** Batched experiments, tallying, and charting are on the roadmap. In the meantime, you can run manual passes from the UI or script your own loops against the `/api/query` endpoint to begin collecting data.

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

## Extending Toward Batch Testing

To move from single-run exploration to the envisioned multi-pass analysis:

1. Introduce a number input in the UI (default `10`) that lets you choose how many times to re-run a scenario against the model.
2. Build a script (Node or browser) that hits `/api/query` repeatedly with the selected `modelName`, `paradoxId`, count, and any custom group descriptions you’ve set.
3. Before saving output, ensure a `results/` directory exists (create if missing); stash each run inside a fresh child folder named like `[model-incrementer]` (for example, `openai-gpt-4o-001`), incrementing until an unused directory name is found.
4. Store the returned decisions and metadata (timestamps, raw output, prompt used) inside that run folder—CSV, JSON, charts, and summary Markdown all live together.
5. Aggregate counts for each decision or moral stance.
6. Visualize the distribution (bar chart, violin plot, etc.) and surface highlights in a “findings” panel within the UI.

> `results/` is already in `.gitignore`, so local experiments won’t clutter commits.

Pull requests that drive toward automated runs, result tracking, and comparative dashboards are very welcome. Let's see which ethical instincts our models really have.
