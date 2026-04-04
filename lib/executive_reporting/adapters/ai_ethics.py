"""
AI-ethics report adapters for the executive-briefing layer.
"""

from __future__ import annotations

from collections.abc import Iterable

from lib.executive_reporting.models import (
    AuditRecord,
    BriefFinding,
    BriefRecommendation,
    EvidenceMetric,
    EvidenceQuote,
    ExecutiveBrief,
)
from lib.report_models import ReportResponse, SingleRunReport, SummaryMetric


def single_run_report_to_executive_brief(report: SingleRunReport) -> ExecutiveBrief:
    """Adapt the existing single-run AI-ethics report into a generic executive brief."""
    executive_summary = _collect_summary_paragraphs(report)
    top_metrics = [_summary_metric_to_evidence_metric(metric) for metric in report.executive_metrics[:3]]

    limitations = list(report.limitation_points)
    if report.reliability_note and report.reliability_note not in limitations:
        limitations.insert(0, report.reliability_note)

    return ExecutiveBrief(
        brief_id=report.run_id,
        title=_brief_title(report),
        subtitle=report.report_subtitle,
        kicker="Strategic Analysis",
        organization="AI Ethics Comparator",
        publication_label=report.run_id,
        date_label=report.generated_at_label,
        headline=_brief_title(report),
        governing_question=f"How did the model respond to {report.paradox_title}?",
        governing_insight=_governing_insight(report),
        executive_summary=executive_summary,
        top_metrics=top_metrics,
        key_findings=_build_findings(report, top_metrics),
        decision_implications=_collect_implications(report),
        recommendations=_build_recommendations(report),
        methodology=list(report.method_points),
        limitations=limitations,
        sources=_build_provenance(report),
        appendix_audit_records=_build_audit_records(report),
        appendix_excerpts=_build_appendix_excerpts(report),
    )


def _collect_summary_paragraphs(report: SingleRunReport) -> list[str]:
    paragraphs = [
        _normalize_brief_sentence(report.executive_summary),
        _normalize_brief_sentence(report.analysis_snapshot),
        _normalize_brief_sentence(report.implication_box),
    ]
    normalized: list[str] = []
    for paragraph in paragraphs:
        text = paragraph.strip()
        if not text or text.startswith("Analyst synthesis is pending"):
            continue
        if any(text in existing or existing in text for existing in normalized):
            continue
        if text not in normalized:
            normalized.append(text)
    return normalized


def _summary_metric_to_evidence_metric(metric: SummaryMetric) -> EvidenceMetric:
    return EvidenceMetric(
        label=metric.label,
        value=metric.value,
        source=metric.support,
    )


def _build_findings(report: SingleRunReport, top_metrics: list[EvidenceMetric]) -> list[BriefFinding]:
    findings: list[BriefFinding] = [
        BriefFinding(
            title=report.evidence_title,
            claim=report.thesis_statement,
            evidence_points=_limit_items(report.observation_points, 4),
            implication=report.implication_box,
            confidence=_confidence_label(report),
            supporting_metrics=top_metrics[:2],
        )
    ]

    interpretation_points = _limit_items(
        report.interpretation_points or report.key_takeaways or [report.analysis_snapshot],
        4,
    )
    findings.append(
        BriefFinding(
            title=report.rationale_chart_title,
            claim=_rationale_claim(report),
            evidence_points=interpretation_points,
            implication=_second_implication(report),
            confidence=_confidence_label(report),
            supporting_metrics=[_summary_metric_to_evidence_metric(report.executive_metrics[-1])]
            if report.executive_metrics
            else [],
        )
    )

    deployment_evidence = _limit_items(report.risky_contexts + report.required_controls, 5)
    findings.append(
        BriefFinding(
            title=report.implications_title,
            claim=report.caveat_box or report.implication_box,
            evidence_points=deployment_evidence,
            implication=_last_or_default(report.readout_points, report.caveat_box),
            confidence="directional",
        )
    )

    return [finding for finding in findings if finding.claim.strip()]


def _collect_implications(report: SingleRunReport) -> list[str]:
    combined = [
        *report.readout_points,
        *report.acceptable_contexts,
        *report.risky_contexts,
    ]
    return _limit_items(combined, 6)


def _build_recommendations(report: SingleRunReport) -> list[BriefRecommendation]:
    recommendations: list[BriefRecommendation] = []
    for index, control in enumerate(report.required_controls[:5], start=1):
        recommendations.append(
            BriefRecommendation(
                action=control,
                owner="Human governance",
                timeline="Before deployment",
                expected_impact="Keeps the model in governed decision-support workflows.",
                key_risk=report.caveat_box if index == 1 else "",
            )
        )
    return recommendations


def _build_provenance(report: SingleRunReport) -> list[str]:
    provenance = [
        f"Run ID: {report.run_id}",
        f"Model: {report.model_name}",
        f"Prompt hash: {report.prompt_hash_short}",
    ]
    if report.analyst_model and report.analyst_model != "Not generated":
        provenance.append(f"Analyst model: {report.analyst_model}")
    return provenance


def _build_audit_records(report: SingleRunReport) -> list[AuditRecord]:
    records: list[AuditRecord] = []
    for response in report.responses:
        if response.output_quality_flag == "clean" and response.notable_anomaly == "None":
            continue
        summary_parts = [response.option_label]
        if response.notable_anomaly != "None":
            summary_parts.append(response.notable_anomaly)
        records.append(
            AuditRecord(
                title=f"Iteration {response.iteration}: {response.output_quality_flag}",
                summary=" ".join(part.strip() for part in summary_parts if part.strip()),
                severity=_severity_for_response(response),
                details=response.display_text,
            )
        )
    severity_rank = {"critical": 0, "warning": 1, "info": 2}
    return sorted(records, key=lambda record: (severity_rank[record.severity], record.title))[:4]


def _build_appendix_excerpts(report: SingleRunReport) -> list[EvidenceQuote]:
    excerpts: list[EvidenceQuote] = []
    for response in report.raw_appendix_responses[:2]:
        if not response.raw_text.strip():
            continue
        excerpts.append(
            EvidenceQuote(
                title=f"Iteration {response.iteration}: {response.option_label}",
                text=response.raw_text,
                attribution=response.output_quality_flag,
            )
        )
    return excerpts


def _severity_for_response(response: ReportResponse) -> str:
    if "truncation" in response.output_quality_flag or "meta-reasoning" in response.output_quality_flag:
        return "critical"
    if response.output_quality_flag != "clean":
        return "warning"
    return "info"


def _confidence_label(report: SingleRunReport) -> str:
    if report.reliability_note:
        return "directional"
    if report.lead_choice_label.lower().startswith("no dominant"):
        return "low"
    return "medium"


def _second_implication(report: SingleRunReport) -> str:
    if len(report.readout_points) > 1 and report.readout_points[1].strip():
        return report.readout_points[1]
    return _last_or_default(report.readout_points, report.implication_box)


def _last_or_default(items: list[str], default: str) -> str:
    for item in reversed(items):
        if item.strip():
            return item
    return default


def _limit_items(items: list[str], limit: int) -> list[str]:
    normalized: list[str] = []
    for item in items:
        text = item.strip()
        if text and text not in normalized:
            normalized.append(text)
        if len(normalized) >= limit:
            break
    return normalized


def _brief_title(report: SingleRunReport) -> str:
    leader_labels = _leader_labels(report)
    if len(leader_labels) > 1:
        return (
            f"The run split between {_format_series(leader_labels)}, so deployment should stay under human review"
        )
    if len(leader_labels) == 1:
        return report.report_title
    return report.paradox_title


def _governing_insight(report: SingleRunReport) -> str:
    leader_labels = _leader_labels(report)
    if len(leader_labels) > 1:
        shared_support = next(
            (
                stat.percentage_label
                for stat in report.option_stats
                if stat.is_leader and stat.percentage_label.strip()
            ),
            report.lead_choice_support,
        )
        return (
            f"The run produced a tie between {_format_series(leader_labels)} at {shared_support} each, "
            "so the result is directional and should be used only with human review."
        )
    if len(leader_labels) == 1:
        return _normalize_brief_sentence(report.thesis_statement)
    return ""


def _leader_labels(report: SingleRunReport) -> list[str]:
    labels = [stat.label.strip() for stat in report.option_stats if stat.is_leader and stat.label.strip()]
    if labels:
        return labels
    lead_choice = report.lead_choice_label.strip()
    if lead_choice and not lead_choice.lower().startswith("no dominant"):
        return [lead_choice]
    return []


def _format_series(values: Iterable[str]) -> str:
    cleaned = [value.strip() for value in values if value.strip()]
    if not cleaned:
        return ""
    if len(cleaned) == 1:
        return cleaned[0]
    if len(cleaned) == 2:
        return f"{cleaned[0]} and {cleaned[1]}"
    return f"{', '.join(cleaned[:-1])}, and {cleaned[-1]}"


def _normalize_brief_sentence(text: str) -> str:
    normalized = text.strip()
    if not normalized:
        return ""
    replacements = (
        (
            "each receiving a clear majority of support",
            "each receiving a co-leading share of selections",
        ),
        (
            "receiving a clear majority of support",
            "receiving the leading share of selections",
        ),
        (
            "The vote revealed a stable tendency with recurring dissent",
            "The vote indicates a recurring split",
        ),
    )
    for source, target in replacements:
        normalized = normalized.replace(source, target)
    return normalized


def _rationale_claim(report: SingleRunReport) -> str:
    candidates = [
        report.analysis_snapshot,
        report.narrative.framework_diagnosis if report.narrative else "",
        *report.interpretation_points,
        *report.key_takeaways,
    ]
    for candidate in candidates:
        text = _normalize_brief_sentence(candidate)
        if text and not text.startswith("Analyst synthesis is pending"):
            return text
    return ""
