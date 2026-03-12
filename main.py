"""
AI Ethics Comparator - Main Server
App factory with startup-time service initialization.
"""

import asyncio
import io
import logging
import os
import random
import re
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator, Awaitable, Callable, Coroutine, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from lib.ai_service import AIService
from lib.analysis import AnalysisConfig, AnalysisEngine
from lib.config import AppConfig
from lib.counterfactual import CounterfactualEngine
from lib.experiment_runner import ExperimentRunner
from lib.fingerprint import compute_model_fingerprint
from lib.paradoxes import extract_scenario_text, get_paradox_by_id, load_paradoxes
from lib.query_errors import AuthenticationError, ModelNotFoundError, QueryExecutionError, QuotaError
from lib.query_processor import QueryProcessor, RunConfig
from lib.report_writer import ReportWriterAgent, NarrativeConfig
from lib.reporting import ReportGenerator
from lib.storage import RunStorage, STRICT_RUN_ID_PATTERN, ExperimentStorage
from lib.validation import ComparisonRequest, ExperimentCreateRequest, ExperimentRecord, InsightRequest, QueryRequest
from lib.view_models import RunViewModel, fetch_recent_run_view_models, safe_markdown

# Load environment before startup config resolution.
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

MODEL_NAME_PATTERN = re.compile(r"^[a-z0-9\-_/:.]+$", re.IGNORECASE)
RUN_ID_PATTERN = STRICT_RUN_ID_PATTERN


@dataclass
class AppServices:
    config: AppConfig
    storage: RunStorage
    experiment_storage: ExperimentStorage
    query_processor: QueryProcessor
    experiment_runner: ExperimentRunner
    counterfactual_engine: CounterfactualEngine
    analysis_engine: AnalysisEngine
    report_writer: ReportWriterAgent
    report_generator: ReportGenerator
    templates: Jinja2Templates
    paradoxes_path: Path


def _build_templates(templates_dir: str) -> Jinja2Templates:
    templates = Jinja2Templates(directory=templates_dir)
    templates.env.filters["markdown"] = safe_markdown
    return templates


def _validate_run_id(run_id: str) -> None:
    if not RUN_ID_PATTERN.fullmatch(run_id):
        raise HTTPException(status_code=400, detail="Invalid run_id")


def _validate_model_id(model_id: str) -> None:
    if not model_id or not MODEL_NAME_PATTERN.fullmatch(model_id):
        raise HTTPException(status_code=400, detail="Invalid model_id")


def _get_services(request: Request) -> AppServices:
    services: Optional[AppServices] = getattr(request.app.state, "services", None)
    if services is None:
        raise HTTPException(status_code=503, detail="Application not initialized")
    return services


def _build_run_config_from_request(
    query_request: QueryRequest,
    paradox: dict[str, Any],
) -> RunConfig:
    return RunConfig(
        modelName=query_request.model_name,
        paradox=paradox,
        option_overrides=(
            [opt.model_dump() for opt in query_request.option_overrides.options]
            if query_request.option_overrides and query_request.option_overrides.options
            else None
        ),
        iterations=query_request.iterations or 10,
        systemPrompt=query_request.system_prompt or "",
        params=query_request.params.model_dump() if query_request.params else {},
    )


def _build_run_config_from_saved_run(
    run_data: dict[str, Any],
    paradox: dict[str, Any],
) -> RunConfig:
    params = run_data.get("params", {})
    return RunConfig(
        modelName=str(run_data.get("modelName", "")),
        paradox=paradox,
        iterations=int(run_data.get("iterationCount", 0) or 0),
        systemPrompt=str(run_data.get("systemPrompt", "") or ""),
        params=params if isinstance(params, dict) else {},
        shuffle_options=isinstance(run_data.get("shuffleMapping"), dict),
    )


async def _save_failed_run(
    storage: RunStorage,
    run_data: dict[str, Any],
    error_message: str,
) -> None:
    run_id = run_data.get("runId")
    if not isinstance(run_id, str):
        return
    failed_run = dict(run_data)
    try:
        failed_run = await storage.get_run(run_id)
    except Exception:
        pass
    failed_run["status"] = "failed"
    failed_run["lastError"] = error_message
    failed_run["updatedAt"] = datetime.now(timezone.utc).isoformat()
    await storage.save_run(run_id, failed_run)


async def _execute_persisted_run(
    services: AppServices,
    run_config: RunConfig,
    run_data: dict[str, Any],
) -> dict[str, Any]:
    run_id = run_data.get("runId")
    if not isinstance(run_id, str):
        raise ValueError("Persisted run is missing runId")

    save_lock = asyncio.Lock()

    async def persist_progress(snapshot: dict[str, Any]) -> None:
        async with save_lock:
            persisted = dict(snapshot)
            persisted["runId"] = run_id
            await services.storage.save_run(run_id, persisted)

    try:
        final_run = await services.query_processor.execute_run(
            run_config,
            existing_run=run_data,
            progress_callback=persist_progress,
        )
    except Exception as exc:
        await _save_failed_run(services.storage, run_data, str(exc))
        raise

    final_run["runId"] = run_id
    final_run["status"] = "completed"
    final_run["updatedAt"] = datetime.now(timezone.utc).isoformat()
    await persist_progress(final_run)
    return final_run


def _track_run_task(
    app: FastAPI,
    run_id: str,
    coroutine: Coroutine[Any, Any, dict[str, Any]],
) -> "asyncio.Task[dict[str, Any]]":
    active_tasks: dict[str, asyncio.Task[dict[str, Any]]] = getattr(app.state, "active_run_tasks", {})
    existing_task = active_tasks.get(run_id)
    if existing_task is not None and not existing_task.done():
        return existing_task

    task = asyncio.create_task(coroutine, name=f"run:{run_id}")
    active_tasks[run_id] = task
    app.state.active_run_tasks = active_tasks

    def _cleanup(done_task: "asyncio.Task[dict[str, Any]]") -> None:
        current = active_tasks.get(run_id)
        if current is done_task:
            active_tasks.pop(run_id, None)
        try:
            exc = done_task.exception()
        except asyncio.CancelledError:
            return
        if exc is not None:
            logger.error("Run task %s failed: %s", run_id, exc)

    task.add_done_callback(_cleanup)
    return task


async def _resume_incomplete_runs(app: FastAPI, services: AppServices) -> None:
    try:
        paradoxes = load_paradoxes(services.paradoxes_path)
    except Exception as exc:
        logger.error("Failed to load paradoxes while resuming runs: %s", exc)
        return

    for run_data in await services.storage.list_incomplete_runs():
        run_id = run_data.get("runId")
        if not isinstance(run_id, str):
            continue

        paradox = get_paradox_by_id(paradoxes, run_data.get("paradoxId"))
        if not paradox:
            await _save_failed_run(services.storage, run_data, "Paradox definition not found during resume")
            continue

        try:
            run_config = _build_run_config_from_saved_run(run_data, paradox)
        except Exception as exc:
            await _save_failed_run(services.storage, run_data, f"Invalid resume configuration: {exc}")
            continue

        _track_run_task(
            app,
            run_id,
            _execute_persisted_run(services, run_config, run_data),
        )


def create_app(config_override: Optional[AppConfig] = None) -> FastAPI:
    templates_dir = "templates"
    templates = _build_templates(templates_dir)
    paradoxes_path = Path(__file__).parent / "paradoxes.json"
    analysis_prompt_path = Path(__file__).parent / templates_dir / "analysis_prompt.txt"
    report_writer_prompt_path = Path(__file__).parent / templates_dir / "report_writer_prompt.txt"

    if config_override is not None:
        app_title = config_override.APP_NAME
        app_version = config_override.VERSION
        allowed_origins = [config_override.APP_BASE_URL] if config_override.APP_BASE_URL else []
    else:
        app_title = "AI Ethics Comparator"
        app_version = "0.0.0"
        app_base_url = os.getenv("APP_BASE_URL")
        allowed_origins = [app_base_url] if app_base_url else []

    @asynccontextmanager
    async def lifespan(app_instance: FastAPI) -> AsyncIterator[None]:
        app_instance.state.active_run_tasks = {}
        config = config_override or AppConfig.load()
        try:
            config.validate_secrets()
        except ValueError as exc:
            logger.critical(str(exc))
            raise RuntimeError(str(exc)) from exc

        ai_service = AIService(
            api_key=str(config.OPENROUTER_API_KEY),
            base_url=config.OPENROUTER_BASE_URL,
            referer=config.APP_BASE_URL,
            app_name=config.APP_NAME,
            max_retries=config.AI_MAX_RETRIES,
            retry_delay=config.AI_RETRY_DELAY,
        )

        storage = RunStorage(str(config.results_path))
        migrated_ids = await storage.migrate_legacy_run_ids()
        if migrated_ids:
            logger.info("Migrated %s legacy run IDs to strict format", len(migrated_ids))
            
        experiment_storage = ExperimentStorage(str(storage.results_root.parent / "experiments"))

        query_processor = QueryProcessor(
            ai_service,
            concurrency_limit=config.AI_CONCURRENCY_LIMIT,
            choice_inference_model=(
                config.ANALYST_MODEL if config.AI_CHOICE_INFERENCE_ENABLED else None
            ),
        )
        analysis_engine = AnalysisEngine(
            ai_service,
            prompt_template_path=analysis_prompt_path,
        )
        report_writer = ReportWriterAgent(
            ai_service,
            prompt_template_path=report_writer_prompt_path,
        )
        report_generator = ReportGenerator(templates_dir=templates_dir)

        experiment_runner = ExperimentRunner(
            query_processor=query_processor,
            run_storage=storage,
            experiment_storage=experiment_storage,
            max_iterations=config.MAX_ITERATIONS,
            max_concurrent_conditions=max(1, min(config.AI_CONCURRENCY_LIMIT, 4)),
        )
        counterfactual_engine = CounterfactualEngine(
            query_processor=query_processor,
            run_storage=storage
        )

        app_instance.state.services = AppServices(
            config=config,
            storage=storage,
            experiment_storage=experiment_storage,
            query_processor=query_processor,
            experiment_runner=experiment_runner,
            counterfactual_engine=counterfactual_engine,
            analysis_engine=analysis_engine,
            report_writer=report_writer,
            report_generator=report_generator,
            templates=templates,
            paradoxes_path=paradoxes_path,
        )
        app_instance.title = config.APP_NAME
        app_instance.version = config.VERSION
        logger.info("Starting %s v%s", config.APP_NAME, config.VERSION)
        await _resume_incomplete_runs(app_instance, app_instance.state.services)
        try:
            yield
        finally:
            active_tasks: dict[str, asyncio.Task[dict[str, Any]]] = getattr(
                app_instance.state,
                "active_run_tasks",
                {},
            )
            for task in list(active_tasks.values()):
                task.cancel()
            if active_tasks:
                await asyncio.gather(*active_tasks.values(), return_exceptions=True)
            app_instance.state.services = None

    app = FastAPI(title=app_title, version=app_version, lifespan=lifespan)
    app.mount("/static", StaticFiles(directory="static"), name="static")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "X-App-Version"],
    )

    app.state.services = None
    app.state.active_run_tasks = {}

    @app.middleware("http")
    async def add_version_header(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response: Response = await call_next(request)
        services: Optional[AppServices] = getattr(request.app.state, "services", None)
        if services is not None:
            response.headers["X-App-Version"] = services.config.VERSION
        return response

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request, runId: Optional[str] = None) -> HTMLResponse:
        services = _get_services(request)
        config = services.config
        try:
            paradoxes = load_paradoxes(services.paradoxes_path)
        except Exception as exc:
            logger.error("Failed to load paradoxes: %s", exc)
            raise HTTPException(
                status_code=500,
                detail="Failed to load paradox definitions. Please check server logs.",
            ) from exc

        recent_run_contexts = await fetch_recent_run_view_models(
            services.storage,
            paradoxes,
            config.ANALYST_MODEL,
        )

        # If a specific run was requested via query param, ensure it is visible.
        if runId and RUN_ID_PATTERN.fullmatch(runId):
            existing_ids = {r["run_id"] for r in recent_run_contexts}
            if runId not in existing_ids:
                try:
                    target_run = await services.storage.get_run(runId)
                    p_id = target_run.get("paradoxId")
                    paradox = get_paradox_by_id(paradoxes, p_id) or {}
                    vm = RunViewModel.build(target_run, paradox)
                    vm["config_analyst_model"] = config.ANALYST_MODEL
                    recent_run_contexts.insert(0, vm)
                except (FileNotFoundError, ValueError):
                    pass

        initial_paradox = random.choice(paradoxes) if paradoxes else None
        initial_scenario_text = ""
        if initial_paradox:
            initial_scenario_text = extract_scenario_text(
                initial_paradox.get("promptTemplate", "")
            )

        return services.templates.TemplateResponse(
            request,
            "index.html",
            {
                "paradoxes": paradoxes,
                "models": config.AVAILABLE_MODELS,
                "default_model": config.DEFAULT_MODEL,
                "recent_run_contexts": recent_run_contexts,
                "initial_paradox": initial_paradox,
                "initial_scenario_text": initial_scenario_text,
                "max_iterations": config.MAX_ITERATIONS,
                "current_page": "single_run",
            },
        )

    @app.get("/experiments")
    async def experiments_ui(request: Request) -> HTMLResponse:
        services = _get_services(request)
        config = services.config

        try:
            paradoxes = load_paradoxes(services.paradoxes_path)
            # Retrieve existing experiments
            experiments = await services.experiment_storage.list_experiments()
        except Exception as exc:
            logger.error("Failed to load laboratory data: %s", exc)
            raise HTTPException(
                status_code=500,
                detail="Failed to load laboratory data. Please check server logs.",
            ) from exc

        return services.templates.TemplateResponse(
            request,
            "experiments.html",
            {
                "paradoxes": paradoxes,
                "models": config.AVAILABLE_MODELS,
                "default_model": config.DEFAULT_MODEL,
                "experiments": experiments,
                "max_iterations": config.MAX_ITERATIONS,
                "current_page": "laboratory",
            },
        )

    @app.get("/health")
    async def health_check(request: Request) -> dict:
        services: Optional[AppServices] = getattr(request.app.state, "services", None)
        version = services.config.VERSION if services else "uninitialized"
        return {
            "status": "healthy" if services else "starting",
            "version": version,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "uptime": "N/A",
        }

    @app.get("/fragments/fingerprint")
    async def get_model_fingerprint_fragment(request: Request, model_id: str) -> HTMLResponse:
        services = _get_services(request)
        if not model_id or not MODEL_NAME_PATTERN.fullmatch(model_id):
            return HTMLResponse("<div>Please select a valid model.</div>", status_code=400)
        try:
            fp_data = await compute_model_fingerprint(model_id, services.storage)
            return services.templates.TemplateResponse(
                request,
                "partials/fingerprint.html",
                {
                    "model_id": model_id,
                    "fingerprint": fp_data.get("fingerprint", []),
                    "total_insights": fp_data.get("totalRunsWithInsights", 0),
                },
            )
        except Exception as exc:
            logger.error("Failed to compute fingerprint fragment for %s: %s", model_id, exc)
            return HTMLResponse(
                (
                    "<div class='error' style='color: var(--accent-danger); "
                    "padding: 1rem; border-left: 3px solid var(--accent-danger);'>"
                    "Failed to load fingerprint.</div>"
                ),
                status_code=500,
            )

    @app.get("/api/paradoxes")
    async def get_paradoxes(request: Request) -> list:
        services = _get_services(request)
        try:
            return load_paradoxes(services.paradoxes_path)
        except Exception as exc:
            logger.error("Failed to read paradoxes: %s", exc)
            raise HTTPException(status_code=500, detail="Failed to read paradoxes.") from exc

    @app.get("/api/fragments/paradox-details")
    async def get_paradox_details(request: Request, paradoxId: str) -> HTMLResponse:
        services = _get_services(request)
        try:
            paradoxes = load_paradoxes(services.paradoxes_path)
            paradox = get_paradox_by_id(paradoxes, paradoxId)
            if not paradox:
                return HTMLResponse("<div>Paradox not found</div>", status_code=404)

            scenario_text = extract_scenario_text(paradox.get("promptTemplate", ""))
            return services.templates.TemplateResponse(
                request,
                "partials/paradox_details.html",
                {
                    "paradox": paradox,
                    "scenario_text": scenario_text,
                },
            )
        except Exception as exc:
            logger.error("Failed to get paradox details: %s", exc)
            return HTMLResponse("<div>Error loading details</div>", status_code=500)

    @app.get("/api/runs")
    async def list_runs(request: Request) -> list:
        services = _get_services(request)
        try:
            return await services.storage.list_runs()
        except Exception as exc:
            logger.error("Failed to list runs: %s", exc)
            raise HTTPException(status_code=500, detail="Failed to retrieve runs.") from exc

    @app.get("/api/runs/{run_id}")
    async def get_run(request: Request, run_id: str) -> dict:
        services = _get_services(request)
        _validate_run_id(run_id)
        try:
            return await services.storage.get_run(run_id)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Run not found.")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            logger.error("Failed to get run %s: %s", run_id, exc)
            raise HTTPException(status_code=500, detail="Failed to retrieve run data.") from exc

    @app.post("/api/runs/{run_id}/counterfactual")
    async def create_counterfactual(request: Request, run_id: str) -> Response:
        _validate_run_id(run_id)
        services = _get_services(request)
        try:
            paradoxes = load_paradoxes(services.paradoxes_path)
            cf_run = await services.counterfactual_engine.execute_counterfactual(run_id, paradoxes)
            if request.headers.get("HX-Request"):
                paradox = get_paradox_by_id(paradoxes, cf_run["paradoxId"]) or {}
                vm = RunViewModel.build(cf_run, paradox)
                vm["config_analyst_model"] = services.config.ANALYST_MODEL
                return services.templates.TemplateResponse(
                    request,
                    "partials/result_item.html",
                    {"ctx": vm},
                )
            return JSONResponse(content=cf_run)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            logger.error("Counterfactual generation failed: %s", exc)
            raise HTTPException(status_code=500, detail="Counterfactual generation failed") from exc

    @app.post("/api/experiments")
    async def create_experiment(request: Request, exp_req: ExperimentCreateRequest) -> dict:
        services = _get_services(request)
        exp_id = f"exp_{int(datetime.now(timezone.utc).timestamp())}_{uuid.uuid4().hex[:6]}"
        
        record = ExperimentRecord(
            id=exp_id,
            title=exp_req.title,
            paradoxIds=exp_req.paradoxIds,
            conditions=exp_req.conditions,
            status="pending",
            tags=exp_req.tags or [],
            createdAt=datetime.now(timezone.utc).isoformat(),
        )
        exp_data = record.model_dump(by_alias=True)
        try:
            await services.experiment_storage.save_experiment(exp_id, exp_data)
            return exp_data
        except Exception as exc:
             logger.error("Failed to create experiment: %s", exc)
             raise HTTPException(status_code=500, detail="Failed to create experiment") from exc

    @app.get("/api/experiments")
    async def list_experiments(request: Request) -> list:
        services = _get_services(request)
        try:
            return await services.experiment_storage.list_experiments()
        except Exception as exc:
            logger.error("Failed to list experiments: %s", exc)
            raise HTTPException(status_code=500, detail="Failed to retrieve experiments")

    def _validate_experiment_id(exp_id: str) -> None:
        if not re.match(r'^exp_[0-9]+_[a-f0-9]+$', exp_id):
            raise HTTPException(status_code=400, detail="Invalid experiment ID format")

    @app.get("/api/experiments/{exp_id}")
    async def get_experiment(request: Request, exp_id: str) -> dict:
        _validate_experiment_id(exp_id)
        services = _get_services(request)
        try:
            return await services.experiment_storage.get_experiment(exp_id)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Experiment not found")
            
    @app.post("/api/experiments/{exp_id}/execute")
    async def execute_experiment(request: Request, exp_id: str) -> dict:
        _validate_experiment_id(exp_id)
        services = _get_services(request)
        
        try:
            exp_data = await services.experiment_storage.get_experiment(exp_id)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Experiment not found")
            
        if exp_data.get("status") != "pending":
            raise HTTPException(status_code=400, detail="Experiment must be in pending status to execute")
            
        exp_data["status"] = "running"
        await services.experiment_storage.save_experiment(exp_id, exp_data)

        try:
            paradoxes = load_paradoxes(services.paradoxes_path)
            result = await services.experiment_runner.execute_experiment(exp_id, exp_data, paradoxes)
            return result.model_dump(by_alias=True)
        except Exception as exc:
            logger.error("Experiment execution failed for %s: %s", exp_id, exc)
            exp_data["status"] = "failed"
            exp_data.setdefault("errors", []).append(str(exc))
            try:
                await services.experiment_storage.save_experiment(exp_id, exp_data)
            except Exception as save_exc:
                logger.error("Failed to persist experiment failure state for %s: %s", exp_id, save_exc)
            raise HTTPException(status_code=500, detail="Failed to execute experiment") from exc

    @app.get("/api/models/{model_id:path}/fingerprint")
    async def get_model_fingerprint_route(request: Request, model_id: str) -> dict:
        services = _get_services(request)
        _validate_model_id(model_id)
        try:
            return await compute_model_fingerprint(model_id, services.storage)
        except Exception as exc:
            logger.error("Failed to compute fingerprint: %s", exc)
            raise HTTPException(status_code=500, detail="Failed to compute fingerprint") from exc

    @app.post("/api/query")
    async def execute_query(request: Request, query_request: QueryRequest):
        services = _get_services(request)
        config = services.config
        try:
            paradoxes = load_paradoxes(services.paradoxes_path)
            paradox = get_paradox_by_id(paradoxes, query_request.paradox_id)
            if not paradox:
                raise HTTPException(
                    status_code=404,
                    detail=f"Paradox '{query_request.paradox_id}' not found",
                )

            req_iterations = query_request.iterations or 10
            if req_iterations > config.MAX_ITERATIONS:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Iterations {req_iterations} exceeds limit of {config.MAX_ITERATIONS}"
                    ),
                )

            run_config = _build_run_config_from_request(query_request, paradox)
            initial_run = services.query_processor.initialize_run_data(run_config)
            run_id = await services.storage.create_run(query_request.model_name, initial_run)
            task = _track_run_task(
                request.app,
                run_id,
                _execute_persisted_run(services, run_config, initial_run),
            )
            run_data = await asyncio.shield(task)

            if request.headers.get("HX-Request"):
                vm = RunViewModel.build(run_data, paradox)
                vm["config_analyst_model"] = config.ANALYST_MODEL
                return services.templates.TemplateResponse(
                    request,
                    "partials/result_item.html",
                    {"ctx": vm},
                )

            return run_data
        except HTTPException:
            raise
        except AuthenticationError as exc:
            logger.error("Query execution failed: %s", exc)
            raise HTTPException(status_code=401, detail="Invalid API key or unauthorized.") from exc
        except QuotaError as exc:
            logger.error("Query execution failed: %s", exc)
            raise HTTPException(status_code=402, detail="Insufficient API credits.") from exc
        except ModelNotFoundError as exc:
            logger.error("Query execution failed: %s", exc)
            raise HTTPException(status_code=404, detail="Requested model not found.") from exc
        except QueryExecutionError as exc:
            logger.error("Query execution failed: %s", exc)
            raise HTTPException(status_code=502, detail="Model provider error") from exc
        except Exception as exc:
            logger.error("Query execution failed: %s", exc)
            raise HTTPException(status_code=500, detail="Internal server error") from exc

    @app.post("/api/insight")
    async def generate_insight(request: Request, insight_request: InsightRequest) -> dict:
        services = _get_services(request)
        try:
            model_to_use = insight_request.analystModel or services.config.ANALYST_MODEL
            cfg = AnalysisConfig(
                run_data=insight_request.runData,
                analyst_model=model_to_use,
            )
            insight_data = await services.analysis_engine.generate_insight(cfg)

            if "runId" in insight_request.runData:
                run_id = insight_request.runData["runId"]
                if RUN_ID_PATTERN.fullmatch(run_id):
                    try:
                        existing_run = await services.storage.get_run(run_id)
                        if "insights" not in existing_run:
                            existing_run["insights"] = []
                        existing_run["insights"].append(insight_data)
                        await services.storage.save_run(run_id, existing_run)
                    except Exception as save_error:
                        logger.error("Error saving insight: %s", save_error)

            return {"insight": insight_data["content"], "model": model_to_use}
        except Exception as exc:
            logger.error("Insight generation failed: %s", exc)
            raise HTTPException(status_code=500, detail="Internal server error") from exc

    @app.post("/api/runs/{run_id}/analyze")
    async def analyze_run(request: Request, run_id: str, regenerate: bool = False) -> HTMLResponse:
        services = _get_services(request)
        _validate_run_id(run_id)
        model_to_use = services.config.ANALYST_MODEL
        try:
            form_data = await request.form()
            requested_analyst = form_data.get("analyst_model")
            if requested_analyst and not MODEL_NAME_PATTERN.fullmatch(requested_analyst):
                return HTMLResponse("<div class='error'>Invalid model name format</div>", status_code=400)

            run_data = await services.storage.get_run(run_id)

            if not regenerate and "insights" in run_data and run_data["insights"]:
                insight = run_data["insights"][-1]
                cached_model = insight.get("analystModel")
                if not requested_analyst or requested_analyst == cached_model:
                    content = insight.get("content", {})
                    if isinstance(content, str):
                        content = {"legacy_text": content}
                    return services.templates.TemplateResponse(
                        request,
                        "partials/analysis_view.html",
                        {
                            "insight": content,
                            "model": cached_model,
                            "cached": True,
                            "run_id": run_id,
                            "run_data": run_data,
                        },
                    )

            model_to_use = requested_analyst or services.config.ANALYST_MODEL
            if not model_to_use or not MODEL_NAME_PATTERN.fullmatch(model_to_use):
                raise ValueError("Invalid analyst model name")

            cfg = AnalysisConfig(run_data=run_data, analyst_model=model_to_use)
            insight_data = await services.analysis_engine.generate_insight(cfg)

            if "insights" not in run_data:
                run_data["insights"] = []
            run_data["insights"].append(insight_data)
            await services.storage.save_run(run_id, run_data)

            return services.templates.TemplateResponse(
                request,
                "partials/analysis_view.html",
                {
                    "insight": insight_data["content"],
                    "model": model_to_use,
                    "cached": False,
                    "run_id": run_id,
                    "run_data": run_data,
                },
            )
        except Exception as exc:
            logger.error("Analysis failed: %s", exc)
            # HTMX callers need 200 to swap the error fragment into the modal;
            # non-HTMX callers get a proper 500.
            error_status = 200 if request.headers.get("HX-Request") else 500
            return services.templates.TemplateResponse(
                request,
                "partials/analysis_error.html",
                {
                    "error_message": str(exc),
                    "model": model_to_use or "",
                    "run_id": run_id,
                },
                status_code=error_status,
            )

    @app.get("/api/runs/{run_id}/pdf")
    async def download_pdf_report(request: Request, run_id: str, theme: str = "dark") -> StreamingResponse:
        services = _get_services(request)
        _validate_run_id(run_id)
        try:
            run_data = await services.storage.get_run(run_id)
            paradoxes = load_paradoxes(services.paradoxes_path)
            paradox = get_paradox_by_id(paradoxes, run_data["paradoxId"])
            if not paradox:
                raise HTTPException(status_code=404, detail="Paradox definition not found")

            insight = None
            if "insights" in run_data and run_data["insights"]:
                insight = run_data["insights"][-1]

            # Generate AI narrative (or use cached version)
            narrative = None
            cached_narrative = run_data.get("narrative")
            if isinstance(cached_narrative, dict) and any(cached_narrative.values()):
                narrative = cached_narrative
            else:
                writer_model = services.config.ANALYST_MODEL
                if writer_model:
                    try:
                        narrative = await services.report_writer.generate_narrative(
                            run_data,
                            paradox,
                            insight,
                            NarrativeConfig(model=writer_model),
                        )
                        # Cache the narrative in run data for future downloads
                        if any(narrative.values()):
                            run_data["narrative"] = narrative
                            await services.storage.save_run(run_id, run_data)
                    except Exception as narr_exc:
                        logger.warning(
                            "Report narrative generation failed for %s, proceeding without: %s",
                            run_id,
                            narr_exc,
                        )

            validated_theme = "light" if theme == "light" else "dark"
            try:
                pdf_bytes = services.report_generator.generate_pdf_report(
                    run_data, paradox, insight, narrative, theme=validated_theme
                )
            except RuntimeError as exc:
                logger.warning("PDF generation unavailable for %s: %s", run_id, exc)
                raise HTTPException(status_code=503, detail="PDF generation unavailable") from exc

            return StreamingResponse(
                io.BytesIO(pdf_bytes),
                media_type="application/pdf",
                headers={"Content-Disposition": f"inline; filename=report_{run_id}.pdf"},
            )
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception("PDF generation failed for %s", run_id)
            raise HTTPException(status_code=500, detail="Failed to generate PDF") from exc

    @app.get("/api/compare/pdf")
    async def download_comparison_pdf(request: Request, run_ids: str, theme: str = "dark") -> StreamingResponse:
        """Generate a comparative PDF for 2-4 runs on the same paradox."""
        services = _get_services(request)
        ids = [rid.strip() for rid in run_ids.split(",") if rid.strip()]
        if len(ids) < 2 or len(ids) > 4:
            raise HTTPException(status_code=400, detail="Provide 2-4 comma-separated run_ids")
        for rid in ids:
            _validate_run_id(rid)

        try:
            runs = [await services.storage.get_run(rid) for rid in ids]
            paradox_ids = {r.get("paradoxId") for r in runs}
            if len(paradox_ids) != 1:
                raise HTTPException(status_code=400, detail="All runs must share the same paradox")

            paradoxes = load_paradoxes(services.paradoxes_path)
            paradox = get_paradox_by_id(paradoxes, paradox_ids.pop())
            if not paradox:
                raise HTTPException(status_code=404, detail="Paradox not found")

            insights = []
            for run in runs:
                ins = run.get("insights", [])
                insights.append(ins[-1] if ins else None)

            validated_theme = "light" if theme == "light" else "dark"
            try:
                pdf_bytes = services.report_generator.generate_comparison_pdf(
                    runs, paradox, insights, theme=validated_theme,
                )
            except RuntimeError as exc:
                logger.warning("Comparison PDF generation unavailable: %s", exc)
                raise HTTPException(status_code=503, detail="Comparison PDF generation unavailable") from exc
            return StreamingResponse(
                io.BytesIO(pdf_bytes),
                media_type="application/pdf",
                headers={"Content-Disposition": "inline; filename=comparison_report.pdf"},
            )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception("Comparison PDF generation failed")
            raise HTTPException(status_code=500, detail="Failed to generate comparison PDF") from exc

    @app.get("/api/runs/{run_id}/export")
    async def export_run(request: Request, run_id: str, format: str = "json") -> Response:
        """Export run data in JSON or PPTX format (Phase 6)."""
        services = _get_services(request)
        _validate_run_id(run_id)
        try:
            run_data = await services.storage.get_run(run_id)
            paradoxes = load_paradoxes(services.paradoxes_path)
            paradox = get_paradox_by_id(paradoxes, run_data["paradoxId"]) or {}

            if format == "json":
                from lib.export_data import export_run_json
                data = export_run_json(run_data, paradox)
                return JSONResponse(content=data)

            if format == "pptx":
                from lib.export_pptx import generate_pptx, pptx_available
                if not pptx_available():
                    raise HTTPException(status_code=503, detail="PowerPoint export unavailable")
                insight = None
                if "insights" in run_data and run_data["insights"]:
                    insight = run_data["insights"][-1]
                pptx_bytes = generate_pptx(run_data, paradox, insight)
                return StreamingResponse(
                    io.BytesIO(pptx_bytes),
                    media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                    headers={"Content-Disposition": f"attachment; filename=report_{run_id}.pptx"},
                )

            raise HTTPException(status_code=400, detail="format must be 'json' or 'pptx'")
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Run not found")
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception("Export failed for %s", run_id)
            raise HTTPException(status_code=500, detail="Export failed") from exc

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
