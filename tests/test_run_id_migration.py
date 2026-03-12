from __future__ import annotations

import asyncio
import json

import pytest

import lib.storage as storage_module


def test_legacy_run_ids_are_migrated_to_strict_format(client) -> None:
    services = client.app.state.services
    results_root = services.storage.results_root
    results_root.mkdir(parents=True, exist_ok=True)

    legacy_path = results_root / "legacyrun.json"
    legacy_data = {
        "modelName": "test/model",
        "paradoxId": "autonomous_vehicle_equal_innocents",
        "paradoxType": "trolley",
        "responses": [{"decisionToken": "{1}", "explanation": "test"}],
        "summary": {"options": [], "undecided": {"count": 0, "percentage": 0}},
        "options": [],
        "timestamp": "2026-01-01T00:00:00+00:00",
    }
    legacy_path.write_text(json.dumps(legacy_data), encoding="utf-8")

    mapping = asyncio.run(services.storage.migrate_legacy_run_ids())
    assert mapping["legacyrun"] == "legacyrun-001"

    strict_path = results_root / "legacyrun-001.json"
    assert strict_path.exists()

    strict_data = json.loads(strict_path.read_text(encoding="utf-8"))
    assert strict_data["runId"] == "legacyrun-001"


def test_create_run_falls_back_when_hard_links_are_unavailable(tmp_path, monkeypatch) -> None:
    storage = storage_module.RunStorage(str(tmp_path))

    def raise_link(_src, _dst) -> None:
        raise OSError("hard links unavailable")

    monkeypatch.setattr(storage_module.os, "link", raise_link)

    run_data = {
        "modelName": "test/model",
        "timestamp": "2026-01-02T00:00:00+00:00",
    }

    run_id = asyncio.run(storage.create_run("test/model", run_data))

    assert run_id == "testmodel-001"
    assert run_data["runId"] == run_id

    run_path = tmp_path / f"{run_id}.json"
    assert run_path.exists()
    stored = json.loads(run_path.read_text(encoding="utf-8"))
    assert stored["runId"] == run_id
    assert stored["modelName"] == "test/model"


def test_create_run_fallback_cleans_reserved_file_on_replace_failure(tmp_path, monkeypatch) -> None:
    storage = storage_module.RunStorage(str(tmp_path))

    def raise_link(_src, _dst) -> None:
        raise OSError("hard links unavailable")

    def raise_replace(_src, _dst) -> None:
        raise OSError("replace failed")

    monkeypatch.setattr(storage_module.os, "link", raise_link)
    monkeypatch.setattr(storage_module.os, "replace", raise_replace)

    with pytest.raises(OSError, match="replace failed"):
        asyncio.run(
            storage.create_run(
                "model",
                {"timestamp": "2026-01-03T00:00:00+00:00"},
            )
        )

    assert list(tmp_path.iterdir()) == []
