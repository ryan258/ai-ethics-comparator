"""Regression tests for storage write validation and metadata caching."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from lib.storage import RunStorage


def _run(run_id: str = "model-001") -> dict:
    return {
        "runId": run_id,
        "timestamp": "2026-01-01T00:00:00+00:00",
        "modelName": "vendor/model",
        "paradoxId": "p",
        "iterationCount": 1,
        "status": "completed",
        "responses": [],
    }


def test_save_run_rejects_ids_that_escape_the_results_root(tmp_path: Path) -> None:
    """Regression: save_run built a path from an unvalidated id."""
    storage = RunStorage(str(tmp_path / "results"))

    for bad_id in ("../escape", "../../etc/passwd", "not-a-run-id", "model-1", ""):
        with pytest.raises(ValueError, match="Invalid run_id"):
            asyncio.run(storage.save_run(bad_id, _run()))

    # Nothing was written anywhere outside the results root.
    assert not (tmp_path / "escape.json").exists()


def test_save_run_accepts_strict_ids(tmp_path: Path) -> None:
    storage = RunStorage(str(tmp_path / "results"))
    asyncio.run(storage.save_run("model-001", _run()))

    saved = json.loads((tmp_path / "results" / "model-001.json").read_text())
    assert saved["runId"] == "model-001"


def test_list_runs_cache_reflects_writes(tmp_path: Path) -> None:
    """The metadata cache must invalidate when a run file changes."""
    storage = RunStorage(str(tmp_path / "results"))
    asyncio.run(storage.save_run("model-001", _run()))

    first = asyncio.run(storage.list_runs())
    assert [r["status"] for r in first] == ["completed"]

    updated = _run()
    updated["status"] = "failed"
    asyncio.run(storage.save_run("model-001", updated))

    second = asyncio.run(storage.list_runs())
    assert [r["status"] for r in second] == ["failed"], "stale cache entry served"


def test_list_runs_drops_deleted_files_from_the_cache(tmp_path: Path) -> None:
    storage = RunStorage(str(tmp_path / "results"))
    asyncio.run(storage.save_run("model-001", _run()))
    assert len(asyncio.run(storage.list_runs())) == 1

    (tmp_path / "results" / "model-001.json").unlink()
    assert asyncio.run(storage.list_runs()) == []
