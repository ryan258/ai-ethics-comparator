"""Derive manifest status from linked runs; no HTTP or provider dependencies."""
from typing import Any

from lib.storage import ExperimentStorage, RunStorage


async def reconcile_experiment(runs: RunStorage, experiments: ExperimentStorage, exp_id: str) -> dict[str, Any]:
    """Read attached run states inside the serialized manifest update.

    Any is confined to the existing JSON storage adapter contract. RunStorage
    validates the run evidence before it reaches this orchestration adapter.
    """
    async def refresh(latest: dict[str, Any]) -> None:
        current: dict[str, str] = {}
        for run_id in latest.get("runIds", []):
            try:
                run = await runs.get_run(run_id)
                state = str(run.get("status") or "unknown")
                if state == "completed" and any(r.get("error") for r in run.get("responses", [])):
                    state = "partial"
                current[run_id] = state
            except (FileNotFoundError, ValueError):
                current[run_id] = "missing"
        latest["conditionStates"] = current
        expected = len(latest.get("paradoxIds", [])) * len(latest.get("conditions", []))
        values = list(current.values())
        if latest.get("executionActive") or any(value == "running" for value in values):
            latest["status"] = "running"
        elif not values and latest.get("status") == "pending":
            return
        elif len(values) < expected:
            latest["status"] = "interrupted"
        elif values and all(value == "completed" for value in values):
            latest["status"] = "completed"
        elif any(value in {"failed", "missing", "unknown"} for value in values):
            latest["status"] = "failed"
        elif any(value in {"cancelled", "interrupted"} for value in values):
            latest["status"] = "interrupted"
        else:
            latest["status"] = "partial"
    return await experiments.update_experiment(exp_id, refresh)
