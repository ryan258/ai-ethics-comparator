# AI Ethics Comparator

## Overview

AI Ethics Comparator is a comprehensive research tool for analyzing how large language models reason about ethical dilemmas. The application supports both **trolley-style scenarios** (binary choice between two groups) and **open-ended ethical questions**, allowing researchers to probe AI decision-making across a wide range of moral frameworks.

For each run, you select a model, configure the scenario, and optionally add ethical priming through system prompts. The tool executes multiple iterations, aggregates results with statistical summaries and visualizations, and provides a complete research dashboard for browsing and exporting past experiments.

## Key Features

### Core Functionality
- **Dual Paradox Support:** Test models on both trolley-type dilemmas (A vs B choices) and open-ended ethical scenarios
- **Model-Agnostic:** Compatible with any OpenRouter model (GPT-4, Claude, Gemini, Llama, etc.)
- **Batch Testing:** Run 1–50 iterations per scenario to identify consistency and patterns
- **Ethical Priming:** Add system prompts to test how different moral frameworks (utilitarian, deontological, etc.) influence responses

### Advanced Features
- **Batch Model Runner:** Select multiple models and run the same scenario across all of them simultaneously with real-time progress tracking
- **Side-by-Side Comparison:** Compare 2-3 runs in split-screen view with automated Chi-square statistical testing for trolley-type runs
- **AI Insight Summary:** Generate AI-powered analysis of run results, automatically detecting ethical frameworks, consistency patterns, and key insights
- **Results Dashboard:** Browse, filter, and view all past experimental runs in a dedicated Results tab
- **Data Export:** Export runs to CSV or JSON format, with batch export capability for all runs at once
- **Visual Analytics:** Automatic bar charts show decision distribution for trolley-type scenarios
- **Statistical Validation:** Chi-square tests with p-values to determine if decision distributions are statistically significant
- **Undecided Detection:** Iterations where the AI fails to choose are flagged with ⚠️ warnings
- **Enhanced Error Reporting:** Specific error messages for API issues (rate limits, invalid models, billing problems, etc.)

### User Experience
- **Live Prompt Preview:** See exactly what the AI will receive as you edit scenarios
- **Session Persistence:** Your last-used model is remembered between sessions
- **Clear Run Button:** Quickly reset results to start fresh
- **Responsive UI:** Tab-based interface with Query and Results views

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

### Query Tab (Running Experiments)

1. **Select a model.** Enter or select an OpenRouter model identifier (e.g., `anthropic/claude-3.5-sonnet`, `openai/gpt-4o`)
   - **Batch Mode:** Enable "Batch mode" checkbox to select multiple models and run them all sequentially with progress tracking
2. **Pick a scenario.** Choose from 12 built-in ethical paradoxes:
   - **7 Trolley-Type Scenarios:** Binary choices between two groups (younger vs. older, criminal vs. surgeon, etc.)
   - **5 Open-Ended Scenarios:** Complex ethical questions (white lies, privacy vs. security, resource allocation, etc.)
3. **Configure the scenario:**
   - For trolley-type: Edit Group 1 and Group 2 descriptions (the UI shows/hides these automatically)
   - For open-ended: The prompt is fixed (no group editing needed)
4. **Set iterations.** Choose 1–50 iterations (default: 10). More iterations = better statistical confidence.
5. **(Optional) Add system prompt.** Expand "Advanced Settings" to add ethical priming:
   - Example: `"You are a strict utilitarian who prioritizes the greatest good for the greatest number."`
   - Example: `"You are a deontologist who believes in absolute moral rules."`
6. **Ask the model.** Click "Ask the Model" to run all iterations
7. **Review results:**
   - **Summary Card:** Shows run ID, model, iteration count, and decision breakdown with percentages
   - **Visual Chart:** Bar chart displays decision distribution (trolley-type only)
   - **Iteration Details:** Expand to see every individual response with explanations
   - **Undecided Warning:** Responses without valid `{1}` or `{2}` tokens are flagged with ⚠️
8. **Clear results.** Use the "Clear Run" button to reset and start fresh

### Results Tab (Browsing Past Runs)

1. **Switch to Results tab** to see all past experimental runs
2. **Browse runs.** Each card shows:
   - Run ID (model name + sequential number)
   - Model used
   - Paradox tested
   - Number of iterations
   - Timestamp
3. **Compare runs.** Click "Enable Compare Mode" to select 2-3 runs for side-by-side comparison
   - Automatically runs Chi-square test for trolley-type runs
   - Displays p-values and statistical significance
   - Shows charts side-by-side for easy comparison
4. **View run details.** Click any run to see full results with summary, chart, and iteration details
5. **Generate AI Insights.** Click "Generate AI Insight Summary" to get automated analysis of the run
   - Choose your analyst model (defaults to `google/gemini-2.0-flash-001`)
   - Identifies dominant ethical framework
   - Analyzes common justifications and reasoning patterns
   - Detects contradictions and consistency issues
6. **Export data:**
   - **Export to CSV:** Individual run in CSV format
   - **Export to JSON:** Individual run in JSON format
   - **Export All:** Batch export all runs as a single JSON file
7. **Return to list.** Use "← Back to List" to browse other runs

### Data Persistence

Each run is automatically saved to `results/<model>-NNN/run.json` with complete data:
- `runId`, `timestamp`, `modelName`, `paradoxId`, `paradoxType`
- `prompt` (the exact text sent to the AI)
- `systemPrompt` (if ethical priming was used)
- `groups` (Group 1 and Group 2 descriptions)
- `iterationCount`
- `summary` (aggregated counts and percentages)
- `responses[]` (every iteration with decision token, group choice, explanation, raw text, and timestamp)

The `results/` directory is gitignored, keeping your experiments local.

## Project Structure

```
ai-ethics-comparator/
├── public/
│   ├── index.html        # UI layout with Query and Results tabs
│   ├── style.css         # Styling and markdown rhythm
│   └── app.js            # Client logic: tabs, results dashboard, charts, CSV export
├── paradoxes.json        # 12 ethical scenarios (7 trolley-type, 5 open-ended)
├── aiService.js          # OpenRouter client with dual API support
├── server.js             # Express API with /query and /runs endpoints
├── results/              # Local run archives (gitignored, auto-created)
├── package.json          # Scripts and dependencies
├── README.md             # This file
├── ROADMAP.md            # Development roadmap and future features
├── HANDBOOK.md           # Comprehensive user guide
└── ...
```

## Available Scripts

- `npm run dev` – Start server with nodemon (auto-restart on file changes)
- `npm start` – Launch server once with Node

## Tech Stack

- **Front-end:** Vanilla HTML, CSS, JavaScript
  - `marked.js` for Markdown rendering
  - `Chart.js` for data visualization
- **Back-end:** Node.js, Express
  - Filesystem-based persistence (JSON)
  - RESTful API architecture
- **AI Integration:** OpenRouter via official `openai` SDK
  - Supports both `responses.create` and `chat.completions` APIs
  - Compatible with 100+ models (GPT, Claude, Gemini, Llama, Mistral, etc.)

## API Endpoints

### `GET /api/paradoxes`
Returns the list of available ethical scenarios from `paradoxes.json`.

### `POST /api/query`
Executes a batch of iterations for a given model and scenario.

### `POST /api/insight`
Generates AI-powered analysis of a run's results.

**Request body:**
```json
{
  "modelName": "anthropic/claude-3.5-sonnet",
  "paradoxId": "trolley_problem",
  "groups": {
    "group1": "A 20-year-old who recently committed a crime",
    "group2": "A 55-year-old community volunteer"
  },
  "iterations": 10,
  "systemPrompt": "You are a utilitarian." // optional
}
```

**Response:** Complete run data with summary and all iteration responses.

### `POST /api/insight`
Generates AI-powered insight summary for a run.

**Request body:**
```json
{
  "runData": { /* complete run.json data */ },
  "analystModel": "google/gemini-2.0-flash-001" // optional, defaults to gemini-2.0-flash
}
```

**Response:**
```json
{
  "insight": "Comprehensive analysis text...",
  "model": "anthropic/claude-3.5-sonnet"
}
```

### `GET /api/runs`
Returns metadata for all past runs (sorted by timestamp, newest first).

### `GET /api/runs/:runId`
Returns complete data for a specific run by ID.

## Research Use Cases

This tool is designed for researchers studying:

1. **AI Alignment:** How do models make ethical decisions by default?
2. **Consistency Testing:** Do models give the same answer across multiple iterations?
3. **Bias Detection:** Are there systematic patterns in how models value different demographics?
4. **Priming Effects:** How do system prompts influence moral reasoning?
5. **Cross-Model Comparison:** How do different AI systems approach the same dilemma?
6. **Framework Analysis:** Do models exhibit utilitarian, deontological, or virtue ethics patterns?
7. **Statistical Validation:** Use Chi-square tests to determine if differences between runs are statistically significant
8. **Large-Scale Studies:** Run batch experiments across multiple models simultaneously for comprehensive comparative analysis

## Contributing

Contributions are welcome! See [`ROADMAP.md`](ROADMAP.md) for planned features. Areas of interest:
- Additional ethical scenarios
- Search/filter functionality for Results tab
- Advanced statistical analysis (confidence intervals, consistency metrics)
- Prompt management UI
- Dark mode and UI enhancements

## License

[Add your license here]

## Documentation

- **README.md** (this file) – Quick start and technical overview
- **HANDBOOK.md** – Comprehensive user guide with research methodology and best practices
- **ROADMAP.md** – Development roadmap and future enhancements
