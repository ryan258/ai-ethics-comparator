"""
Ethics Fingerprinting Module - Arsenal Module
Compute ethical fingerprints across runs for a given model.
"""

from typing import Dict, Any, List
from lib.storage import RunStorage
from lib.stats import wilson_confidence_interval
import logging

logger = logging.getLogger(__name__)

async def compute_model_fingerprint(model_id: str, storage: RunStorage) -> Dict[str, Any]:
    """
    Computes an ethics fingerprint for a specific model by aggregating
    'moral_complexes' across all its runs.
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
                
    counts: Dict[str, int] = {}
    total_insights = 0
    
    for run in model_runs:
        insights = run.get("insights", [])
        if not insights:
            continue
            
        latest_insight = insights[-1]
        content = latest_insight.get("content", {})
        if isinstance(content, dict):
            complexes = content.get("moral_complexes", [])
            if isinstance(complexes, list):
                total_insights += 1
                for c in complexes:
                    if isinstance(c, dict) and isinstance(c.get("label"), str):
                        c_clean = c["label"].strip()
                        counts[c_clean] = counts.get(c_clean, 0) + 1
                        
    fingerprint = []
    if total_insights > 0:
        for complex_name, count in counts.items():
            ci = wilson_confidence_interval(count, total_insights)
            fingerprint.append({
                "dimension": complex_name,
                "count": count,
                "prevalence": ci["proportion"],
                "lowerBound": ci["lower"],
                "upperBound": ci["upper"]
            })
            
    # Sort by prevalence descending
    fingerprint.sort(key=lambda x: x["prevalence"], reverse=True)
    
    return {
        "modelName": model_id,
        "totalRunsWithInsights": total_insights,
        "fingerprint": fingerprint
    }
