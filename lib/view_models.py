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
    """Builder for Run Result View Data"""

    @staticmethod
    def build(run_data: Dict[str, Any], paradox: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepare a run record for display.
        Handles missing keys, formatting, and pre-rendering.
        """

        # 1. Extract Groups
        groups = run_data.get("groups", {})
        group1_desc = groups.get("group1") or paradox.get("group1Default", "")
        group2_desc = groups.get("group2") or paradox.get("group2Default", "")

        # 2. Pre-render Scenario Prompt
        prompt_template = paradox.get("promptTemplate", "")
        # Robust replacement
        scenario_html = safe_markdown(
            prompt_template.replace("{{GROUP1}}", group1_desc)
                           .replace("{{GROUP2}}", group2_desc)
        )

        # 3. Format Statistics
        summary = run_data.get("summary", {})
        g1_stats = summary.get("group1", {})
        g2_stats = summary.get("group2", {})

        p1 = f"{g1_stats.get('percentage', 0):.1f}"
        p2 = f"{g2_stats.get('percentage', 0):.1f}"

        # 4. Analysis/Insight
        insights = run_data.get("insights", [])
        insight_html = Markup("")
        insight_model = ""
        has_insight = False

        if insights:
            latest = insights[-1]
            insight_content = latest.get("content", "")
            insight_model = latest.get("analystModel", "Unknown")
            insight_html = safe_markdown(insight_content)
            has_insight = True

        return {
            "run_id": run_data.get("runId", "unknown"),
            "model_name": run_data.get("modelName", "Unknown"),
            "paradox_title": paradox.get("title", "Unknown Paradox"),
            "paradox_type": paradox.get("type", "unknown"),

            # Scenario
            "scenario_html": scenario_html,
            "group1_desc": group1_desc,
            "group2_desc": group2_desc,

            # Stats
            "p1": p1,
            "p2": p2,
            "count1": g1_stats.get("count", 0),
            "count2": g2_stats.get("count", 0),

            # Analysis
            "has_insight": has_insight,
            "insight_html": insight_html,
            "insight_model": insight_model,

            # Raw Data (for JSON dump)
            "run_data_json": json.dumps(run_data, indent=2),

            # Original Logic Objects (if strictly needed by template logic, but try to avoid)
            # Keeping these for minimal friction if needed
            "_raw_run": run_data
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
