"""
Ethics Fingerprinting Module - Arsenal Module
Compute ethical fingerprints across runs for a given model.
"""

import logging
from typing import Any

from lib.evidence import selected_insight
from lib.paradoxes import ETHICAL_DIMENSIONS
from lib.stats import wilson_confidence_interval
from lib.storage import RunStorage

logger = logging.getLogger(__name__)


def _dominant_labels(complexes: list[Any]) -> tuple[list[str], dict[str, int]]:
    """Split one run's moral complexes into (dominant labels, intensity by label).

    The analyst returns a per-label `count` -- how strongly that complex showed
    up across the run. Dominance is the argmax of those counts; ties are all
    counted as dominant, because a tie genuinely means no single complex led.
    """
    intensity: dict[str, int] = {}
    for entry in complexes:
        if not isinstance(entry, dict):
            continue
        label = entry.get("label")
        if not isinstance(label, str) or not label.strip():
            continue
        count = entry.get("count")
        if label not in ETHICAL_DIMENSIONS or type(count) is not int or count < 0:
            continue
        intensity[label] = count

    if not intensity:
        return [], {}

    peak = max(intensity.values())
    return [label for label, count in intensity.items() if count == peak and peak > 0], intensity


async def compute_model_fingerprint(model_id: str, storage: RunStorage) -> dict[str, Any]:
    """
    Computes an ethics fingerprint for a specific model by aggregating
    'moral_complexes' across all its runs.

    Two measures are reported per dimension:

    - `prevalence` (+ Wilson interval): the share of runs in which this complex
      DOMINATED. This is a proper Bernoulli trial per run, so the confidence
      interval is meaningful.
    - `intensityShare`: this complex's share of all complex-weight the analyst
      assigned across every run, which uses the full signal rather than just
      the winner.

    Counting mere *presence* -- as this did before -- saturates near 1.0 for
    every model, because almost every dilemma engages almost every complex at
    least once. That produced confident-looking profiles that discriminated
    nothing.
    """
    runs = await storage.list_runs()

    # Filter first, then fetch only matching runs to avoid redundant I/O
    matching_ids = [
        run_meta["runId"]
        for run_meta in runs
        if run_meta.get("modelName") == model_id and run_meta.get("runId")
    ]

    model_runs = []
    for run_id in matching_ids:
        try:
            run_data = await storage.get_run(run_id)
            model_runs.append(run_data)
        except Exception as e:
            logger.warning(f"Failed to load run {run_id} for fingerprinting: {e}")

    dominance_counts: dict[str, int] = {}
    intensity_totals: dict[str, int] = {}
    presence_counts: dict[str, int] = {}
    total_insights = 0
    cohort = []

    for run in model_runs:
        expected = run.get("iterationCount")
        if (run.get("status") != "completed" or type(expected) is not int or expected < 1
                or len(run.get("responses", [])) != expected
                or any(r.get("error") for r in run.get("responses", []))):
            continue
        latest_insight = selected_insight(run)
        if latest_insight is None:
            continue
        content = latest_insight.get("content", {})
        if not isinstance(content, dict):
            continue

        complexes = content.get("moral_complexes", [])
        if not isinstance(complexes, list):
            continue

        dominant, intensity = _dominant_labels(complexes)
        if not intensity:
            continue

        total_insights += 1
        cohort.append({"runId": run.get("runId"), "paradoxId": run.get("paradoxId"),
                       "systemPrompt": run.get("systemPrompt"), "params": run.get("params"),
                       "analystModel": latest_insight.get("analystModel"),
                       "evidenceHash": latest_insight.get("evidenceHash")})
        for label in dominant:
            dominance_counts[label] = dominance_counts.get(label, 0) + 1
        for label, count in intensity.items():
            intensity_totals[label] = intensity_totals.get(label, 0) + count
            presence_counts[label] = presence_counts.get(label, 0) + int(count > 0)

    fingerprint = []
    total_intensity = sum(intensity_totals.values())
    if total_insights > 0:
        for label, weight in intensity_totals.items():
            dominant_in = dominance_counts.get(label, 0)
            ci = wilson_confidence_interval(dominant_in, total_insights)
            fingerprint.append({
                "dimension": label,
                "count": dominant_in,
                "prevalence": ci["proportion"],
                "lowerBound": ci["lower"],
                "upperBound": ci["upper"],
                "intensityShare": round(weight / total_intensity, 4) if total_intensity else 0.0,
                "intensityTotal": weight,
                "presentInRuns": presence_counts.get(label, 0),
            })

    # Sort by dominance, then by intensity share so zero-dominance dimensions
    # still order sensibly against each other.
    fingerprint.sort(key=lambda x: (x["prevalence"], x["intensityShare"]), reverse=True)

    return {
        "cohort": cohort,
        "measurement": "Dominance across the listed completed sampled runs; intervals describe this corpus and evaluator mix, not general model certainty.",
        "modelName": model_id,
        "totalRunsWithInsights": total_insights,
        "fingerprint": fingerprint
    }
