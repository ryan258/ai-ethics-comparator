"""
Ethics Fingerprinting Module - Arsenal Module
Compute ethical fingerprints across runs for a given model.
"""

from typing import Any, Dict, List
from lib.storage import RunStorage
from lib.stats import wilson_confidence_interval
import logging

logger = logging.getLogger(__name__)


def _dominant_labels(complexes: List[Any]) -> tuple[List[str], Dict[str, int]]:
    """Split one run's moral complexes into (dominant labels, intensity by label).

    The analyst returns a per-label `count` -- how strongly that complex showed
    up across the run. Dominance is the argmax of those counts; ties are all
    counted as dominant, because a tie genuinely means no single complex led.
    """
    intensity: Dict[str, int] = {}
    for entry in complexes:
        if not isinstance(entry, dict):
            continue
        label = entry.get("label")
        if not isinstance(label, str) or not label.strip():
            continue
        raw_count = entry.get("count", 1)
        try:
            count = int(raw_count)
        except (TypeError, ValueError):
            count = 1
        # A complex the analyst listed is present at least once, even if it
        # returned 0 or omitted the field.
        intensity[label.strip()] = max(count, 1)

    if not intensity:
        return [], {}

    peak = max(intensity.values())
    return [label for label, count in intensity.items() if count == peak], intensity


async def compute_model_fingerprint(model_id: str, storage: RunStorage) -> Dict[str, Any]:
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

    dominance_counts: Dict[str, int] = {}
    intensity_totals: Dict[str, int] = {}
    presence_counts: Dict[str, int] = {}
    total_insights = 0

    for run in model_runs:
        insights = run.get("insights", [])
        if not insights:
            continue

        latest_insight = insights[-1]
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
        for label in dominant:
            dominance_counts[label] = dominance_counts.get(label, 0) + 1
        for label, count in intensity.items():
            intensity_totals[label] = intensity_totals.get(label, 0) + count
            presence_counts[label] = presence_counts.get(label, 0) + 1

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
        "modelName": model_id,
        "totalRunsWithInsights": total_insights,
        "fingerprint": fingerprint
    }
