"""
Experiment Runner - Arsenal Module
Handles experiment execution, validation, and error boundary logic.
"""

import asyncio
import logging
from collections.abc import Callable, Coroutine
from typing import Any

from pydantic import BaseModel

from lib.experiment_state import reconcile_experiment
from lib.paradoxes import Paradox, get_paradox_by_id
from lib.query_errors import safe_error_message
from lib.query_processor import QueryProcessor, RunConfig
from lib.run_executor import execute_persisted_run
from lib.storage import ExperimentStorage, RunStorage
from lib.validation import ConditionConfig, ExperimentRecord

logger = logging.getLogger(__name__)


def condition_to_run_config(
    condition: ConditionConfig,
    paradox: Paradox,
    max_allowed_iterations: int,
) -> RunConfig:
    """Convert a validated condition into an executable run configuration.

    Lives here rather than on ConditionConfig so `lib/validation.py` stays a
    pure shape-validation layer with no dependency on the query processor.
    """
    iters = (
        condition.iterations
        if condition.iterations is not None
        else min(10, max_allowed_iterations)
    )
    if iters > max_allowed_iterations:
        raise ValueError(
            f"Requested iterations ({iters}) exceeds maximum allowed ({max_allowed_iterations})"
        )

    return RunConfig(
        modelName=condition.modelName,
        paradox=paradox,
        systemPrompt=condition.systemPrompt,
        params=condition.params.model_dump(),
        iterations=iters,
        shuffle_options=condition.shuffle_options,
        shuffle_seed=condition.shuffle_seed,
    )


class ConditionResult(BaseModel):
    run_id: str | None
    error: str | None
    partial: bool = False

class ExperimentRunner:
    def __init__(
        self,
        query_processor: QueryProcessor,
        run_storage: RunStorage,
        experiment_storage: ExperimentStorage,
        max_iterations: int = 10,
        max_concurrent_conditions: int = 4,
    ) -> None:
        self.task_tracker: Callable[[str, Coroutine[Any, Any, dict[str, Any]]], asyncio.Task[dict[str, Any]]] | None = None
        self.query_processor = query_processor
        self.run_storage = run_storage
        self.experiment_storage = experiment_storage
        self.max_iterations = max_iterations
        self.max_concurrent_conditions = max(1, max_concurrent_conditions)

    async def _mark_run_failed(self, run_id: str, error_message: str) -> None:
        """Record a condition failure on its reserved run file (best effort)."""
        try:
            run_data = await self.run_storage.get_run(run_id)
        except Exception:
            return
        run_data["status"] = "failed"
        run_data["lastError"] = error_message
        try:
            await self.run_storage.save_run(run_id, run_data)
        except Exception as exc:
            logger.error("Failed to persist failure state for run %s: %s", run_id, exc)

    async def execute_experiment(
        self, exp_id: str, exp_data: dict[str, Any], paradoxes: list[Paradox],
    ) -> ExperimentRecord:
        try:
            await self._execute_experiment(exp_id, exp_data, paradoxes)
        finally:
            await self.experiment_storage.update_experiment(exp_id, lambda latest: latest.update(executionActive=False))
            await reconcile_experiment(self.run_storage, self.experiment_storage, exp_id)
        return ExperimentRecord(**await self.experiment_storage.get_experiment(exp_id))

    async def _execute_experiment(
        self, exp_id: str, exp_data: dict[str, Any], paradoxes: list[Paradox],
    ) -> ExperimentRecord:
        existing: dict[str, dict[str, Any]] = {}
        for rid in exp_data.get("runIds", []):
            run = await self.run_storage.get_run(rid)
            key = run.get("experimentConditionKey")
            if not key:
                matches = [i for i, c in enumerate(exp_data.get("conditions", []))
                           if c == run.get("experimentCondition")]
                if len(matches) != 1:
                    raise ValueError("Legacy condition identity is ambiguous; resume its individual run instead")
                key = f"{run.get('paradoxId')}:{matches[0]}"
            existing[key] = run
        jobs: list[tuple[Paradox, dict[str, Any], str]] = []
        for pid in exp_data.get("paradoxIds", []):
            pdx = get_paradox_by_id(paradoxes, pid)
            if pdx is None:
                raise ValueError(f"Scenario no longer exists: {pid}; individual saved runs remain resumable")
            for index, condition in enumerate(exp_data.get("conditions", [])):
                jobs.append((pdx, condition, f"{pid}:{index}"))

        async def run_condition(pdx: Paradox, condition: dict[str, Any], key: str) -> None:
            initial = existing.get(key)
            if initial and initial.get("status") == "completed":
                return  # Includes terminal undecided outcomes; never rewrite evidence.
            cond = ConditionConfig(**condition)
            config = condition_to_run_config(cond, pdx, self.max_iterations)
            if initial:
                config = RunConfig(modelName=initial["modelName"], paradox=initial.get("paradox") or pdx,
                    iterations=initial["iterationCount"], params=initial.get("params", {}),
                    systemPrompt=initial.get("systemPrompt", ""),
                    shuffle_options=bool(initial.get("shufflePerIteration") or initial.get("shuffleMapping")))
                if config.iterations > self.max_iterations:
                    raise ValueError("Saved condition exceeds the current iteration limit")
                initial = await self.run_storage.update_run(initial["runId"], lambda latest: latest.update(status="running", lastError=None))
            else:
                initial = self.query_processor.initialize_run_data(config)
                initial.update(experimentId=exp_id, experimentCondition=condition, experimentConditionKey=key)
                async def reserve() -> None:
                    rid = await self.run_storage.create_run(cond.modelName, initial)
                    def attach(latest: dict[str, Any]) -> None:
                        latest.setdefault("runIds", []).append(rid)
                        latest.setdefault("conditionStates", {})[rid] = "running"
                    await self.experiment_storage.update_experiment(exp_id, attach)
                reservation = asyncio.create_task(reserve())
                try:
                    await asyncio.shield(reservation)
                except asyncio.CancelledError:
                    await reservation
                    await self.run_storage.update_run(initial["runId"], lambda latest: latest.update(status="interrupted"))
                    raise
            run_id = initial["runId"]
            execution = execute_persisted_run(self.query_processor, self.run_storage, config, initial)
            try:
                if self.task_tracker:
                    await self.task_tracker(run_id, execution)
                else:
                    await execution
            except Exception as exc:
                message = safe_error_message(exc)
                def record_error(latest: dict[str, Any]) -> None:
                    latest.setdefault("errors", []).append(f"{run_id}: {message}")
                await self.experiment_storage.update_experiment(exp_id, record_error)
            finally:
                await reconcile_experiment(self.run_storage, self.experiment_storage, exp_id)

        for start in range(0, len(jobs), self.max_concurrent_conditions):
            outcomes = await asyncio.gather(
                *(run_condition(*job) for job in jobs[start:start + self.max_concurrent_conditions]),
                return_exceptions=True,
            )
            for outcome in outcomes:
                if isinstance(outcome, BaseException):
                    raise outcome
        return ExperimentRecord(**await reconcile_experiment(self.run_storage, self.experiment_storage, exp_id))
