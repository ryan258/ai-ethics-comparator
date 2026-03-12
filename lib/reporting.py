"""
Reporting Module - Arsenal Module
Handles polished PDF generation for experimental runs.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

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
from lib.pdf_charts import (
    PALETTE_DARK,
    PALETTE_LIGHT,
    render_donut_svg,
    render_heatmap_svg,
    render_sparkline_svg,
)
from lib.pdf_native import NativePdfReportRenderer, pdf_available
from lib.report_models import (
    AnalysisContext,
    ComparisonReport,
    DonutSlice,
    MoralComplex,
    NarrativeContext,
    ReasoningQuality,
    ReportOptionStat,
    ReportResponse,
    SectionLink,
    SingleRunReport,
)

logger = logging.getLogger(__name__)


def _format_timestamp(timestamp: object) -> str:
    if not isinstance(timestamp, str) or not timestamp.strip():
        return "Unknown"
    try:
        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError:
        return timestamp
    return parsed.strftime("%B %d, %Y %I:%M %p %Z").strip()


def _normalize_list(value: object) -> list[str]:
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


def _build_scenario_excerpt(value: object, limit: int = 800) -> str:
    text = str(value or "").strip()
    if not text:
        return ""

    paragraphs = [
        paragraph.strip()
        for paragraph in text.split("\n\n")
        if paragraph.strip()
    ]
    filtered: list[str] = []
    stop_markers = ("**Decision Context**", "**Instructions**", "**Options**", "**Output Contract")
    for paragraph in paragraphs:
        if paragraph.startswith(stop_markers):
            break
        filtered.append(paragraph)

    excerpt = "\n\n".join(filtered[:2]) if filtered else text
    return _truncate_text(excerpt, limit)


def _classify_run_pattern(
    option_stats: list[ReportOptionStat],
    response_count: int,
    undecided: object,
) -> str:
    """Classify the run's decision pattern for narrative specialization."""
    if response_count == 0:
        return "ambiguous"
    undecided_pct = 0.0
    if isinstance(undecided, dict):
        undecided_pct = float(undecided.get("percentage", 0.0) or 0.0)
    if undecided_pct > 30:
        return "ambiguous"

    pcts = sorted([float(option.percentage or 0.0) for option in option_stats], reverse=True)
    if not pcts:
        return "ambiguous"
    if pcts[0] >= 99.9:
        return "unanimous"
    if pcts[0] > 70:
        return "dominant"
    above_20 = [pct for pct in pcts if pct > 20]
    if len(above_20) >= 3:
        return "split"
    if len(pcts) >= 2 and abs(pcts[0] - pcts[1]) <= 15:
        return "contested"
    return "dominant"


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
        run_data: dict[str, Any],
        paradox: dict[str, Any],
        insight: Optional[dict[str, Any]] = None,
        narrative: Optional[dict[str, str]] = None,
        *,
        theme: str = "dark",
    ) -> bytes:
        """Generate PDF bytes for a single-run report."""
        report = self._build_report_context(run_data, paradox, insight, narrative, theme=theme)
        return self._render_report(report)

    def generate_comparison_pdf(
        self,
        runs: list[dict[str, Any]],
        paradox: dict[str, Any],
        insights: list[Optional[dict[str, Any]]],
        narrative: Optional[dict[str, str]] = None,
        *,
        theme: str = "dark",
    ) -> bytes:
        """Generate a comparative PDF for multiple runs on the same paradox."""
        from lib.comparison_report import build_comparison_context

        report = build_comparison_context(runs, paradox, insights, narrative, theme=theme)
        return self._render_report(report)

    def _render_report(self, report: SingleRunReport | ComparisonReport) -> bytes:
        """Dispatch rendering explicitly by report type."""
        if isinstance(report, SingleRunReport):
            if HTML is not None and self.env is not None and self.html_template_available:
                try:
                    return self._generate_weasyprint_pdf("reports/pdf_report.html", report)
                except Exception as exc:
                    logger.warning("WeasyPrint PDF render failed, using native fallback: %s", exc)

            if not pdf_available():
                raise RuntimeError(
                    "PDF generation is unavailable because WeasyPrint could not load its native "
                    "dependencies and no native fallback backend is installed."
                ) from WEASYPRINT_IMPORT_ERROR

            return NativePdfReportRenderer(report.model_dump(mode="json"), theme=report.theme).render()

        if HTML is None or self.env is None:
            raise RuntimeError("Comparison PDF generation requires WeasyPrint") from WEASYPRINT_IMPORT_ERROR

        try:
            return self._generate_weasyprint_pdf("reports/comparison_report.html", report)
        except Exception as exc:
            logger.warning("WeasyPrint comparison render failed: %s", exc)
            raise RuntimeError("Comparison PDF generation unavailable") from exc

    def _generate_weasyprint_pdf(
        self,
        template_name: str,
        report: SingleRunReport | ComparisonReport,
    ) -> bytes:
        assert self.env is not None
        template = self.env.get_template(template_name)
        html_content = template.render(report=report)
        return HTML(string=html_content, base_url=str(self.templates_dir.parent)).write_pdf()

    def _build_report_context(
        self,
        run_data: dict[str, Any],
        paradox: dict[str, Any],
        insight: Optional[dict[str, Any]],
        narrative: Optional[dict[str, str]] = None,
        *,
        theme: str = "dark",
    ) -> SingleRunReport:
        options = run_data.get("options", [])
        option_lookup = {
            option.get("id"): option
            for option in options
            if isinstance(option, dict) and isinstance(option.get("id"), int)
        }

        responses: list[ReportResponse] = []
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
            decision_token = response.get("decisionToken")
            responses.append(
                ReportResponse(
                    iteration=int(response.get("iteration", index) or index),
                    decision_token=str(decision_token).strip() if decision_token is not None else None,
                    option_id=option_id if isinstance(option_id, int) else None,
                    option_label=str(option_meta.get("label", "Undecided") or "Undecided"),
                    latency_label=f"{latency:.2f}s latency" if latency else "",
                    token_usage_label=(
                        f"{prompt_tokens} in / {completion_tokens} out"
                        if prompt_tokens or completion_tokens
                        else ""
                    ),
                    display_text=display_text,
                    used_raw_fallback=bool(raw and not explanation),
                )
            )

        summary = run_data.get("summary", {})
        summary_options = summary.get("options", []) if isinstance(summary, dict) else []
        max_count = 0
        for option_stat in summary_options:
            if isinstance(option_stat, dict):
                max_count = max(max_count, int(option_stat.get("count", 0) or 0))

        option_stats: list[ReportOptionStat] = []
        leaders: list[str] = []
        for option_stat in summary_options:
            if not isinstance(option_stat, dict):
                continue
            option_id = option_stat.get("id")
            option_meta = option_lookup.get(option_id, {}) if isinstance(option_id, int) else {}
            count = int(option_stat.get("count", 0) or 0)
            percentage = float(option_stat.get("percentage", 0.0) or 0.0)
            is_leader = bool(count and count == max_count)
            label = str(option_meta.get("label", f"Option {option_id}") or f"Option {option_id}")
            if is_leader:
                leaders.append(label)
            option_stats.append(
                ReportOptionStat(
                    id=option_id if isinstance(option_id, int) else None,
                    token=f"{{{option_id}}}" if isinstance(option_id, int) else "{?}",
                    label=label,
                    description=str(option_meta.get("description", "") or ""),
                    count=count,
                    percentage=percentage,
                    percentage_label=f"{percentage:.1f}%",
                    is_leader=is_leader,
                )
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

        analysis_context: Optional[AnalysisContext] = None
        analyst_model = "Not generated"
        if isinstance(insight, dict):
            analyst_model = str(insight.get("analystModel", "Not generated") or "Not generated")
            content = insight.get("content")
            if isinstance(content, dict):
                reasoning_quality = content.get("reasoning_quality", {})
                analysis_context = AnalysisContext(
                    legacy_text=str(content.get("legacy_text", "") or "").strip(),
                    dominant_framework=str(content.get("dominant_framework", "") or "").strip(),
                    key_insights=_normalize_list(content.get("key_insights")),
                    justifications=_normalize_list(content.get("justifications")),
                    consistency=_normalize_list(content.get("consistency")),
                    moral_complexes=[
                        MoralComplex(
                            label=str(item.get("label", "Complex")).strip(),
                            count=int(item.get("count", 0) or 0),
                            justification=str(item.get("justification", "") or "").strip(),
                        )
                        for item in content.get("moral_complexes", [])
                        if isinstance(item, dict)
                    ],
                    reasoning_quality=ReasoningQuality(
                        noticed=_normalize_list(reasoning_quality.get("noticed"))
                        if isinstance(reasoning_quality, dict)
                        else [],
                        missed=_normalize_list(reasoning_quality.get("missed"))
                        if isinstance(reasoning_quality, dict)
                        else [],
                    ),
                )

        prompt_hash = str(run_data.get("promptHash", "") or "")
        scenario_text = extract_scenario_text(paradox.get("promptTemplate", ""))
        analysis_snapshot = ""
        if analysis_context:
            if analysis_context.dominant_framework:
                analysis_snapshot = (
                    f"Analyst synthesis framed the run as {analysis_context.dominant_framework}."
                )
            elif analysis_context.key_insights:
                analysis_snapshot = analysis_context.key_insights[0]
        if not analysis_snapshot:
            analysis_snapshot = "Analyst synthesis is pending for this run."

        narrative_ctx: Optional[NarrativeContext] = None
        if isinstance(narrative, dict):
            candidate = NarrativeContext(
                executive_narrative=str(narrative.get("executive_narrative", "") or "").strip(),
                response_arc=str(narrative.get("response_arc", "") or "").strip(),
                implications=str(narrative.get("implications", "") or "").strip(),
                scenario_commentary=str(narrative.get("scenario_commentary", "") or "").strip(),
                cross_iteration_patterns=str(narrative.get("cross_iteration_patterns", "") or "").strip(),
                framework_diagnosis=str(narrative.get("framework_diagnosis", "") or "").strip(),
            )
            if any(candidate.model_dump().values()):
                narrative_ctx = candidate

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

        latency_series: list[float] = []
        decision_sequence: list[Optional[int]] = []
        for response in run_data.get("responses", []):
            if isinstance(response, dict):
                latency_series.append(float(response.get("latency", 0.0) or 0.0))
                option_id = response.get("optionId")
                decision_sequence.append(option_id if isinstance(option_id, int) else None)

        chart_option_ids = [option.id for option in option_stats if option.id is not None]

        slice_colors = ["#A6ACCD", "#7C83B0", "#C9A0DC", "#6DBFB8"]
        donut_data: list[DonutSlice] = []
        accent_idx = 0
        for option in option_stats:
            if option.is_leader:
                color = PALETTE_DARK["success"] if theme == "dark" else PALETTE_LIGHT["success"]
            else:
                color = slice_colors[accent_idx % len(slice_colors)]
                accent_idx += 1
            donut_data.append(DonutSlice(label=option.label, value=option.count, color=color))

        active_palette = PALETTE_DARK if theme == "dark" else PALETTE_LIGHT
        donut_svg = render_donut_svg([slice_.model_dump() for slice_ in donut_data], active_palette)
        sparkline_svg = render_sparkline_svg(latency_series, active_palette) if latency_series else ""
        heatmap_svg = render_heatmap_svg(decision_sequence, chart_option_ids, active_palette)

        sections: list[SectionLink] = [SectionLink(id="cover", title="Cover")]
        if narrative_ctx:
            sections.append(SectionLink(id="narrative", title="Interpretive Synthesis"))
        sections.append(SectionLink(id="distribution", title="Choice Distribution"))
        if responses:
            sections.append(SectionLink(id="responses", title="Response Ledger"))
        if analysis_context:
            sections.append(SectionLink(id="analysis", title="Analyst Assessment"))

        return SingleRunReport(
            run_id=str(run_data.get("runId", "unknown") or "unknown"),
            model_name=str(run_data.get("modelName", "Unknown") or "Unknown"),
            paradox_title=str(paradox.get("title", "Unknown paradox") or "Unknown paradox"),
            category=str(paradox.get("category", "Uncategorized") or "Uncategorized"),
            generated_at_label=_format_timestamp(run_data.get("timestamp")),
            prompt_hash_short=f"{prompt_hash[:8]}..." if prompt_hash else "n/a",
            analyst_model=analyst_model,
            executive_summary=executive_summary,
            analysis_snapshot=analysis_snapshot,
            scenario_excerpt=_build_scenario_excerpt(scenario_text),
            scope_points=scope_points,
            readout_points=readout_points,
            response_count=response_count,
            response_count_support=(
                f"{len(option_stats)} options evaluated"
                if option_stats
                else "No response distribution available"
            ),
            lead_choice_label=lead_choice_label,
            lead_choice_support=lead_choice_support,
            lead_choice_token=next((option.token for option in option_stats if option.is_leader), "{?}"),
            mean_latency_label=f"{mean_latency:.2f}s" if response_count else "n/a",
            latency_support=f"{total_latency:.2f}s total model time" if total_latency else "No latency recorded",
            token_volume_label=f"{total_prompt_tokens + total_completion_tokens:,}",
            token_support=f"{total_prompt_tokens:,} prompt / {total_completion_tokens:,} completion",
            scenario_text=scenario_text,
            option_stats=option_stats,
            undecided_count=int(undecided.get("count", 0) or 0) if isinstance(undecided, dict) else 0,
            undecided_percentage_label=(
                f"{float(undecided.get('percentage', 0.0) or 0.0):.1f}%"
                if isinstance(undecided, dict)
                else "0.0%"
            ),
            responses=responses,
            analysis=analysis_context,
            narrative=narrative_ctx,
            theme="light" if theme == "light" else "dark",
            latency_series=latency_series,
            decision_sequence=decision_sequence,
            chart_option_ids=chart_option_ids,
            donut_data=donut_data,
            donut_svg=donut_svg,
            sparkline_svg=sparkline_svg,
            heatmap_svg=heatmap_svg,
            sections=sections,
            run_pattern=_classify_run_pattern(option_stats, response_count, undecided),
        )
