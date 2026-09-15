"""Framework-independent checkpointed execution shared by every run workflow."""
import asyncio
from datetime import UTC, datetime
from typing import Any

from lib.query_errors import safe_error_message
from lib.query_processor import QueryProcessor, RunConfig
from lib.storage import RunStorage


async def execute_persisted_run(
    processor: QueryProcessor, storage: RunStorage, config: RunConfig,
    initial: dict[str, Any],
) -> dict[str, Any]:
    """Execute an already reserved run and persist each accepted iteration."""
    run_id = initial["runId"]

    async def persist(snapshot: dict[str, Any]) -> None:
        await storage.save_run(run_id, {**snapshot, "runId": run_id})

    try:
        result = await processor.execute_run(config, existing_run=initial, progress_callback=persist)
        result.update(runId=run_id, status="completed", updatedAt=datetime.now(UTC).isoformat())
        await persist(result)
        return await storage.get_run(run_id)
    except BaseException as exc:
        status = "interrupted" if isinstance(exc, asyncio.CancelledError) else "failed"
        message = safe_error_message(exc)
        await storage.update_run(run_id, lambda latest: latest.update(
            status=status, lastError=message, updatedAt=datetime.now(UTC).isoformat()))
        raise
