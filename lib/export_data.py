"""
JSON data export (Phase 6).

Produces a structured, documented JSON export of a run's report context
for programmatic consumption.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def export_run_json(
    run_data: Dict[str, Any],
    paradox: Dict[str, Any],
    insight: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Produce a structured JSON export suitable for downstream tools."""
    options = run_data.get("options", [])
    option_lookup = {o["id"]: o for o in options if isinstance(o, dict)}

    summary = run_data.get("summary", {})
    summary_options = summary.get("options", []) if isinstance(summary, dict) else []

    distribution: List[Dict[str, Any]] = []
    for opt in summary_options:
        if not isinstance(opt, dict):
            continue
        oid = opt.get("id")
        meta = option_lookup.get(oid, {})
        distribution.append({
            "option_id": oid,
            "label": meta.get("label", f"Option {oid}"),
            "count": int(opt.get("count", 0) or 0),
            "percentage": float(opt.get("percentage", 0.0) or 0.0),
        })

    responses_export: List[Dict[str, Any]] = []
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
        "schema_version": "1.0",
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
        "undecided": summary.get("undecided") if isinstance(summary, dict) else None,
        "responses": responses_export,
        "insight": insight_export,
        "narrative": run_data.get("narrative"),
    }
