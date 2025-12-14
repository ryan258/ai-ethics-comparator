"""
AI Ethics Comparator - Main Server
Thin routing layer using Arsenal Strategy modules
"""

import os
import json
from pathlib import Path
from datetime import datetime
from typing import Optional

from dotenv import load_dotenv
# Load environment immediately - MUST be before any lib imports that use config
load_dotenv()

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware

# Arsenal modules
from lib.validation import QueryRequest, InsightRequest
from lib.ai_service import AIService
from lib.storage import RunStorage
from lib.query_processor import QueryProcessor
from lib.analysis import AnalysisEngine, AnalysisConfig

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
    api_key=config.OPENROUTER_API_KEY, # type: ignore (validated above)
    base_url=config.OPENROUTER_BASE_URL,
    referer=config.APP_BASE_URL,
    app_name=config.APP_NAME
)

storage = RunStorage(str(config.results_path))
query_processor = QueryProcessor(ai_service, concurrency_limit=2)
# AnalysisEngine no longer needs config, just ai_service
analysis_engine = AnalysisEngine(ai_service)

# FastAPI setup
app = FastAPI(title=config.APP_NAME, version=config.VERSION)

# Templates
templates = Jinja2Templates(directory="templates")

import markdown
import html
from markupsafe import Markup

def markdown_filter(text):
    # Escape raw HTML in the input text to prevent injection
    escaped_text = html.escape(str(text))
    # Render markdown
    rendered = markdown.markdown(escaped_text)
    # Mark as safe for Jinja (since we verified input is safe-ish by escaping)
    return Markup(rendered)

templates.env.filters['markdown'] = markdown_filter

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
async def add_version_header(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-App-Version"] = config.VERSION
    return response


# Routes

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Serve main application page"""
    # Load paradoxes for the dropdown
    try:
        paradoxes_path = Path(__file__).parent / "paradoxes.json"
        with open(paradoxes_path, 'r') as f:
            paradoxes = json.load(f)
    except Exception:
        paradoxes = []
        
    return templates.TemplateResponse("index.html", {
        "request": request, 
        "paradoxes": paradoxes,
        "models": config.AVAILABLE_MODELS,
        "default_model": config.DEFAULT_MODEL
    })


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "version": config.VERSION,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "uptime": "N/A"  # Can add process uptime if needed
    }


@app.get("/api/paradoxes")
async def get_paradoxes():
    """Get available paradoxes"""
    try:
        paradoxes_path = Path(__file__).parent / "paradoxes.json"
        with open(paradoxes_path, 'r') as f:
            paradoxes = json.load(f)
        return paradoxes
    except Exception as e:
        logger.error(f"Failed to read paradoxes: {e}")
        raise HTTPException(status_code=500, detail="Failed to read paradoxes.")


@app.get("/api/runs")
async def list_runs():
    """List all runs (metadata only)"""
    try:
        runs = await storage.list_runs()
        return runs
    except Exception as e:
        logger.error(f"Failed to list runs: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve runs.")


@app.get("/api/runs/{run_id}")
async def get_run(run_id: str):
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
async def execute_query(request: Request, query_request: QueryRequest):
    """Execute experimental run"""
    try:
        # Load paradox
        paradoxes_path = Path(__file__).parent / "paradoxes.json"
        with open(paradoxes_path, 'r') as f:
            paradoxes = json.load(f)

        paradox = next((p for p in paradoxes if p["id"] == query_request.paradoxId), None)
        if not paradox:
            raise HTTPException(status_code=404, detail="Paradox not found.")

        # Execute run
        from lib.query_processor import RunConfig

        # Create typed run configuration
        run_config = RunConfig(
            modelName=query_request.modelName,
            paradox=paradox,
            groups=query_request.groups.dict() if query_request.groups else {},
            iterations=query_request.iterations or 10,
            systemPrompt=query_request.systemPrompt or "",
            params=query_request.params.dict() if query_request.params else {}
        )

        run_data = await query_processor.execute_run(run_config)

        # Generate unique run ID and save
        run_id = await storage.generate_run_id(query_request.modelName)
        run_data["runId"] = run_id

        await storage.save_run(run_id, run_data)

        # Check for HTMX
        if request.headers.get("HX-Request"):
            # Return an HTML fragment for the results stream
            summary = run_data.get('summary', {})
            g1 = summary.get('group1', {})
            g2 = summary.get('group2', {})
            p1 = g1.get('percentage', 0)
            p2 = g2.get('percentage', 0)
            
            return templates.TemplateResponse("partials/result_item.html", {
                "request": request,
                "run_data": run_data,
                "paradox": paradox,
                "run_id": run_id,
                "summary": summary,
                "p1": f"{p1:.1f}",
                "p2": f"{p2:.1f}",
                "run_data_json": json.dumps(run_data, indent=2),
                "config_analyst_model": config.ANALYST_MODEL
            })

        return run_data
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Query execution failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/api/insight")
async def generate_insight(request: InsightRequest):
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
                # But let's stick to get/save pattern for now to be safe with existing logic logic
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
async def analyze_run(request: Request, run_id: str):
    """Generate and return analysis for a run (HTMX plain text/html)"""
    try:
        # Get form data if present
        form_data = await request.form()
        requested_analyst = form_data.get("analyst_model")

        run_data = await storage.get_run(run_id)
        
        # Check cache
        if "insights" in run_data and len(run_data["insights"]) > 0:
            insight = run_data["insights"][-1]
            cached_model = insight.get("analystModel")
            
            if not requested_analyst or (requested_analyst == cached_model):
                return templates.TemplateResponse("partials/analysis_view.html", {
                    "request": request,
                    "insight": insight["content"],
                    "model": cached_model,
                    "cached": True
                })

        # Generate new insight
        model_to_use = requested_analyst or config.ANALYST_MODEL
        
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
            "cached": False
        })
        
    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        return HTMLResponse(f"<div class='error'>Analysis failed. Please check logs.</div>", status_code=500)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
