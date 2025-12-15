# AI Ethics Comparator (Python/FastAPI)

A research tool for analyzing how large language models (LLMs) reason about ethical dilemmas. It supports both **trolley-style scenarios** (binary choices) and **open-ended ethical questions**.

## Core Features
*   **Arsenal Architecture**: Modular, dependency-injected design (FastAPI + HTMX).
*   **Dual Paradox Support**: Binary choices & open-ended scenarios.
*   **Deep Analysis**: "Moral Complexes" detection (Duty, Consequence, etc.) by an Analyst Agent.
*   **Persistence**: Run history saved to local JSON files.
*   **Reproducibility**: Experiments capture all parameters (temperature, full prompt, seeds).

## Quick Start

### Prerequisites
*   Python 3.10+
*   An OpenRouter API Key

### Installation

1.  **Clone & Setup**:
    ```bash
    git clone <repo>
    cd ai-ethics-comparator
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    ```

2.  **Configuration**:
    Create a `.env` file:
    ```env
    OPENROUTER_API_KEY=sk-or-your-key-here
    OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
    APP_BASE_URL=http://localhost:8000
    APP_NAME="AI Ethics Comparator"
    # optional:
    ANALYST_MODEL=provider/model-name
    ```

3.  **Run**:
    ```bash
    ./run_server.sh
    # OR
    source venv/bin/activate
    uvicorn main:app --reload
    ```

4.  **Access**: Open `http://localhost:8000`

## Project Structure

*   `main.py`: Fast API entry point & routing.
*   `lib/`: Core logic modules (Arsenal Strategy).
    *   `ai_service.py`: OpenRouter interaction.
    *   `analysis.py`: Insight generation & Moral Complexes.
    *   `query_processor.py`: Experiment execution engine.
    *   `storage.py`: Async filesystem result storage.
    *   `stats.py`: Statistical utilities.
*   `templates/`: Jinja2 templates (HTMX partials).
*   `static/`: CSS & assets (Candlelight theme).
*   `results/`: Local JSON storage for runs (gitignored).

## Usage

1.  **Configure**: Select a paradox and an AI model (or type any OpenRouter ID).
2.  **Run**: Set iterations (e.g., 5 or 10) and click "Run Experiment".
3.  **Analyze**: Click "View Analysis" on any result to generate an AI-powered breakdown of ethical frameworks used.
