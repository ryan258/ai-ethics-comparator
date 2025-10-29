# AI Ethics Comparator

## Overview

AI Ethics Comparator probes how contemporary large language models navigate trolley-style dilemmas. For every run you pick a model, describe two groups of pedestrians, and the app repeatedly asks the model which group to sacrifice. Results are aggregated, saved locally, and rendered in the UI so you can spot patterns such as consistent biases or contradictory reasoning.

## Key Features

- **Model-agnostic input:** Paste any OpenRouter-compatible identifier (e.g. `openai/gpt-4o`) to target the model you want to examine.
- **Prompt templating:** Every scenario is Markdown-based with placeholders for “Group 1” and “Group 2”. The preview updates live as you edit descriptions.
- **Batch interrogation:** Choose 1–50 iterations (defaults to 10). The server executes that many back-to-back calls, captures the raw `{1}`/`{2}` token, and logs the explanation for each pass.
- **Instant summary:** The UI surfaces aggregated counts and percentages per group, followed by a detailed breakdown of every iteration.
- **Structured run logs:** Each batch is written to `results/<model>-NNN/run.json`, making it trivial to plug the data into your own analyses or dashboards.

## Quick Start

```bash
npm install
```

Create `.env` with your OpenRouter credentials (copy `.example.env` if you like):

```env
OPENROUTER_API_KEY=sk-or-your-key
# optional:
# OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
# APP_BASE_URL=http://localhost:3000
# APP_NAME="AI Ethics Comparator"
```

Launch the app:

```bash
npm run dev   # nodemon auto-restarts on changes
# or npm start for a one-off process
```

Open `http://localhost:3000` in your browser.

## Using the App

1. **Select a model.** Paste the OpenRouter slug (e.g. `anthropic/claude-3.5-sonnet`).
2. **Pick a scenario.** Scenarios live in `paradoxes.json`; each expresses the dilemma in Markdown.
3. **Describe the groups.** Edit the “Group 1” and “Group 2” text areas. The prompt preview updates instantly.
4. **Set iterations.** Choose how many times to rerun the prompt (1–50, defaults to 10).
5. **Ask the model.** The server sends all iterations, compiles the counts, and returns the full prompt plus every response.
6. **Review results.** The summary card shows the raw `{n}` token, total counts, percentages, and the filesystem path where the run was stored.
7. **Inspect run logs.** Each run is stored under `results/<model>-NNN/run.json` with fields:
   - `prompt`, `iterationCount`, and `groups`
   - `summary` counts and percentages per group
   - `responses[]` with the iteration index, `{n}` token, explanation, raw text, and timestamp

`results/` is ignored by git, so local experimentation stays out of version control.

## Project Structure

```
ai-ethics-comparator/
├── public/
│   ├── index.html        # UI layout
│   ├── style.css         # Styling and markdown rhythm
│   └── app.js            # Client logic, fetches, markdown rendering
├── paradoxes.json        # Scenario templates with group defaults
├── aiService.js          # OpenRouter client wrapper
├── server.js             # Express API, iteration engine, result persistence
├── results/              # Local run archives (gitignored)
├── package.json          # Scripts and dependencies
└── ...
```

## Available Scripts

- `npm run dev` – start the server with nodemon (auto-restart on file changes).
- `npm start` – launch the server once with Node.

## Tech Stack

- **Front end:** Vanilla HTML, CSS, JavaScript + `marked` for Markdown rendering.
- **Back end:** Node.js, Express, filesystem persistence.
- **AI access:** OpenRouter via the official `openai` SDK.

## Next Steps

Roadmap items—such as multi-model comparisons, visualization overlays, and richer analytics—are tracked in [`ROADMAP.md`](ROADMAP.md). Contributions and ideas are welcome.
