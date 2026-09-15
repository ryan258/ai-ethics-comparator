"""Regression tests for D-02: the fingerprint must discriminate between models.

The analyst prompt asks for a per-complex `count` (intensity). The fingerprint
used to discard it and increment by presence instead. Because almost every
dilemma engages almost every moral complex at least once, presence saturates
near 1.0 and every model produced the same profile.

These tests pin the two properties that matter: the intensity is used, and two
models with genuinely different reasoning produce genuinely different profiles.
"""

from __future__ import annotations

from lib.evidence import ANALYSIS_VERSION, evidence_hash
from lib.fingerprint import compute_model_fingerprint


class FakeStorage:
    """Minimal RunStorage stand-in: list_runs + get_run over in-memory dicts."""

    def __init__(self, runs: list[dict]) -> None:
        self._runs = {run["runId"]: run for run in runs}

    async def list_runs(self) -> list[dict]:
        return [{"runId": r["runId"], "modelName": r["modelName"]} for r in self._runs.values()]

    async def get_run(self, run_id: str) -> dict:
        return self._runs[run_id]


def _run(run_id: str, model: str, complexes: list[tuple[str, int]]) -> dict:
    run = {
        "status": "completed",
        "iterationCount": 10,
        "responses": [{"iteration": n, "explanation": "sample"} for n in range(1, 11)],
        "runId": run_id,
        "modelName": model,
        "insights": [
            {
                "analystModel": "test/analyst",
                "content": {
                    "moral_complexes": [
                        {"label": label, "count": count, "justification": "x"}
                        for label, count in complexes
                    ]
                },
            }
        ],
    }

    run["insights"][0].update(analysisVersion=ANALYSIS_VERSION, evidenceHash=evidence_hash(run))
    return run


def _by_dimension(fingerprint: dict) -> dict[str, dict]:
    return {d["dimension"]: d for d in fingerprint["fingerprint"]}


async def test_intensity_decides_dominance_not_presence() -> None:
    """A complex mentioned once must not rank equal to one mentioned five times."""
    storage = FakeStorage([
        _run("m-001", "a/b", [("Consequence", 5), ("Purity", 1)]),
        _run("m-002", "a/b", [("Consequence", 4), ("Purity", 1)]),
    ])

    dims = _by_dimension(await compute_model_fingerprint("a/b", storage))

    assert dims["Consequence"]["prevalence"] == 1.0
    assert dims["Purity"]["prevalence"] == 0.0
    # Both were *present* in both runs -- the old metric would tie them at 1.0.
    assert dims["Purity"]["presentInRuns"] == 2


async def test_profiles_separate_across_models() -> None:
    """The whole point of a fingerprint: two models must look different."""
    storage = FakeStorage([
        _run("c-001", "consequentialist/m", [("Consequence", 8), ("Duty", 1)]),
        _run("c-002", "consequentialist/m", [("Consequence", 7), ("Duty", 2)]),
        _run("d-001", "deontologist/m", [("Consequence", 1), ("Duty", 9)]),
        _run("d-002", "deontologist/m", [("Consequence", 2), ("Duty", 8)]),
    ])

    conseq = _by_dimension(await compute_model_fingerprint("consequentialist/m", storage))
    deont = _by_dimension(await compute_model_fingerprint("deontologist/m", storage))

    assert conseq["Consequence"]["prevalence"] == 1.0
    assert deont["Duty"]["prevalence"] == 1.0
    assert conseq["Consequence"]["intensityShare"] > deont["Consequence"]["intensityShare"]


async def test_intensity_share_uses_the_full_signal() -> None:
    storage = FakeStorage([_run("s-001", "a/b", [("Duty", 3), ("Purity", 1)])])

    dims = _by_dimension(await compute_model_fingerprint("a/b", storage))

    assert dims["Duty"]["intensityShare"] == 0.75
    assert dims["Purity"]["intensityShare"] == 0.25


async def test_ties_count_every_tied_label_as_dominant() -> None:
    storage = FakeStorage([_run("t-001", "a/b", [("Duty", 4), ("Consequence", 4)])])

    dims = _by_dimension(await compute_model_fingerprint("a/b", storage))

    assert dims["Duty"]["prevalence"] == 1.0
    assert dims["Consequence"]["prevalence"] == 1.0


async def test_missing_or_malformed_old_insights_require_revalidation() -> None:
    """Older insights do not meet the evidence contract and must be excluded."""
    storage = FakeStorage([
        {
            "runId": "o-001",
            "modelName": "a/b",
            "insights": [
                {
                    "content": {
                        "moral_complexes": [
                            {"label": "Duty"},
                            {"label": "Purity", "count": "not-a-number"},
                            {"label": "  "},
                            "not-a-dict",
                        ]
                    }
                }
            ],
        }
    ])

    result = await compute_model_fingerprint("a/b", storage)
    dims = _by_dimension(result)

    assert result["totalRunsWithInsights"] == 0
    assert dims == {}


async def test_model_with_no_insights_returns_empty_fingerprint() -> None:
    storage = FakeStorage([{"runId": "n-001", "modelName": "a/b", "insights": []}])

    result = await compute_model_fingerprint("a/b", storage)

    assert result["totalRunsWithInsights"] == 0
    assert result["fingerprint"] == []


async def test_zero_counts_and_incomplete_cohorts_are_preserved() -> None:
    zero = _run("z-001", "a/b", [("Duty", 0), ("Purity", 0)])
    incomplete = _run("z-002", "a/b", [("Duty", 3)])
    incomplete["status"] = "interrupted"
    result = await compute_model_fingerprint("a/b", FakeStorage([zero, incomplete]))
    assert result["totalRunsWithInsights"] == 1
    assert [r["runId"] for r in result["cohort"]] == ["z-001"]
    assert all(d["prevalence"] == 0 and d["intensityTotal"] == 0 and d["presentInRuns"] == 0 for d in result["fingerprint"])
