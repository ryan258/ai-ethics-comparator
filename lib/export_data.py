"""
JSON data export (Phase 6).

Produces a structured, documented JSON export of a run's report context
for programmatic consumption.
"""

from __future__ import annotations

import copy
from typing import Any

from lib.measurements import build_run_measurements


def export_run_json(
    run_data: dict[str, Any],
    paradox: dict[str, Any],
    insight: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Produce a structured JSON export suitable for downstream tools."""
    measurements = build_run_measurements(run_data)
    summary = measurements.summary()
    distribution = [{"option_id": option.id, "label": option.label,
                     "count": option.count, "percentage": option.percentage}
                    for option in measurements.options]

    responses_export: list[dict[str, Any]] = []
    for resp in run_data.get("responses", []):
        if not isinstance(resp, dict):
            continue
        responses_export.append({
            "iteration": resp.get("iteration"),
            "option_id": resp.get("optionId"),
            "decision_token": resp.get("decisionToken"),
            "explanation": str(resp.get("explanation", "") or "").strip(),
            "latency": float(resp.get("latency", 0.0) or 0.0),
            "token_usage": resp.get("tokenUsage", {}),
        })

    insight_export = None
    if isinstance(insight, dict):
        content = insight.get("content")
        if isinstance(content, dict):
            insight_export = {
                "analyst_model": insight.get("analystModel"),
                "dominant_framework": content.get("dominant_framework"),
                "key_insights": content.get("key_insights", []),
                "moral_complexes": content.get("moral_complexes", []),
            }

    return {
        "schema_version": "2.0",
        "export_kind": "reproducibility",
        "complete_run": copy.deepcopy(run_data),
        "run_id": run_data.get("runId"),
        "model_name": run_data.get("modelName"),
        "paradox": {
            "id": paradox.get("id"),
            "title": paradox.get("title"),
            "category": paradox.get("category"),
        },
        "timestamp": run_data.get("timestamp"),
        "prompt_hash": run_data.get("promptHash"),
        "distribution": distribution,
        "measurement_basis": {"denominator": "recorded_outcomes", "recorded": measurements.recorded,
                              "requested": measurements.requested, "status": measurements.status,
                              "limitations": list(measurements.limitations)},
        "undecided": summary.get("undecided") if isinstance(summary, dict) else None,
        "responses": responses_export,
        "insight": insight_export,
        "narrative": run_data.get("narrative"),
    }
