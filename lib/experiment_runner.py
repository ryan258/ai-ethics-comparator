"""
Experiment Runner - Arsenal Module
Handles experiment execution, validation, and error boundary logic.
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from pydantic import BaseModel

from lib.query_errors import safe_error_message
from lib.query_processor import QueryProcessor, RunConfig
from lib.storage import RunStorage, ExperimentStorage
from lib.paradoxes import get_paradox_by_id, Paradox
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
        else max_allowed_iterations
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
    )


class ConditionResult(BaseModel):
    run_id: Optional[str]
    error: Optional[str]
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
        self,
        exp_id: str,
        exp_data: Dict[str, Any],
        paradoxes: List[Paradox],
    ) -> ExperimentRecord:
        """
        Executes an experiment condition matrix, enforcing boundaries and limits.
        """
        # 1. Validate paradox IDs up front
        paradox_ids = exp_data.get("paradoxIds", [])
        valid_paradoxes = []
        for p_id in paradox_ids:
            pdx = get_paradox_by_id(paradoxes, p_id)
            if not pdx:
                exp_data["status"] = "failed"
                exp_data["errors"] = exp_data.get("errors", []) + [f"Paradox ID not found: {p_id}"]
                await self.experiment_storage.save_experiment(exp_id, exp_data)
                return ExperimentRecord(**exp_data)
            valid_paradoxes.append(pdx)

        async def run_condition(pdx: Paradox, condition: Dict[str, Any]) -> ConditionResult:
            run_id: Optional[str] = None
            try:
                cond_cfg = ConditionConfig(**condition)
                run_cfg = condition_to_run_config(cond_cfg, pdx, self.max_iterations)

                # Reserve the run file up front and stream progress into it, so a
                # crash mid-matrix leaves resumable runs instead of losing the work.
                initial_run = self.query_processor.initialize_run_data(run_cfg)
                run_id = await self.run_storage.create_run(cond_cfg.modelName, initial_run)
                save_lock = asyncio.Lock()

                async def persist(snapshot: Dict[str, Any]) -> None:
                    async with save_lock:
                        snapshot["runId"] = run_id
                        await self.run_storage.save_run(str(run_id), snapshot)

                run_data_res = await self.query_processor.execute_run(
                    run_cfg,
                    existing_run=initial_run,
                    progress_callback=persist,
                )

                # Iterations that exhausted their re-ask budget are recorded as errors.
                errors = [r.get("error") for r in run_data_res.get("responses", []) if r.get("error")]
                if errors:
                    run_data_res["partial_failure"] = True
                    run_data_res["errors"] = errors

                run_data_res["runId"] = run_id
                run_data_res["status"] = "completed"
                await self.run_storage.save_run(str(run_id), run_data_res)
                return ConditionResult(run_id=run_id, error=None, partial=bool(errors))
            except Exception as e:
                logger.error("Condition failed: %s", e)
                if run_id is not None:
                    await self._mark_run_failed(run_id, safe_error_message(e))
                # Report the reserved run_id even on failure: the file exists and
                # is resumable, and dropping it here orphans it from the experiment.
                return ConditionResult(run_id=run_id, error=safe_error_message(e), partial=False)
        
        jobs: List[tuple[Paradox, Dict[str, Any]]] = []
        for pdx in valid_paradoxes:
            for cond in exp_data.get("conditions", []):
                jobs.append((pdx, cond))

        results: List[ConditionResult | Exception] = []
        for batch_start in range(0, len(jobs), self.max_concurrent_conditions):
            batch = jobs[batch_start : batch_start + self.max_concurrent_conditions]
            batch_results = await asyncio.gather(
                *(run_condition(pdx, cond) for pdx, cond in batch),
                return_exceptions=True,
            )
            results.extend(batch_results)
        
        has_errors = False
        has_partial = False
        succeeded = 0
        exp_data.setdefault("runIds", [])

        for res in results:
            if isinstance(res, Exception):
                has_errors = True
                exp_data.setdefault("errors", []).append(safe_error_message(res))
            elif isinstance(res, ConditionResult):
                if res.run_id and res.run_id not in exp_data["runIds"]:
                    exp_data["runIds"].append(res.run_id)
                if res.error:
                    has_errors = True
                    exp_data.setdefault("errors", []).append(res.error)
                else:
                    succeeded += 1
                if res.partial:
                    has_partial = True

        # Status keys off whether a condition actually succeeded; runIds now also
        # contains the reserved files of failed conditions.
        if has_errors:
            exp_data["status"] = "partial" if succeeded else "failed"
        elif has_partial:
            exp_data["status"] = "partial"
        else:
            exp_data["status"] = "completed"
            
        await self.experiment_storage.save_experiment(exp_id, exp_data)
        return ExperimentRecord(**exp_data)
