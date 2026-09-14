"""Regression tests for D-03 / Decision D11: stored runs survive library edits.

A run's `paradoxId` points into `paradoxes.json`, which is edited freely. Before
this was enforced, three consumers stopped at a live-library lookup and silently
degraded: JSON/PPTX export emitted a null paradox, the counterfactual fragment
and the home-page run list rendered "Unknown Paradox".

The invariant is that EVERY consumer walks all three tiers. These tests pin it
by deleting the scenario from the library and asserting each surface still
names it.
"""

from __future__ import annotations

import json
from pathlib import Path

from lib.export_data import export_run_json
from lib.paradoxes import resolve_paradox

RETIRED_ID = "retired_scenario"


def _run(**overrides) -> dict:
    base = {
        "runId": "retired-001",
        "modelName": "test/model",
        "paradoxId": RETIRED_ID,
        "paradoxType": "trolley",
        "paradoxTitle": "The Retired Scenario",
        "timestamp": "2026-01-01T00:00:00+00:00",
        "prompt": "You must choose.",
        "iterationCount": 1,
        "completedIterations": 1,
        "status": "completed",
        "options": [
            {"id": 1, "label": "A", "description": "a"},
            {"id": 2, "label": "B", "description": "b"},
        ],
        "responses": [
            {"iteration": 1, "optionId": 1, "decisionToken": "{1}", "explanation": "because"}
        ],
        "summary": {
            "total": 1,
            "options": [
                {"id": 1, "count": 1, "percentage": 100.0},
                {"id": 2, "count": 0, "percentage": 0.0},
            ],
            "undecided": {"count": 0, "percentage": 0.0},
        },
        "paradox": {
            "id": RETIRED_ID,
            "title": "The Retired Scenario",
            "category": "Classic Ethics",
            "promptTemplate": "You must choose.",
            "type": "trolley",
            "options": [
                {"id": 1, "label": "A", "description": "a"},
                {"id": 2, "label": "B", "description": "b"},
            ],
        },
    }
    base.update(overrides)
    return base


# --- tier mechanics ------------------------------------------------------


def test_tier1_live_library_wins_over_snapshot() -> None:
    """Corrections to a still-existing scenario must take effect."""
    corrected = {
        "id": RETIRED_ID,
        "title": "Corrected Title",
        "promptTemplate": "x",
        "options": [{"id": 1, "label": "A", "description": "a"}],
    }
    assert resolve_paradox(_run(), [corrected])["title"] == "Corrected Title"


def test_tier2_snapshot_used_when_library_drops_the_scenario() -> None:
    resolved = resolve_paradox(_run(), [])
    assert resolved["id"] == RETIRED_ID
    assert resolved["title"] == "The Retired Scenario"
    assert resolved["category"] == "Classic Ethics"


def test_tier3_reconstructs_pre_snapshot_runs() -> None:
    """Runs created before D11 carry no `paradox` key and must still resolve."""
    legacy = _run()
    del legacy["paradox"]

    resolved = resolve_paradox(legacy, [])

    assert resolved["id"] == RETIRED_ID
    assert resolved["title"] == "The Retired Scenario"
    assert resolved["promptTemplate"] == "You must choose."
    assert len(resolved["options"]) == 2


def test_resolution_never_returns_an_empty_paradox() -> None:
    """Even a near-empty record resolves to something titled."""
    resolved = resolve_paradox({"runId": "x-001"}, [])
    assert resolved["id"]
    assert resolved["title"]


def test_snapshot_is_copied_not_aliased() -> None:
    """Mutating a resolved paradox must not poison the stored run record."""
    run = _run()
    resolve_paradox(run, [])["title"] = "MUTATED"
    assert run["paradox"]["title"] == "The Retired Scenario"


# --- consumer surfaces ---------------------------------------------------


def test_json_export_keeps_the_paradox_after_library_edit() -> None:
    """D-03's worst symptom: anonymous exported records."""
    run = _run()
    exported = export_run_json(run, resolve_paradox(run, []))

    assert exported["paradox"]["id"] == RETIRED_ID
    assert exported["paradox"]["title"] == "The Retired Scenario"
    assert exported["paradox"]["category"] == "Classic Ethics"


def _write_run(app, run: dict) -> None:
    root = Path(app.state.services.storage.results_root)
    root.mkdir(parents=True, exist_ok=True)
    (root / f"{run['runId']}.json").write_text(json.dumps(run))


def test_home_page_names_a_run_whose_scenario_left_the_library(client) -> None:
    _write_run(client.app, _run())

    html = client.get("/").text

    assert "The Retired Scenario" in html
    assert "Unknown Paradox" not in html


def test_export_route_names_a_run_whose_scenario_left_the_library(client) -> None:
    _write_run(client.app, _run())

    payload = client.get("/api/runs/retired-001/export?format=json").json()

    assert payload["paradox"]["title"] == "The Retired Scenario"


def test_export_route_survives_a_run_with_no_paradox_id(client) -> None:
    """Direct key access here used to raise KeyError -> 500."""
    run = _run()
    del run["paradoxId"]
    del run["paradox"]
    _write_run(client.app, run)

    response = client.get("/api/runs/retired-001/export?format=json")

    assert response.status_code == 200
    assert response.json()["paradox"]["title"] == "The Retired Scenario"
