"""
AI Ethics Comparator - Main Server
App factory with startup-time service initialization.
"""

import asyncio
import io
import json
import logging
import os
import random
import re
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable, Coroutine
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypeVar

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
from lib.evidence import evidence_hash, selected_insight, validate_comparison
from lib.experiment_runner import ExperimentRunner
from lib.fingerprint import compute_model_fingerprint
from lib.paradoxes import (
    extract_scenario_text,
    get_paradox_by_id,
    load_paradoxes,
    resolve_paradox,
)
from lib.query_errors import (
    AuthenticationError,
    ModelNotFoundError,
    QueryExecutionError,
    QuotaError,
    safe_error_message,
)
from lib.query_processor import QueryProcessor, RunConfig
from lib.reporting import ReportGenerator
from lib.run_executor import execute_persisted_run
from lib.storage import STRICT_RUN_ID_PATTERN, ExperimentStorage, RunStorage
from lib.validation import (
    ExperimentCreateRequest,
    ExperimentRecord,
    InsightRequest,
    QueryRequest,
)
from lib.view_models import RunViewModel, fetch_recent_run_view_models, safe_markdown

# Load environment before startup config resolution.
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

# Keep the terminal focused on application events rather than dependency chatter.
for noisy_logger_name in (
    "httpx",
    "httpcore",
    "fontTools",
    "fontTools.subset",
    "uvicorn.access",
):
    logging.getLogger(noisy_logger_name).setLevel(logging.WARNING)

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
    services: AppServices | None = getattr(request.app.state, "services", None)
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
        shuffle_options=query_request.shuffle_options,
    )


def _build_run_config_from_saved_run(
    run_data: dict[str, Any],
    paradox: dict[str, Any],
    max_iterations: int,
) -> RunConfig:
    params = run_data.get("params", {})
    stored_iterations = int(run_data.get("iterationCount", 0) or 0)
    if stored_iterations > max_iterations:
        raise ValueError(
            f"Run needs {stored_iterations} iterations, above the current limit of {max_iterations}"
        )
    return RunConfig(
        modelName=str(run_data.get("modelName", "")),
        paradox=paradox,
        iterations=stored_iterations,
        systemPrompt=str(run_data.get("systemPrompt", "") or ""),
        params=params if isinstance(params, dict) else {},
        # A resumed run must keep permuting the way it started: legacy runs
        # carry one run-level shuffleMapping, newer ones a per-iteration flag.
        shuffle_options=(
            isinstance(run_data.get("shuffleMapping"), dict)
            or bool(run_data.get("shufflePerIteration"))
        ),
    )


async def _execute_persisted_run(
    services: AppServices,
    run_config: RunConfig,
    run_data: dict[str, Any],
) -> dict[str, Any]:
    return await execute_persisted_run(services.query_processor, services.storage, run_config, run_data)


def _track_run_task(
    app: FastAPI,
    run_id: str,
    coroutine: Coroutine[Any, Any, dict[str, Any]],
) -> "asyncio.Task[dict[str, Any]]":
    active_tasks: dict[str, asyncio.Task[dict[str, Any]]] = getattr(app.state, "active_run_tasks", {})
    existing_task = active_tasks.get(run_id)
    if existing_task is not None and not existing_task.done():
        coroutine.close()
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


async def _mark_interrupted_runs(app: FastAPI, services: AppServices) -> None:
    """Mark runs that were left in 'running' state at shutdown as 'interrupted'.

    Auto-resume previously caused boot-time loops when a run hit a non-retryable
    provider error: the failure status never persisted before the next reload, so
    the broken run was resumed on every startup. Surface them as 'interrupted'
    instead and let the user choose whether to resume via the API/UI.
    """
    for run_data in await services.storage.list_incomplete_runs():
        run_id = run_data.get("runId")
        if not isinstance(run_id, str):
            continue
        run_data["status"] = "interrupted"
        run_data["lastError"] = "Run was interrupted (server restart). Resume manually if desired."
        run_data["updatedAt"] = datetime.now(UTC).isoformat()
        try:
            await services.storage.save_run(run_id, run_data)
        except Exception as exc:
            logger.error("Failed to mark run %s as interrupted: %s", run_id, exc)


async def _resume_run_by_id(app: FastAPI, services: AppServices, run_id: str) -> dict[str, Any]:
    run_data = await services.storage.get_run(run_id)
    if run_data.get("status") not in ("interrupted", "failed", "cancelled"):
        raise ValueError(f"Run {run_id} is not in a resumable state (status={run_data.get('status')!r})")

    paradoxes = load_paradoxes(services.paradoxes_path)
    # All three D11 tiers: a run whose scenario left the library is still
    # resumable, because the run carries its own prompt and options.
    paradox = resolve_paradox(run_data, paradoxes)

    run_config = _build_run_config_from_saved_run(run_data, paradox, services.config.MAX_ITERATIONS)
    def claim(latest: dict[str, Any]) -> None:
        if latest.get("status") not in ("interrupted", "failed", "cancelled"):
            raise ValueError("Run is already executing or completed")
        latest.update(status="running", lastError=None, updatedAt=datetime.now(UTC).isoformat())
    run_data = await services.storage.update_run(run_id, claim)


    _track_run_task(
        app,
        run_id,
        _execute_persisted_run(services, run_config, run_data),
    )
    return run_data


RenderResult = TypeVar("RenderResult", str, bytes)


def create_app(config_override: AppConfig | None = None) -> FastAPI:
    render_slots = asyncio.Semaphore(2)

    async def render_export(fn: Callable[..., RenderResult], *args: Any, **kwargs: Any) -> RenderResult:
        async with render_slots:
            task = asyncio.create_task(asyncio.to_thread(fn, *args, **kwargs))
            try:
                return await asyncio.shield(task)
            except asyncio.CancelledError:
                await task  # Keep the slot until the rendering thread really stops.
                raise

    templates_dir = "templates"
    templates = _build_templates(templates_dir)
    paradoxes_path = Path(__file__).parent / "paradoxes.json"
    analysis_prompt_path = Path(__file__).parent / templates_dir / "analysis_prompt.txt"

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
            report_generator=report_generator,
            templates=templates,
            paradoxes_path=paradoxes_path,
        )
        app_instance.title = config.APP_NAME
        app_instance.version = config.VERSION
        logger.info("Starting %s v%s", config.APP_NAME, config.VERSION)
        services = app_instance.state.services
        services.experiment_runner.task_tracker = lambda run_id, coro: _track_run_task(app_instance, run_id, coro)
        await _mark_interrupted_runs(app_instance, services)
        run_metadata = await services.storage.list_runs()
        for meta in await services.experiment_storage.list_experiments():
            exp = await services.experiment_storage.get_experiment(meta["id"])
            if exp.get("status") == "running":
                exp["status"] = "interrupted"
                for run_meta in run_metadata:
                    if run_meta.get("experimentId") == exp["id"] and run_meta["runId"] not in exp.setdefault("runIds", []):
                        exp["runIds"].append(run_meta["runId"])
                for rid in exp.get("runIds", []):
                    try:
                        saved = await services.storage.get_run(rid)
                    except (FileNotFoundError, ValueError):
                        saved = {"status": "missing"}
                    exp.setdefault("conditionStates", {})[rid] = saved.get("status", "interrupted")
                await services.experiment_storage.save_experiment(exp["id"], exp)
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
            await ai_service.close()
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
        services: AppServices | None = getattr(request.app.state, "services", None)
        if services is not None:
            response.headers["X-App-Version"] = services.config.VERSION
        return response

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request, runId: str | None = None) -> HTMLResponse:
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
                    paradox = resolve_paradox(target_run, paradoxes)
                    vm = RunViewModel.build(target_run, paradox)
                    vm["config_analyst_model"] = config.ANALYST_MODEL
                    recent_run_contexts.insert(0, vm)
                except (FileNotFoundError, ValueError):
                    pass

        initial_paradox = random.choice(paradoxes) if paradoxes else None  # noqa: S311 - picks a demo scenario, not a secret
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
        services: AppServices | None = getattr(request.app.state, "services", None)
        version = services.config.VERSION if services else "uninitialized"
        return {
            "status": "healthy" if services else "starting",
            "version": version,
            "timestamp": datetime.now(UTC).isoformat(),
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
                    "cohort": fp_data.get("cohort", []),
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

    @app.get("/fragments/runs/{run_id}")
    async def run_fragment(request: Request, run_id: str) -> HTMLResponse:
        _validate_run_id(run_id)
        services = _get_services(request)
        try:
            run = await services.storage.get_run(run_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Run not found") from exc
        vm = RunViewModel.build(run, resolve_paradox(run, []))
        vm["config_analyst_model"] = services.config.ANALYST_MODEL
        return services.templates.TemplateResponse(request, "partials/result_item.html", {"ctx": vm})

    @app.get("/api/runs/{run_id}")
    async def get_run(request: Request, run_id: str) -> Any:
        services = _get_services(request)
        _validate_run_id(run_id)
        try:
            run_data = await services.storage.get_run(run_id)
            if request.headers.get("HX-Request"):
                # This body is verbatim model output and is NOT escaped. HTMX
                # ignores Content-Type and swaps with innerHTML by default, so
                # the caller MUST use hx-swap="textContent"
                # (templates/partials/result_item.html). Removing that attribute
                # reintroduces model-controlled HTML into the DOM.
                return Response(
                    content=json.dumps(run_data, indent=2),
                    media_type="text/plain",
                )
            return run_data
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Run not found.")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            logger.error("Failed to get run %s: %s", run_id, exc)
            raise HTTPException(status_code=500, detail="Failed to retrieve run data.") from exc

    @app.post("/api/runs/{run_id}/resume")
    async def resume_run(request: Request, run_id: str) -> dict:
        _validate_run_id(run_id)
        services = _get_services(request)
        try:
            run_data = await _resume_run_by_id(request.app, services, run_id)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Run not found.")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            logger.error("Failed to resume run %s: %s", run_id, exc)
            raise HTTPException(status_code=500, detail="Failed to resume run.") from exc
        return {"runId": run_id, "status": run_data.get("status")}

    @app.post("/api/runs/{run_id}/cancel")
    async def cancel_run(request: Request, run_id: str) -> dict:
        _validate_run_id(run_id)
        services = _get_services(request)
        active_tasks: dict[str, asyncio.Task[dict[str, Any]]] = getattr(
            request.app.state, "active_run_tasks", {}
        )
        task = active_tasks.get(run_id)
        if task is None or task.done():
            raise HTTPException(status_code=404, detail="No active run to cancel.")
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        try:
            run_data = await services.storage.get_run(run_id)
        except FileNotFoundError:
            run_data = {"runId": run_id}
        except Exception as exc:
            logger.error("Failed to load run %s during cancel: %s", run_id, exc)
            run_data = {"runId": run_id}
        run_data["status"] = "cancelled"
        run_data["lastError"] = "Run cancelled by user"
        run_data["updatedAt"] = datetime.now(UTC).isoformat()
        try:
            await services.storage.save_run(run_id, run_data)
        except Exception as exc:
            logger.error("Failed to persist cancellation for %s: %s", run_id, exc)
        return {"runId": run_id, "status": "cancelled"}

    @app.post("/api/runs/{run_id}/counterfactual")
    async def create_counterfactual(request: Request, run_id: str) -> Response:
        _validate_run_id(run_id)
        services = _get_services(request)
        try:
            paradoxes = load_paradoxes(services.paradoxes_path)
            services.counterfactual_engine.max_iterations = services.config.MAX_ITERATIONS
            cf_config, cf_run = await services.counterfactual_engine.prepare_counterfactual(run_id, paradoxes)
            _track_run_task(request.app, cf_run["runId"], _execute_persisted_run(services, cf_config, cf_run))
            if request.headers.get("HX-Request"):
                paradox = resolve_paradox(cf_run, paradoxes)
                vm = RunViewModel.build(cf_run, paradox)
                vm["config_analyst_model"] = services.config.ANALYST_MODEL
                return services.templates.TemplateResponse(
                    request,
                    "partials/result_item.html",
                    {"ctx": vm},
                )
            return JSONResponse(content=cf_run, status_code=202)
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
        exp_id = f"exp_{int(datetime.now(UTC).timestamp())}_{uuid.uuid4().hex[:6]}"
        
        record = ExperimentRecord(
            id=exp_id,
            title=exp_req.title,
            paradoxIds=exp_req.paradoxIds,
            conditions=exp_req.conditions,
            status="pending",
            tags=exp_req.tags or [],
            createdAt=datetime.now(UTC).isoformat(),
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
            raise HTTPException(status_code=500, detail="Failed to retrieve experiments") from exc

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
        except Exception as exc:
            logger.error("Failed to get experiment %s: %s", exp_id, exc)
            raise HTTPException(status_code=500, detail="Failed to retrieve experiment") from exc
            
    @app.post("/api/experiments/{exp_id}/execute")
    async def execute_experiment(request: Request, exp_id: str) -> Response:
        _validate_experiment_id(exp_id)
        services = _get_services(request)
        
        try:
            exp_data = await services.experiment_storage.claim_experiment(exp_id)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Experiment not found")
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

        async def execute_manifest() -> dict[str, Any]:
            try:
                paradoxes = load_paradoxes(services.paradoxes_path)
                result = await services.experiment_runner.execute_experiment(exp_id, exp_data, paradoxes)
                return result.model_dump(by_alias=True)
            except Exception as exc:
                logger.error("Experiment execution failed for %s: %s", exp_id, exc)
                latest = await services.experiment_storage.get_experiment(exp_id)
                latest["status"] = "failed"
                latest.setdefault("errors", []).append(safe_error_message(exc))
                await services.experiment_storage.save_experiment(exp_id, latest)
                raise

        _track_run_task(request.app, exp_id, execute_manifest())
        return JSONResponse(content=exp_data, status_code=202)

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
    async def execute_query(request: Request, query_request: QueryRequest) -> Response:
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
            _track_run_task(
                request.app,
                run_id,
                _execute_persisted_run(services, run_config, initial_run),
            )
            run_data = initial_run

            if request.headers.get("HX-Request"):
                vm = RunViewModel.build(run_data, paradox)
                vm["config_analyst_model"] = config.ANALYST_MODEL
                return services.templates.TemplateResponse(
                    request,
                    "partials/result_item.html",
                    {"ctx": vm},
                )

            return JSONResponse(content=run_data, status_code=202)
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
                        await services.storage.update_run(run_id, lambda latest: latest.setdefault("insights", []).append(insight_data))
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

            if not regenerate and selected_insight(run_data):
                insight = selected_insight(run_data)
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

            run_data = await services.storage.update_run(run_id, lambda latest: latest.setdefault("insights", []).append(insight_data))

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
            logger.exception("Analysis failed for %s", run_id)
            # HTMX callers need 200 to swap the error fragment into the modal;
            # non-HTMX callers get a proper 500.
            error_status = 200 if request.headers.get("HX-Request") else 500
            return services.templates.TemplateResponse(
                request,
                "partials/analysis_error.html",
                {
                    # Provider exceptions carry raw upstream response bodies; keep
                    # them in the log, not in the browser.
                    "error_message": safe_error_message(exc),
                    "model": model_to_use or "",
                    "run_id": run_id,
                },
                status_code=error_status,
            )

    @app.get("/reports/runs/{run_id}", response_class=HTMLResponse)
    async def view_run_report(request: Request, run_id: str, theme: str | None = None, view: str = "brief") -> HTMLResponse:
        services = _get_services(request)
        _validate_run_id(run_id)
        if view not in ("brief", "slides"):
            raise HTTPException(status_code=400, detail="Choose brief or slides")
        try:
            run = await services.storage.get_run(run_id)
            paradox = resolve_paradox(run, [])
            narrative = run.get("narrative") if run.get("narrativeEvidenceHash") == evidence_hash(run) else None
            content = await render_export(
                (services.report_generator.generate_insight_slides if view == "slides"
                 else services.report_generator.generate_html_report), run, paradox,
                selected_insight(run), narrative,
                theme=theme if theme in ("dark", "light") else services.config.REPORT_THEME,
            )
            return HTMLResponse(content, headers={"Cache-Control": "no-store"})
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Run not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            logger.error("Report rendering failed: %s", exc)
            raise HTTPException(status_code=503, detail="Report rendering unavailable") from exc

    @app.get("/reports/compare", response_class=HTMLResponse)
    async def view_comparison_report(request: Request, run_ids: str, theme: str | None = None) -> HTMLResponse:
        services = _get_services(request)
        ids = [rid.strip() for rid in run_ids.split(",") if rid.strip()]
        if not 2 <= len(ids) <= 4:
            raise HTTPException(status_code=400, detail="Provide 2–4 distinct run IDs")
        for rid in ids:
            _validate_run_id(rid)
        try:
            runs = [await services.storage.get_run(rid) for rid in ids]
            validate_comparison(runs)
            content = await render_export(
                services.report_generator.generate_comparison_html, runs, resolve_paradox(runs[0], []),
                [selected_insight(run) for run in runs],
                theme=theme if theme in ("dark", "light") else services.config.REPORT_THEME,
            )
            return HTMLResponse(content, headers={"Cache-Control": "no-store"})
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Run not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            logger.error("Report rendering failed: %s", exc)
            raise HTTPException(status_code=503, detail="Report rendering unavailable") from exc

    @app.get("/api/runs/{run_id}/export")
    async def export_run(request: Request, run_id: str, format: str = "json") -> Response:
        """Export run data in JSON or PPTX format (Phase 6)."""
        services = _get_services(request)
        _validate_run_id(run_id)
        try:
            run_data = await services.storage.get_run(run_id)
            paradoxes = load_paradoxes(services.paradoxes_path)
            paradox = resolve_paradox(run_data, paradoxes)

            if format == "json":
                from lib.export_data import export_run_json
                data = export_run_json(run_data, paradox, selected_insight(run_data))
                return JSONResponse(content=data)

            if format == "pptx":
                from lib.export_pptx import generate_pptx, pptx_available
                if not pptx_available():
                    raise HTTPException(status_code=503, detail="PowerPoint export unavailable")
                insight = None
                if "insights" in run_data and run_data["insights"]:
                    insight = selected_insight(run_data)
                pptx_bytes = await render_export(generate_pptx, run_data, paradox, insight)
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

    uvicorn.run("main:app", host=AppConfig().APP_HOST, port=8000, reload=False)
