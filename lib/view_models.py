"""
View Models - Arsenal Module
Logic-free data structures for templates.
"""

import json
import html
import re
import markdown
import logging
from typing import Dict, Any, Optional, List
from markupsafe import Markup

logger = logging.getLogger(__name__)

def safe_markdown(text: str) -> Markup:
    """
    Render markdown safely.
    Escapes HTML first, then renders.
    Jinja2's |safe filter should still NOT be used on raw user input.
    """
    if not text:
        return Markup("")
    # 1. Escape HTML (prevents injection of scripts via HTML tags)
    escaped = html.escape(str(text))
    rendered = markdown.markdown(escaped)

    # 3. Enhanced Security Hardening ("No-Bloat" Compliance)
    # Explicitly strip <a> tags (keep content) and <img> tags (remove entirely)
    # prevent phishing or malicious data URIs

    # Strip links: <a href="...">text</a> -> text
    rendered = re.sub(r'<a\s+[^>]*>(.*?)</a>', r'\1', rendered, flags=re.IGNORECASE | re.DOTALL)

    # Strip images: <img ...> -> ""
    rendered = re.sub(r'<img\s+[^>]*>', '', rendered, flags=re.IGNORECASE)

    return Markup(rendered)


class RunViewModel:
    """Builder for Run Result View Data (N-way support)"""

    @staticmethod
    def _build_response_details(
        responses: List[Dict[str, Any]],
        options: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Prepare per-response explanation data for the result card."""
        option_labels: Dict[int, str] = {}
        for option in options:
            option_id = option.get("id")
            if isinstance(option_id, int):
                option_labels[option_id] = str(option.get("label", f"Option {option_id}"))

        response_details: List[Dict[str, Any]] = []
        for idx, response in enumerate(responses, start=1):
            if not isinstance(response, dict):
                continue

            option_id = response.get("optionId")
            decision_token = response.get("decisionToken")
            explanation = response.get("explanation")
            error = response.get("error")
            raw = response.get("raw")

            choice_label = "Undecided"
            if isinstance(option_id, int):
                option_label = option_labels.get(option_id, f"Option {option_id}")
                choice_prefix = decision_token if isinstance(decision_token, str) and decision_token else f"Option {option_id}"
                choice_label = f"{choice_prefix} - {option_label}"
            elif isinstance(decision_token, str) and decision_token.strip():
                choice_label = decision_token.strip()

            meta_parts: List[str] = []
            if response.get("inferred"):
                method = response.get("inferenceMethod")
                if isinstance(method, str) and method.strip():
                    meta_parts.append(f"Inferred via {method.strip()}")
                else:
                    meta_parts.append("Inferred choice")

            reask_count = response.get("reaskCount")
            if isinstance(reask_count, int) and reask_count > 0:
                meta_parts.append(f"Re-asked {reask_count}x")

            response_details.append(
                {
                    "iteration": response.get("iteration", idx),
                    "decision_token": decision_token.strip() if isinstance(decision_token, str) else None,
                    "option_id": option_id if isinstance(option_id, int) else None,
                    "explanation": explanation.strip() if isinstance(explanation, str) else "",
                    "error": error.strip() if isinstance(error, str) else "",
                    "raw": raw.strip() if isinstance(raw, str) else "",
                    "meta_label": " | ".join(meta_parts),
                    "choice_label": choice_label,
                }
            )

        return response_details

    @staticmethod
    def build(run_data: Dict[str, Any], paradox: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepare a run record for display.
        Handles missing keys, formatting, and pre-rendering.
        Supports N-way paradoxes (2-4 options).
        """
        if not isinstance(run_data, dict):
             logger.error(f"Invalid run_data type: {type(run_data)}")
             return {}

        # Basic schema check
        required_keys = ["modelName", "paradoxId", "summary"]
        missing = [k for k in required_keys if k not in run_data]
        if missing:
             logger.warning(f"Run data missing keys: {missing}")

        # 1. Build Options Summary (N-way support)
        options_summary = []
        summary = run_data.get("summary", {})

        if run_data.get("paradoxType") == "trolley":
            options_from_run = run_data.get("options", [])
            options_from_summary = summary.get("options", [])

            # Match stats with option metadata
            for opt_stat in options_from_summary:
                opt_id = opt_stat.get("id", 0)
                opt_meta = next((o for o in options_from_run if o["id"] == opt_id), {})

                options_summary.append({
                    "id": opt_id,
                    "label": opt_meta.get("label", f"Option {opt_id}"),
                    "description": opt_meta.get("description", ""),
                    "count": opt_stat.get("count", 0),
                    "percentage": opt_stat.get("percentage", 0)
                })

        # 2. Extract undecided stats
        undecided = summary.get("undecided", {})
        undecided_count = undecided.get("count", 0)
        undecided_percentage = undecided.get("percentage", 0)
        response_details = RunViewModel._build_response_details(
            run_data.get("responses", []),
            run_data.get("options", []),
        )

        # 3. Pre-render Scenario Prompt (use prompt from run_data if available)
        # Run data stores the fully rendered prompt, so we can just use it
        scenario_html = safe_markdown(run_data.get("prompt", ""))

        # 4. Analysis/Insight
        insights = run_data.get("insights", [])
        insight_html = Markup("")
        insight_model = ""
        has_insight = False

        if insights:
            latest = insights[-1]
            insight_content = latest.get("content", "")
            insight_model = latest.get("analystModel", "Unknown")

            # Handle both string (legacy) and dict (structured) insights
            if isinstance(insight_content, str):
                insight_html = safe_markdown(insight_content)
            elif isinstance(insight_content, dict):
                # For structured insights, check if legacy_text exists
                if "legacy_text" in insight_content:
                    insight_html = safe_markdown(insight_content["legacy_text"])
                else:
                    # Structured insight - show simple preview text
                    insight_html = Markup("<p><em>Analysis complete. Click 'View Analysis' to see insights.</em></p>")
            else:
                insight_html = Markup("<p><em>Invalid insight format</em></p>")

            has_insight = True

        return {
            "run_id": run_data.get("runId", "unknown"),
            "model_name": run_data.get("modelName", "Unknown"),
            "paradox_title": paradox.get("title", "Unknown Paradox"),
            "paradox_type": paradox.get("type", "unknown"),

            # Scenario
            "scenario_html": scenario_html,

            # N-Way Stats
            "options_summary": options_summary,
            "undecided_count": undecided_count,
            "undecided_percentage": undecided_percentage,
            "total_responses": summary.get("total", 0),
            "response_details": response_details,

            # Analysis
            "system_prompt": run_data.get("systemPrompt", ""),
            "has_insight": has_insight,
            "insight_html": insight_html,
            "insight_model": insight_model,

            # Raw Data (for JSON dump)
            "run_data_json": json.dumps(run_data, indent=2),

            # Original Logic Objects (if strictly needed by template logic, but try to avoid)
            "_raw_run": run_data,

            # Audit / Counterfactual Metadata
            "is_counterfactual": run_data.get("isCounterfactual", False),
            "original_run_id": run_data.get("originalRunId", ""),
            "applied_evidence": run_data.get("appliedEvidence", ""),
            "prompt_hash": run_data.get("promptHash", ""),
            "total_latency": sum(r.get("latency", 0) for r in run_data.get("responses", [])),
            "total_prompt_tokens": sum(r.get("tokenUsage", {}).get("prompt_tokens", 0) for r in run_data.get("responses", [])),
            "total_completion_tokens": sum(r.get("tokenUsage", {}).get("completion_tokens", 0) for r in run_data.get("responses", []))
        }

async def fetch_recent_run_view_models(
    storage: Any,
    paradoxes: List[Dict[str, Any]],
    config_analyst_model: Optional[str],
) -> List[Dict[str, Any]]:
    """
    Orchestration helper to fetch, sort, and build view models for the recent runs stream.
    Keeps main.py simple.
    """
    recent_run_contexts = []
    try:
        # Get metadata list first
        all_runs_meta = await storage.list_runs()
        # list_runs now handles sorting safely

        # Top 5 - Fetch FULL data for view model
        for meta in all_runs_meta[:5]:
            try:
                run_id = meta.get("runId")
                if not run_id: continue

                # Fetch complete data
                full_run_data = await storage.get_run(run_id)

                p_id = full_run_data.get("paradoxId")
                paradox = next((p for p in paradoxes if p["id"] == p_id), {})

                # Build View Model
                vm = RunViewModel.build(full_run_data, paradox)
                vm["config_analyst_model"] = config_analyst_model

                recent_run_contexts.append(vm)

            except Exception as inner_e:
                logger.warning(f"Failed to load run {meta.get('runId')}: {inner_e}")
                continue

    except Exception as e:
        logger.error(f"Failed to load recent runs: {e}")

    return recent_run_contexts
