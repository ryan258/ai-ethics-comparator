"""
AI Ethics Comparator - Main Server
Thin routing layer using Arsenal Strategy modules
"""

import os
import json
from pathlib import Path
from datetime import datetime
import re
import random

from dotenv import load_dotenv
# Load environment immediately - MUST be before any lib imports that use config
load_dotenv()

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse, Response
import io
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from typing import Callable, Awaitable

# Arsenal modules
from lib.validation import QueryRequest, InsightRequest
from lib.ai_service import AIService
from lib.storage import RunStorage
from lib.query_processor import QueryProcessor
from lib.analysis import AnalysisEngine, AnalysisConfig
from lib.view_models import safe_markdown, fetch_recent_run_view_models
from lib.paradoxes import extract_scenario_text, get_paradox_by_id, load_paradoxes
from lib.reporting import ReportGenerator

# Global services
report_generator = ReportGenerator(templates_dir="templates")

# Logger setup
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Config
from lib.config import AppConfig

# Load and validate config
try:
    config = AppConfig.load()
    config.validate_secrets()
except ValueError as e:
    import sys
    logger.critical(str(e))
    sys.exit(1)

logger.info(f"Starting {config.APP_NAME} v{config.VERSION}")

# Initialize services
ai_service = AIService(
    api_key=str(config.OPENROUTER_API_KEY), # Validated above, safe cast
    base_url=config.OPENROUTER_BASE_URL,
    referer=config.APP_BASE_URL,
    app_name=config.APP_NAME
)

storage = RunStorage(str(config.results_path))
query_processor = QueryProcessor(ai_service, concurrency_limit=config.AI_CONCURRENCY_LIMIT)
# AnalysisEngine no longer needs config, just ai_service
analysis_engine = AnalysisEngine(ai_service)

# FastAPI setup
app = FastAPI(title=config.APP_NAME, version=config.VERSION)

# Templates
templates = Jinja2Templates(directory="templates")
# Use the centralized safe markdown filter
templates.env.filters['markdown'] = safe_markdown

# Paradoxes data path (used across handlers)
PARADOXES_PATH = Path(__file__).parent / "paradoxes.json"

# Static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[config.APP_BASE_URL],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-App-Version"],
)


# Middleware to add version header
@app.middleware("http")
async def add_version_header(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    response: Response = await call_next(request)
    response.headers["X-App-Version"] = config.VERSION
    return response


# Routes

@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    """Serve main application page"""
    try:
        paradoxes = load_paradoxes(PARADOXES_PATH)
    except Exception as e:
        logger.error(f"Failed to load paradoxes: {e}")
        # Critical failure - UI cannot function without paradoxes
        raise HTTPException(
            status_code=500, 
            detail="Failed to load paradox definitions. Please check server logs."
        )
        
    # Load recent runs for persistence using centralized helper
    recent_run_contexts = await fetch_recent_run_view_models(
        storage,
        paradoxes,
        config.ANALYST_MODEL
    )

    # Select random paradox for initial display
    initial_paradox = None
    initial_scenario_text = ""
    if paradoxes:
        initial_paradox = random.choice(paradoxes)
        initial_scenario_text = extract_scenario_text(initial_paradox.get("promptTemplate", ""))

    return templates.TemplateResponse("index.html", {
        "request": request, 
        "paradoxes": paradoxes,
        "models": config.AVAILABLE_MODELS,
        "default_model": config.DEFAULT_MODEL,
        "recent_run_contexts": recent_run_contexts,
        "initial_paradox": initial_paradox,
        "initial_scenario_text": initial_scenario_text,
        "max_iterations": config.MAX_ITERATIONS
    })


@app.get("/health")
async def health_check() -> dict:
    """Health check endpoint"""
    return {
        "status": "healthy",
        "version": config.VERSION,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "uptime": "N/A"  # Can add process uptime if needed
    }


@app.get("/api/paradoxes")
async def get_paradoxes() -> list:
    """Get available paradoxes"""
    try:
        paradoxes = load_paradoxes(PARADOXES_PATH)
        return paradoxes
    except Exception as e:
        logger.error(f"Failed to read paradoxes: {e}")
        raise HTTPException(status_code=500, detail="Failed to read paradoxes.")


@app.get("/api/fragments/paradox-details")
async def get_paradox_details(request: Request, paradoxId: str) -> HTMLResponse:
    """Get HTML fragment for paradox details"""
    try:
        paradoxes = load_paradoxes(PARADOXES_PATH)
        paradox = get_paradox_by_id(paradoxes, paradoxId)

        if not paradox:
            return HTMLResponse(
                "<div>Paradox not found</div>",
                status_code=404
            )

        # Pre-compute scenario text safely
        scenario_text = extract_scenario_text(paradox.get("promptTemplate", ""))

        return templates.TemplateResponse("partials/paradox_details.html", {
            "request": request,
            "paradox": paradox,
            "scenario_text": scenario_text
        })
    except Exception as e:
        logger.error(f"Failed to get paradox details: {e}")
        return HTMLResponse(
            "<div>Error loading details</div>",
            status_code=500
        )


@app.get("/api/runs")
async def list_runs() -> list:
    """List all runs (metadata only)"""
    try:
        runs = await storage.list_runs()
        return runs
    except Exception as e:
        logger.error(f"Failed to list runs: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve runs.")


@app.get("/api/runs/{run_id}")
async def get_run(run_id: str) -> dict:
    """Get specific run by ID"""
    try:
        run = await storage.get_run(run_id)
        return run
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Run not found.")
    except Exception as e:
        logger.error(f"Failed to get run {run_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve run data.")


@app.post("/api/query")
async def execute_query(request: Request, query_request: QueryRequest) -> dict:
    """Execute experimental run"""
    """Execute experimental run"""
    try:
        # Load paradox
        paradoxes = load_paradoxes(PARADOXES_PATH)
        paradox = get_paradox_by_id(paradoxes, query_request.paradox_id)

        if not paradox:
            raise HTTPException(status_code=404, detail=f"Paradox '{query_request.paradox_id}' not found")

        # Validate iterations against config limit
        req_iterations = query_request.iterations or 10
        if req_iterations > config.MAX_ITERATIONS:
            raise HTTPException(
                status_code=400, 
                detail=f"Iterations {req_iterations} exceeds limit of {config.MAX_ITERATIONS}"
            )

        # Execute run
        from lib.query_processor import RunConfig

        # Create typed run configuration
        run_config = RunConfig(
            modelName=query_request.model_name,
            paradox=paradox,
            option_overrides=[opt.dict() for opt in query_request.option_overrides.options] if query_request.option_overrides and query_request.option_overrides.options else None,
            iterations=query_request.iterations or 10,
            systemPrompt=query_request.system_prompt or "",
            params=query_request.params.dict() if query_request.params else {}
        )

        run_data = await query_processor.execute_run(run_config)

        # Generate unique run ID and save
        run_id = await storage.generate_run_id(query_request.model_name)
        run_data["runId"] = run_id

        await storage.save_run(run_id, run_data)

        # Check for HTMX
        if request.headers.get("HX-Request"):
            # Return an HTML fragment for the results stream
            # defined in lib/view_models.py
            from lib.view_models import RunViewModel
            
            vm = RunViewModel.build(run_data, paradox)
            vm["config_analyst_model"] = config.ANALYST_MODEL
            
            return templates.TemplateResponse("partials/result_item.html", {
                "request": request,
                "ctx": vm
            })

        return run_data
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Query execution failed: {e}")
        error_str = str(e).lower()
        if "401" in error_str or "unauthorized" in error_str:
            raise HTTPException(status_code=401, detail="Invalid API Key or Unauthorized.")
        elif "429" in error_str or "rate limit" in error_str:
            raise HTTPException(status_code=429, detail="Rate limit exceeded. Try fewer iterations.")
        elif "insufficient_quota" in error_str or "quota" in error_str:
            raise HTTPException(status_code=402, detail="Insufficient API credits.")

        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/api/insight")
async def generate_insight(request: InsightRequest) -> dict:
    """Generate AI insight summary"""
    try:
        model_to_use = request.analystModel or config.ANALYST_MODEL
        
        cfg = AnalysisConfig(
            run_data=request.runData,
            analyst_model=model_to_use
        )
        
        insight_data = await analysis_engine.generate_insight(cfg)

        # Save insight to run.json if runId provided
        if "runId" in request.runData:
            try:
                # We need to fetch, append, and save.
                # Since storage.update_run is now available, we should use it if we implemented it properly.
                # But let's stick to get/save pattern for now to be safe with existing logic
                # Actually storage.update_run was implemented to do partial updates?
                # The prompt implemented update_run to update the file content.
                # But we need to append to a list. Does update_run handle list appending? No.
                # So we must get, modify, save.
                
                existing_run = await storage.get_run(request.runData["runId"])
                if "insights" not in existing_run:
                    existing_run["insights"] = []
                existing_run["insights"].append(insight_data)
                
                # Use update_run just to save the whole blob again? Or save_run.
                # save_run overwrites.
                await storage.save_run(request.runData["runId"], existing_run)
            except Exception as save_error:
                logger.error(f"Error saving insight: {save_error}")

        return {"insight": insight_data["content"], "model": model_to_use}
    except Exception as e:
        logger.error(f"Insight generation failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/api/runs/{run_id}/analyze")
async def analyze_run(request: Request, run_id: str, regenerate: bool = False) -> HTMLResponse:
    """Generate and return analysis for a run (HTMX plain text/html)"""
    model_to_use = config.ANALYST_MODEL  # Initialize early for error handler
    try:
        # Get form data if present
        form_data = await request.form()
        requested_analyst = form_data.get("analyst_model")

        # Validate analyst model name
        if requested_analyst and not re.match(r'^[a-z0-9\-_/:.]+$', requested_analyst, re.IGNORECASE):
             return HTMLResponse("<div class='error'>Invalid model name format</div>", status_code=400)

        run_data = await storage.get_run(run_id)
        
        # Check cache (unless forcing regeneration)
        if not regenerate and "insights" in run_data and len(run_data["insights"]) > 0:
            insight = run_data["insights"][-1]
            cached_model = insight.get("analystModel")
            
            if not requested_analyst or (requested_analyst == cached_model):
                content = insight["content"]
                # Normalize legacy string content
                if isinstance(content, str):
                    content = {"legacy_text": content}

                return templates.TemplateResponse("partials/analysis_view.html", {
                    "request": request,
                    "insight": content,
                    "model": cached_model,
                    "cached": True,
                    "run_id": run_id,
                    "run_data": run_data,
                })

        # Generate new insight
        # Validate model selection for safety
        model_to_use = requested_analyst or config.ANALYST_MODEL
        if not model_to_use or not re.match(r'^[a-z0-9\-_/:.]+$', model_to_use, re.IGNORECASE):
             raise ValueError("Invalid analyst model name")
        
        cfg = AnalysisConfig(
            run_data=run_data,
            analyst_model=model_to_use
        )
        
        insight_data = await analysis_engine.generate_insight(cfg)

        # Save
        if "insights" not in run_data:
            run_data["insights"] = []
            
        run_data["insights"].append(insight_data)
        await storage.save_run(run_id, run_data)

        return templates.TemplateResponse("partials/analysis_view.html", {
            "request": request,
            "insight": insight_data["content"],
            "model": model_to_use,
            "cached": False,
            "run_id": run_id,
            "run_data": run_data,
        })
        
    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        error_html = f"""
        <div class="analysis-content">
            <div class="dashboard-card" style="border-color: var(--accent-danger); color: var(--accent-danger); text-align: center; padding: 2rem;">
                <h3 style="margin-bottom: 1rem; border-color: var(--accent-danger);">analysis failed</h3>
                <p style="opacity: 0.8; margin-bottom: 1.5rem;">{str(e)}</p>
                <div style="font-size: 0.8rem; opacity: 0.6; margin-bottom: 1.5rem;">
                    The Analyst Model ({model_to_use}) encountered an error.<br>
                    Try switching to a different model or check your API limits.
                </div>
                
                <!-- Retry Form -->
                <div class="analysis-input-group" style="margin-bottom: 0;">
                    <label for="retry-model-{run_id}" class="analysis-input-label" style="color: var(--text-color);">Try Another Model:</label>
                    <input type="text" name="analyst_model" id="retry-model-{run_id}" value="{model_to_use}" 
                           class="analysis-input-field" style="border-color: var(--accent-danger);">
                </div>
                
                <button class="btn btn-primary" 
                        hx-post="/api/runs/{run_id}/analyze" 
                        hx-include="#retry-model-{run_id}"
                        hx-target="#analysis-content-{run_id}"
                        hx-swap="innerHTML"
                        hx-indicator="#retry-loading-{run_id}">
                    Retry Analysis
                </button>
                <div id="retry-loading-{run_id}" class="htmx-indicator" style="margin-top: 0.5rem; font-size: 0.8rem; color: var(--text-color);">
                    Retrying...
                </div>
            </div>
        </div>
        """
        return HTMLResponse(error_html, status_code=200) # Return 200 to allow HTMX to swap content






@app.get("/api/runs/{run_id}/pdf")
async def download_pdf_report(run_id: str) -> StreamingResponse:
    """Generate and download PDF report"""
    # Security: Validate run_id to prevent path traversal
    if not run_id or "/" in run_id or ".." in run_id or "\\" in run_id:
        raise HTTPException(status_code=400, detail="Invalid run_id")
        
    try:
        # Load Data
        run_data = await storage.get_run(run_id)
        paradoxes = load_paradoxes(PARADOXES_PATH)
        paradox = get_paradox_by_id(paradoxes, run_data["paradoxId"])
        
        if not paradox:
             raise HTTPException(status_code=404, detail="Paradox definition not found")

        # Get latest insight if available
        insight = None
        if "insights" in run_data and run_data["insights"]:
            insight = run_data["insights"][-1]

        # Generate PDF (using global instance)
        pdf_bytes = report_generator.generate_pdf_report(run_data, paradox, insight)
        
        # Stream response
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=report_{run_id}.pdf"
            }
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"PDF generation failed for {run_id}")
        raise HTTPException(status_code=500, detail=f"Failed to generate PDF: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
