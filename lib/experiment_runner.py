"""
Experiment Runner - Arsenal Module
Handles experiment execution, validation, and error boundary logic.
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from pydantic import BaseModel

from lib.query_processor import QueryProcessor
from lib.storage import RunStorage, ExperimentStorage
from lib.paradoxes import get_paradox_by_id, Paradox
from lib.validation import ConditionConfig, ExperimentRecord

logger = logging.getLogger(__name__)

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
            try:
                cond_cfg = ConditionConfig(**condition)
                run_cfg = cond_cfg.to_run_config(pdx, self.max_iterations)
                run_data_res = await self.query_processor.execute_run(run_cfg)

                # Check for iteration failures
                errors = [r.get("error") for r in run_data_res.get("responses", []) if r.get("error")]
                if errors:
                    run_data_res["partial_failure"] = True
                    run_data_res["errors"] = errors

                run_id = await self.run_storage.create_run(condition["modelName"], run_data_res)
                return ConditionResult(run_id=run_id, error=None, partial=bool(errors))
            except Exception as e:
                logger.error("Condition failed: %s", e)
                return ConditionResult(run_id=None, error=str(e), partial=False)
        
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
        exp_data.setdefault("runIds", [])
        
        for res in results:
            if isinstance(res, Exception):
                has_errors = True
                exp_data.setdefault("errors", []).append(str(res))
            elif isinstance(res, ConditionResult):
                if res.run_id:
                    if res.run_id not in exp_data["runIds"]:
                        exp_data["runIds"].append(res.run_id)
                if res.error:
                    has_errors = True
                    exp_data.setdefault("errors", []).append(res.error)
                if res.partial:
                    has_partial = True

        if has_errors:
            exp_data["status"] = "failed" if not exp_data.get("runIds") else "partial"
        elif has_partial:
            exp_data["status"] = "partial"
        else:
            exp_data["status"] = "completed"
            
        await self.experiment_storage.save_experiment(exp_id, exp_data)
        return ExperimentRecord(**exp_data)
