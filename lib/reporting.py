"""
Reporting Module - Arsenal Module
Handles polished PDF generation for experimental runs.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from jinja2 import Environment, FileSystemLoader
except ModuleNotFoundError:  # pragma: no cover - optional dependency guard
    Environment = None  # type: ignore[assignment]
    FileSystemLoader = None  # type: ignore[assignment]

try:
    from weasyprint import HTML
except (ModuleNotFoundError, OSError) as exc:  # pragma: no cover - optional dependency guard
    HTML = None  # type: ignore[assignment]
    WEASYPRINT_IMPORT_ERROR: Exception | None = exc
else:  # pragma: no cover - import side effect only
    WEASYPRINT_IMPORT_ERROR = None

from lib.paradoxes import extract_scenario_text
from lib.pdf_native import NativePdfReportRenderer, pdf_available

logger = logging.getLogger(__name__)


def _format_timestamp(timestamp: object) -> str:
    if not isinstance(timestamp, str) or not timestamp.strip():
        return "Unknown"
    try:
        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError:
        return timestamp
    return parsed.strftime("%B %d, %Y %I:%M %p %Z").strip()


def _normalize_list(value: object) -> List[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _truncate_text(value: object, limit: int) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _build_scenario_excerpt(value: object, limit: int = 420) -> str:
    text = str(value or "").strip()
    if not text:
        return ""

    paragraphs = [
        paragraph.strip()
        for paragraph in text.split("\n\n")
        if paragraph.strip()
    ]
    filtered: List[str] = []
    stop_markers = ("**Decision Context**", "**Instructions**", "**Options**", "**Output Contract")
    for paragraph in paragraphs:
        if paragraph.startswith(stop_markers):
            break
        filtered.append(paragraph)

    excerpt = "\n\n".join(filtered[:2]) if filtered else text
    return _truncate_text(excerpt, limit)


class ReportGenerator:
    """Generate professional PDF reports from run data."""

    def __init__(self, templates_dir: str = "templates") -> None:
        self.templates_dir = Path(templates_dir)
        self.template_name = "reports/pdf_report.html"
        self.env: Optional[Environment] = None
        self.html_template_available = False

        if Environment is not None and FileSystemLoader is not None and self.templates_dir.exists():
            self.env = Environment(loader=FileSystemLoader(str(self.templates_dir)))
            try:
                self.env.get_template(self.template_name)
                self.html_template_available = True
            except Exception as exc:
                logger.warning("PDF template unavailable, native renderer only: %s", exc)

        self.pdf_available = HTML is not None or pdf_available()

    def generate_pdf_report(
        self,
        run_data: Dict[str, Any],
        paradox: Dict[str, Any],
        insight: Optional[Dict[str, Any]] = None,
    ) -> bytes:
        """Generate PDF bytes using WeasyPrint when possible, else native fallback."""
        report = self._build_report_context(run_data, paradox, insight)

        if HTML is not None and self.env is not None and self.html_template_available:
            try:
                return self._generate_weasyprint_pdf(report)
            except Exception as exc:
                logger.warning("WeasyPrint PDF render failed, using native fallback: %s", exc)

        if not pdf_available():
            raise RuntimeError(
                "PDF generation is unavailable because WeasyPrint could not load its native "
                "dependencies and no native fallback backend is installed."
            ) from WEASYPRINT_IMPORT_ERROR

        return NativePdfReportRenderer(report).render()

    def _generate_weasyprint_pdf(self, report: Dict[str, Any]) -> bytes:
        assert self.env is not None
        template = self.env.get_template(self.template_name)
        html_content = template.render(report=report)
        return HTML(string=html_content, base_url=str(self.templates_dir.parent)).write_pdf()

    def _build_report_context(
        self,
        run_data: Dict[str, Any],
        paradox: Dict[str, Any],
        insight: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        options = run_data.get("options", [])
        option_lookup = {
            option.get("id"): option
            for option in options
            if isinstance(option, dict) and isinstance(option.get("id"), int)
        }

        responses: List[Dict[str, Any]] = []
        total_latency = 0.0
        total_prompt_tokens = 0
        total_completion_tokens = 0
        for index, response in enumerate(run_data.get("responses", []), start=1):
            if not isinstance(response, dict):
                continue

            latency = float(response.get("latency", 0.0) or 0.0)
            token_usage = response.get("tokenUsage", {})
            prompt_tokens = int(token_usage.get("prompt_tokens", 0) or 0) if isinstance(token_usage, dict) else 0
            completion_tokens = int(token_usage.get("completion_tokens", 0) or 0) if isinstance(token_usage, dict) else 0
            total_latency += latency
            total_prompt_tokens += prompt_tokens
            total_completion_tokens += completion_tokens

            option_id = response.get("optionId")
            option_meta = option_lookup.get(option_id, {}) if isinstance(option_id, int) else {}
            explanation = str(response.get("explanation", "") or "").strip()
            raw = str(response.get("raw", "") or "").strip()
            display_text = explanation or raw or "No explanation recorded."
            responses.append(
                {
                    "iteration": int(response.get("iteration", index) or index),
                    "decision_token": response.get("decisionToken"),
                    "option_id": option_id if isinstance(option_id, int) else None,
                    "option_label": option_meta.get("label", "Undecided"),
                    "latency_label": f"{latency:.2f}s latency" if latency else "",
                    "token_usage_label": (
                        f"{prompt_tokens} in / {completion_tokens} out"
                        if prompt_tokens or completion_tokens
                        else ""
                    ),
                    "display_text": display_text,
                    "used_raw_fallback": bool(raw and not explanation),
                }
            )

        summary = run_data.get("summary", {})
        summary_options = summary.get("options", []) if isinstance(summary, dict) else []
        max_count = 0
        for option_stat in summary_options:
            if isinstance(option_stat, dict):
                max_count = max(max_count, int(option_stat.get("count", 0) or 0))

        option_stats: List[Dict[str, Any]] = []
        leaders: List[str] = []
        for option_stat in summary_options:
            if not isinstance(option_stat, dict):
                continue
            option_id = option_stat.get("id")
            option_meta = option_lookup.get(option_id, {}) if isinstance(option_id, int) else {}
            count = int(option_stat.get("count", 0) or 0)
            percentage = float(option_stat.get("percentage", 0.0) or 0.0)
            is_leader = bool(count and count == max_count)
            if is_leader:
                leaders.append(option_meta.get("label", f"Option {option_id}"))
            option_stats.append(
                {
                    "id": option_id,
                    "token": f"{{{option_id}}}" if isinstance(option_id, int) else "{?}",
                    "label": option_meta.get("label", f"Option {option_id}"),
                    "description": option_meta.get("description", ""),
                    "count": count,
                    "percentage": percentage,
                    "percentage_label": f"{percentage:.1f}%",
                    "is_leader": is_leader,
                }
            )

        response_count = len(responses)
        lead_choice_label = " / ".join(leaders) if leaders else "No dominant choice"
        lead_choice_support = (
            f"{max_count} of {response_count} responses ({(max_count / response_count * 100):.1f}%)"
            if response_count and max_count
            else "No successful responses recorded."
        )
        mean_latency = total_latency / response_count if response_count else 0.0
        undecided = summary.get("undecided", {}) if isinstance(summary, dict) else {}

        analysis_context: Optional[Dict[str, Any]] = None
        analyst_model = "Not generated"
        if isinstance(insight, dict):
            analyst_model = str(insight.get("analystModel", "Not generated") or "Not generated")
            content = insight.get("content")
            if isinstance(content, dict):
                analysis_context = {
                    "legacy_text": str(content.get("legacy_text", "") or "").strip(),
                    "dominant_framework": str(content.get("dominant_framework", "") or "").strip(),
                    "key_insights": _normalize_list(content.get("key_insights")),
                    "justifications": _normalize_list(content.get("justifications")),
                    "consistency": _normalize_list(content.get("consistency")),
                    "moral_complexes": [
                        {
                            "label": str(item.get("label", "Complex")).strip(),
                            "count": int(item.get("count", 0) or 0),
                            "justification": str(item.get("justification", "") or "").strip(),
                        }
                        for item in content.get("moral_complexes", [])
                        if isinstance(item, dict)
                    ],
                    "reasoning_quality": (
                        {
                            "noticed": _normalize_list(content.get("reasoning_quality", {}).get("noticed"))
                            if isinstance(content.get("reasoning_quality"), dict)
                            else [],
                            "missed": _normalize_list(content.get("reasoning_quality", {}).get("missed"))
                            if isinstance(content.get("reasoning_quality"), dict)
                            else [],
                        }
                    ),
                }

        prompt_hash = str(run_data.get("promptHash", "") or "")
        scenario_text = extract_scenario_text(paradox.get("promptTemplate", ""))
        analysis_snapshot = ""
        if analysis_context:
            if analysis_context.get("dominant_framework"):
                analysis_snapshot = (
                    f"Analyst synthesis framed the run as {analysis_context['dominant_framework']}."
                )
            elif analysis_context.get("key_insights"):
                analysis_snapshot = analysis_context["key_insights"][0]
        if not analysis_snapshot:
            analysis_snapshot = "Analyst synthesis is pending for this run."

        executive_summary = (
            f"Across {response_count} iterations, {lead_choice_label} led with {lead_choice_support.lower()} "
            f"Mean latency was {f'{mean_latency:.2f}s' if response_count else 'n/a'}, and the run consumed "
            f"{total_prompt_tokens + total_completion_tokens:,} total tokens."
        )
        scope_points = [
            f"Decision category: {paradox.get('category', 'Uncategorized')}.",
            (
                f"Sampling depth: {response_count} recorded responses across {len(option_stats)} answer paths."
                if response_count
                else "No recorded responses were available for this report."
            ),
            (
                "Analyst synthesis is included in this edition."
                if analysis_context
                else "Analyst synthesis has not yet been generated for this edition."
            ),
        ]
        readout_points = [
            f"Lead position: {lead_choice_label}.",
            f"Undecided rate: {int(undecided.get('count', 0) or 0)} ({float(undecided.get('percentage', 0.0) or 0.0):.1f}%)."
            if isinstance(undecided, dict)
            else "Undecided rate: 0 (0.0%).",
            f"Prompt fingerprint: {prompt_hash[:12] if prompt_hash else 'n/a'}.",
        ]

        return {
            "run_id": run_data.get("runId", "unknown"),
            "model_name": run_data.get("modelName", "Unknown"),
            "paradox_title": paradox.get("title", "Unknown paradox"),
            "category": paradox.get("category", "Uncategorized"),
            "generated_at_label": _format_timestamp(run_data.get("timestamp")),
            "prompt_hash_short": f"{prompt_hash[:8]}..." if prompt_hash else "n/a",
            "analyst_model": analyst_model,
            "executive_summary": executive_summary,
            "analysis_snapshot": analysis_snapshot,
            "scenario_excerpt": _build_scenario_excerpt(scenario_text),
            "scope_points": scope_points,
            "readout_points": readout_points,
            "response_count": response_count,
            "response_count_support": (
                f"{len(option_stats)} options evaluated"
                if option_stats
                else "No response distribution available"
            ),
            "lead_choice_label": lead_choice_label,
            "lead_choice_support": lead_choice_support,
            "lead_choice_token": next(
                (option["token"] for option in option_stats if option.get("is_leader")),
                "{?}",
            ),
            "mean_latency_label": f"{mean_latency:.2f}s" if response_count else "n/a",
            "latency_support": f"{total_latency:.2f}s total model time" if total_latency else "No latency recorded",
            "token_volume_label": f"{total_prompt_tokens + total_completion_tokens:,}",
            "token_support": f"{total_prompt_tokens:,} prompt / {total_completion_tokens:,} completion",
            "scenario_text": scenario_text,
            "option_stats": option_stats,
            "undecided_count": int(undecided.get("count", 0) or 0) if isinstance(undecided, dict) else 0,
            "undecided_percentage_label": (
                f"{float(undecided.get('percentage', 0.0) or 0.0):.1f}%"
                if isinstance(undecided, dict)
                else "0.0%"
            ),
            "responses": responses,
            "analysis": analysis_context,
        }
