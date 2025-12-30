# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## MISSION BRIEFING: AI Ethics Comparator

Research tool for analyzing how LLMs reason about ethical dilemmas. Two paradox types: trolley-type (binary choice with stats) and open-ended (qualitative analysis). FastAPI + HTMX frontend, JSON filesystem storage.

---

## Commands

**Run Dev:** `uvicorn main:app --reload`

**Run Prod:** `python main.py`

**Health Check:** `curl http://localhost:8000/health`

**Setup:**

```bash
pip install -r requirements.txt
# Create .env with OPENROUTER_API_KEY=sk-or-your-key
```

---

## Architecture: The Research Protocol

### Arsenal Strategy (Modular lib/)

**Backend Modules (Copy-Paste Ready):**

- `lib/validation.py` - Pydantic request/response models
- `lib/ai_service.py` - OpenRouter client with retry logic and dual API support
- `lib/storage.py` - Run persistence (filesystem JSON)
- `lib/query_processor.py` - Run execution with asyncio concurrency
- `lib/stats.py` - Statistical analysis (chi-square, Wilson CI, bootstrap, Cohen's h)

**Main Application:**

- `main.py` - Thin FastAPI routing layer (~250 lines)

**Frontend:**

- `templates/index.html` - Jinja2 + HTMX (no build steps)
- `static/style.css` - Candlelight Mode styling

**Data:**

- `paradoxes.json` - 12 scenarios (7 trolley, 5 open-ended)
- `results/` - Run archives (gitignored, auto-created)

### The Copy-Paste Test

- `lib/stats.py` - ✅ Pure Python, zero dependencies on project
- `lib/ai_service.py` - ✅ Only needs OpenAI SDK + config
- `lib/storage.py` - ✅ Only needs pathlib
- `lib/validation.py` - ✅ Only needs Pydantic

### No-Bloat Achieved

NO Docker. NO React. NO node_modules. NO microservices. NO build steps.
**Dependencies:** FastAPI, Uvicorn, Jinja2, OpenAI (Python SDK), WeasyPrint.

Stack: FastAPI + Jinja2 + HTMX + Pure CSS

---

## Critical Patterns (Mission Control Intel)

### Pattern 1: Asyncio Concurrency Limiting

**Location:** `lib/query_processor.py:66`

```python
class QueryProcessor:
    def __init__(self, ai_service, concurrency_limit: int = 2):
        self.ai_service = ai_service
        self.semaphore = asyncio.Semaphore(concurrency_limit)

    async def execute_run(self, config):
        async def run_iteration(iteration_number):
            async with self.semaphore:  # Max 2 concurrent
                response = await self.ai_service.get_model_response(...)
                return parsed_response
```

**Why:** Prevents OpenRouter rate limiting during batch operations. DO NOT remove or increase limit without testing.

### Pattern 2: Paradox Type Switching

**Source of Truth:** `paradoxes.json` - Each paradox has `"type": "trolley"` or `"type": "open_ended"`

**Critical Branches:**

- `lib/query_processor.py:95-125` - Response parsing logic switches on `paradox["type"]`
- `templates/index.html` - Frontend conditionally shows/hides group inputs

**Trolley type:**

- Expects `{1}`, `{2}`, `{3}`, or `{4}` decision tokens in response (N-way support)
- Parses to extract decision + explanation
- Aggregates statistics (counts, percentages)
- Renders CSS-based horizontal bar charts (no external dependencies)

**Open-ended type:**

- No token parsing
- Stores full response text
- No statistical aggregation
- Qualitative analysis focus

**Rule:** ALWAYS check `paradox["type"]` before processing responses.

### Pattern 3: Dual API Support

**Location:** `lib/ai_service.py:48-98`

Auto-selects OpenRouter API based on system prompt:

- **With system prompt:** Uses `chat.completions` with system message role
- **Without system prompt:** Uses `chat.completions` with user message only

**Why:** Enables ethical priming experiments while maintaining backwards compatibility.

### Pattern 4: Sequential Run IDs

**Location:** `lib/storage.py:25-51`

Run IDs format: `{modelName}-{sequentialNumber}`

Example: `anthropic-claude-3-5-sonnet-001`, `anthropic-claude-3-5-sonnet-002`

**Collision Prevention:** Scans existing runs, finds highest number, increments.

### Pattern 5: Retry with Exponential Backoff

**Location:** `lib/ai_service.py:103-175`

- MAX_RETRIES: 4 attempts
- Initial delay: 2 seconds
- Exponential backoff on 429 (rate limit)
- Specific error messages for common failures (billing, invalid model, auth)

---

## Run Data Schema (results/{runId}/run.json)

```python
{
  "runId": "anthropic-claude-3-5-sonnet-001",
  "timestamp": "2025-12-14T...",
  "modelName": "anthropic/claude-3.5-sonnet",
  "paradoxId": "autonomous_vehicle_equal_innocents",
  "paradoxType": "trolley",  # or "open_ended"
  "prompt": "...",           # exact text sent to AI
  "systemPrompt": "...",     # optional ethical priming
  "groups": {"group1": "...", "group2": "..."},
  "iterationCount": 20,
  "params": {                # full reproducibility
    "temperature": 1.0,
    "top_p": 1.0,
    "max_tokens": 1000,
    "seed": None,            # optional
    "frequency_penalty": 0,
    "presence_penalty": 0
  },
  "summary": {               # trolley-type only
    "total": 20,
    "group1": {"count": 15, "percentage": 75.0},
    "group2": {"count": 5, "percentage": 25.0},
    "undecided": {"count": 0, "percentage": 0.0}
  },
  "responses": [
    {
      "iteration": 1,
      "decisionToken": "{1}",  # trolley-type
      "group": "1",            # trolley-type
      "explanation": "...",    # trolley-type
      "response": "...",       # open-ended
      "raw": "...",
      "timestamp": "..."
    }
  ],
  "insights": [              # added by AI analysis feature
    {
      "timestamp": "...",
      "analystModel": "google/gemini-2.0-flash-001",
      "content": "..."
    }
  ]
}
```

**Rule:** DO NOT break this schema. Existing runs in the wild depend on it.

---

## Security Protocol

1. **CORS middleware** - Limited to APP_BASE_URL origin
2. **Pydantic validation** - All API inputs validated with strict models
3. **Regex validation** - Model names and paradox IDs sanitized
4. **Version header** - X-App-Version on all responses

**Rule:** ALL new API endpoints MUST use Pydantic models for validation.

---

## Common Missions

### Mission: Add New Paradox

Edit `paradoxes.json`:

```json
{
  "id": "your_paradox_id",
  "title": "Display Title",
  "type": "trolley", // or "open_ended"
  "promptTemplate": "Your prompt with {{GROUP1}} and {{GROUP2}} placeholders",
  "group1Default": "Default description",
  "group2Default": "Default description"
}
```

NO code changes needed. UI and backend auto-adapt.

### Mission: Add Generation Parameter

1. Update Pydantic model in `lib/validation.py`:

```python
class GenerationParams(BaseModel):
    # existing...
    new_param: float = Field(default=0, ge=0, le=1)
```

2. Update `lib/ai_service.py` request_params building (line 48-60)
3. Update `lib/query_processor.py` params dict (line 111-117)
4. Add UI input in `templates/index.html` Advanced Settings

### Mission: Add API Endpoint

**Pattern:**

```python
@app.post("/api/endpoint")
async def my_endpoint(request: MyRequestModel):
    try:
        # ... business logic using arsenal modules
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

---

## API Endpoints

- `GET /` - Main application page (HTMX)
- `GET /health` - Health check with version
- `GET /api/paradoxes` - List scenarios
- `POST /api/query` - Execute experimental run
- `POST /api/insight` - Generate AI analysis of run
- `GET /api/runs` - List all runs (metadata)
- `GET /api/runs/{run_id}` - Get full run data

---

## Known Issues (Mission Hazards)

### OpenAI SDK async client

- Uses `AsyncOpenAI` for non-blocking requests
- All AI calls must be awaited
- Semaphore controls concurrency

### No automated tests

- Manual testing via browser and curl
- Future: pytest integration planned

### HTMX state management

- Server-side rendering for most UI
- Zero client-side JavaScript (pure CSS visualizations)
- CSS-based horizontal bar charts for decision distributions

### High "Undecided" rate

- Expected for some models (they don't understand `{1}/{2}` format)
- NOT a bug - document as model limitation

---

## Troubleshooting

**Server won't start:**

- Check `.env` exists with valid OPENROUTER_API_KEY
- Verify Python 3.9+ installed
- Run `pip install -r requirements.txt`
- Check port 8000 not in use

**Results not saving:**

- Check `results/` directory writable
- Verify disk space

**API errors:**

- 429 (rate limit): Automatic retry with backoff (wait)
- 401 (auth): Check OPENROUTER_API_KEY in .env
- 404 (model): Verify model name at openrouter.ai/models

---

## Code Review Protocol (Mission Control)

When asked to review code, output format:

**FINAL VERDICT:** [SHIP IT 🚢] or [HOLD 🛑]

**Summary:**

- Performance: [changes]
- Correctness: [changes]
- Readability: [changes]

**Issues:** [If HOLD, list blocking bugs]

**Action:** "Ready to commit" or specific fix instructions.

---

## Tone & Role

You are **Mission Control**. User is the **Pilot**.

- Be concise
- Use "we"
- Prioritize ETC (Easier To Change) over "Perfect"
- Keep changes minimal and reversible
- Focus on what matters for research reproducibility

---

## Visual Protocol: Candlelight Mode

- Background: Off-Black (#121212)
- Text: Warm Beige (#EBD2BE)
- Accent: Muted Lavender (#A6ACCD)
- Success: Muted Green (#98C379)
- Error: Muted Red (#E06C75)

---

## File Map

**Arsenal Modules (lib/):**

- `validation.py` - Pydantic models
- `ai_service.py` - OpenRouter client
- `storage.py` - Run persistence
- `query_processor.py` - Execution logic
- `stats.py` - Statistical functions

**Application:**

- `main.py` - FastAPI routes (~250 lines)
- `templates/index.html` - HTMX frontend
- `static/style.css` - Candlelight styling

**Data:**

- `paradoxes.json` - 12 scenarios
- `results/` - Run archives (gitignored)
- `.env` - Environment variables

**Docs:**

- `README.md` - Quick start
- `HANDBOOK.md` - Research guide
- `ROADMAP.md` - Development history
