"""
Strategic-analysis presentation plugin.
"""

from __future__ import annotations

import json

from pydantic import Field

from lib.executive_reporting.models import (
    BriefFinding,
    BriefRecommendation,
    BriefingModel,
    EvidenceMetric,
    EvidenceQuote,
    EvidenceTable,
    ExecutiveBrief,
)
from lib.executive_reporting.plugins.base import ExecutiveBriefPlugin


class StrategicFindingSection(BriefingModel):
    title: str
    claim: str
    evidence_points: list[str] = Field(default_factory=list)
    implication: str = ""
    confidence_label: str = ""
    supporting_metrics: list[EvidenceMetric] = Field(default_factory=list)


class StrategicRecommendationRow(BriefingModel):
    action: str
    owner: str = ""
    timeline: str = ""
    expected_impact: str = ""
    key_risk: str = ""


class StrategicExcerptBlock(BriefingModel):
    title: str
    text: str
    attribution: str = ""
    significance: str = ""
    is_structured: bool = False


class StrategicAnalysisContext(BriefingModel):
    brief_id: str = ""
    header_label: str
    organization: str
    publication_label: str
    title: str
    subtitle: str = ""
    date_label: str = ""
    headline: str = ""
    governing_question: str = ""
    governing_insight: str = ""
    executive_summary: list[str] = Field(default_factory=list)
    top_metrics: list[EvidenceMetric] = Field(default_factory=list)
    findings: list[StrategicFindingSection] = Field(default_factory=list)
    decision_implications: list[str] = Field(default_factory=list)
    recommendations: list[StrategicRecommendationRow] = Field(default_factory=list)
    methodology: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    appendix_reference_text: str = ""
    appendix_reference_table: EvidenceTable | None = None
    appendix_excerpts: list[StrategicExcerptBlock] = Field(default_factory=list)


class StrategicAnalysisPlugin(ExecutiveBriefPlugin[StrategicAnalysisContext]):
    """Consulting-style strategic briefing layout for reusable executive briefs."""

    plugin_id = "strategic_analysis"
    display_name = "Strategic Analysis"
    template_name = "reports/strategic_analysis_brief.html"

    def __init__(
        self,
        *,
        organization: str = "Cyborg Labs",
        header_label: str = "Strategic Analysis",
        publication_label: str = "",
    ) -> None:
        self.organization = organization
        self.header_label = header_label
        self.publication_label = publication_label

    def build_context(self, brief: ExecutiveBrief) -> StrategicAnalysisContext:
        executive_summary = [paragraph for paragraph in brief.executive_summary if paragraph.strip()]
        if not executive_summary:
            executive_summary = [brief.governing_insight] if brief.governing_insight else []

        findings = [self._build_finding_section(finding) for finding in brief.key_findings]
        recommendations = [self._build_recommendation_row(item) for item in brief.recommendations]

        return StrategicAnalysisContext(
            brief_id=brief.brief_id,
            header_label=brief.kicker or self.header_label,
            organization=brief.organization or self.organization,
            publication_label=brief.publication_label or self.publication_label,
            title=brief.title,
            subtitle=brief.subtitle,
            date_label=brief.date_label,
            headline=brief.headline or brief.title,
            governing_question=brief.governing_question,
            governing_insight=brief.governing_insight,
            executive_summary=executive_summary,
            top_metrics=[
                EvidenceMetric(
                    label=metric.label,
                    value=metric.value,
                    source=metric.source,
                    note=metric.note,
                )
                for metric in brief.top_metrics
            ],
            findings=findings,
            decision_implications=list(brief.decision_implications),
            recommendations=recommendations,
            methodology=list(brief.methodology),
            limitations=list(brief.limitations),
            sources=list(brief.sources),
            appendix_reference_text=brief.appendix_reference_text,
            appendix_reference_table=brief.appendix_reference_table,
            appendix_excerpts=[self._build_excerpt_block(excerpt) for excerpt in brief.appendix_excerpts],
        )

    def _build_finding_section(self, finding: BriefFinding) -> StrategicFindingSection:
        return StrategicFindingSection(
            title=finding.title,
            claim=finding.claim,
            evidence_points=list(finding.evidence_points),
            implication=finding.implication,
            confidence_label=finding.confidence.capitalize(),
            supporting_metrics=[
                EvidenceMetric(
                    label=metric.label,
                    value=metric.value,
                    source=metric.source,
                    note=metric.note,
                )
                for metric in finding.supporting_metrics
            ],
        )

    def _build_recommendation_row(self, item: BriefRecommendation) -> StrategicRecommendationRow:
        return StrategicRecommendationRow(
            action=item.action,
            owner=item.owner,
            timeline=item.timeline,
            expected_impact=item.expected_impact,
            key_risk=item.key_risk,
        )

    def _build_excerpt_block(self, excerpt: EvidenceQuote) -> StrategicExcerptBlock:
        formatted_text, is_structured = _format_excerpt_text(excerpt.text)
        return StrategicExcerptBlock(
            title=excerpt.title,
            text=formatted_text,
            attribution=excerpt.attribution,
            significance=excerpt.significance,
            is_structured=is_structured,
        )


def _format_excerpt_text(text: str) -> tuple[str, bool]:
    normalized = text.strip()
    if not normalized:
        return "", False

    try:
        parsed = json.loads(normalized)
    except json.JSONDecodeError:
        return normalized, False

    if not isinstance(parsed, dict | list):
        return normalized, False

    return json.dumps(parsed, indent=2, ensure_ascii=False), True
