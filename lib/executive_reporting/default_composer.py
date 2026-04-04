"""
Default composer for turning a generic EvidencePackage into an ExecutiveBrief.
"""

from __future__ import annotations

from typing import Iterable

from lib.executive_reporting.composer import ExecutiveBriefComposer
from lib.executive_reporting.models import (
    BriefFinding,
    BriefMetadataItem,
    EvidenceMetric,
    EvidenceObservation,
    EvidencePackage,
    EvidenceQuote,
    EvidenceTable,
    EvidenceTableRow,
    ExecutiveBrief,
)


class EvidencePackageComposer(ExecutiveBriefComposer):
    """Default drop-in composer for generic evidence packages."""

    def __init__(
        self,
        *,
        organization: str = "",
        publication_label: str = "",
        header_label: str = "Strategic Analysis",
        max_top_metrics: int = 3,
        max_findings: int = 3,
        max_implications: int = 5,
    ) -> None:
        self.organization = organization
        self.publication_label = publication_label
        self.header_label = header_label
        self.max_top_metrics = max(1, max_top_metrics)
        self.max_findings = max(1, max_findings)
        self.max_implications = max(1, max_implications)

    def compose(self, evidence: EvidencePackage) -> ExecutiveBrief:
        top_metrics = list(evidence.summary_metrics[: self.max_top_metrics])
        governing_insight = evidence.governing_insight.strip() or _first_non_empty(
            observation.summary for observation in evidence.observations
        )
        key_findings = _build_findings(evidence, top_metrics, self.max_findings)
        headline = _metadata_value(evidence.metadata, "headline") or governing_insight or evidence.subject

        executive_summary = _build_executive_summary(evidence, governing_insight)
        if not executive_summary and governing_insight:
            executive_summary = [governing_insight]

        return ExecutiveBrief(
            brief_id=evidence.package_id,
            title=evidence.subject,
            subtitle=_metadata_value(evidence.metadata, "subtitle"),
            kicker=self.header_label,
            organization=self.organization or _metadata_value(evidence.metadata, "organization"),
            publication_label=self.publication_label or _metadata_value(evidence.metadata, "publication"),
            date_label=_metadata_value(evidence.metadata, "date"),
            headline=headline,
            governing_question=evidence.governing_question,
            governing_insight=governing_insight,
            executive_summary=executive_summary,
            top_metrics=top_metrics,
            key_findings=key_findings,
            decision_implications=_build_decision_implications(evidence, self.max_implications),
            recommendations=[],
            methodology=list(evidence.methodology),
            limitations=list(evidence.limitations),
            sources=list(evidence.sources),
            appendix_reference_text="",
            appendix_reference_table=None,
            appendix_audit_records=list(evidence.audit_records),
            appendix_excerpts=list(evidence.excerpts),
            metadata=list(evidence.metadata),
        )


def _build_executive_summary(evidence: EvidencePackage, governing_insight: str) -> list[str]:
    paragraphs: list[str] = []
    for candidate in (
        governing_insight,
        *[observation.summary for observation in evidence.observations[:2]],
        *[observation.significance for observation in evidence.observations[:1]],
    ):
        text = candidate.strip()
        if text and text not in paragraphs:
            paragraphs.append(text)
    return paragraphs[:3]


def _build_findings(
    evidence: EvidencePackage,
    top_metrics: list[EvidenceMetric],
    limit: int,
) -> list[BriefFinding]:
    findings: list[BriefFinding] = []

    for index, observation in enumerate(evidence.observations[:limit]):
        findings.append(_observation_to_finding(observation, top_metrics[index : index + 1], evidence.excerpts))

    if len(findings) < limit:
        for table in evidence.evidence_tables:
            findings.append(_table_to_finding(table, top_metrics[len(findings) : len(findings) + 1]))
            if len(findings) >= limit:
                break

    if not findings and top_metrics:
        metric = top_metrics[0]
        findings.append(
            BriefFinding(
                title=metric.label,
                claim=f"{metric.label} is the clearest quantitative signal in the evidence package.",
                evidence_points=[metric.source] if metric.source else [],
                implication=metric.note,
                confidence="directional",
                supporting_metrics=[metric],
            )
        )

    return findings[:limit]


def _observation_to_finding(
    observation: EvidenceObservation,
    supporting_metrics: list[EvidenceMetric],
    excerpts: list[EvidenceQuote],
) -> BriefFinding:
    quotations = [quote for quote in excerpts if quote.title.strip() == observation.title.strip()][:2]
    return BriefFinding(
        title=observation.title,
        claim=observation.summary,
        evidence_points=list(observation.evidence_points),
        implication=observation.significance,
        confidence=observation.confidence,
        supporting_metrics=supporting_metrics,
        quotations=quotations,
    )


def _table_to_finding(table: EvidenceTable, supporting_metrics: list[EvidenceMetric]) -> BriefFinding:
    evidence_points = [_format_table_row(table, row) for row in table.rows[:3]]
    claim = table.intro.strip() or f"{table.title} summarizes the underlying evidence."
    implication = table.source.strip()
    return BriefFinding(
        title=table.title,
        claim=claim,
        evidence_points=evidence_points,
        implication=implication,
        confidence="directional",
        supporting_metrics=supporting_metrics,
        evidence_table=table,
    )


def _format_table_row(table: EvidenceTable, row: EvidenceTableRow) -> str:
    cells = row.cells
    parts: list[str] = []
    for column in table.columns:
        value = str(cells.get(column.key, "")).strip()
        if value:
            parts.append(f"{column.label}: {value}")
    return "; ".join(parts)


def _build_decision_implications(evidence: EvidencePackage, limit: int) -> list[str]:
    candidates = [
        observation.significance
        for observation in evidence.observations
        if observation.significance.strip()
    ]
    candidates.extend(
        excerpt.significance
        for excerpt in evidence.excerpts
        if excerpt.significance.strip()
    )

    implications: list[str] = []
    for candidate in candidates:
        text = candidate.strip()
        if text and text not in implications:
            implications.append(text)
        if len(implications) >= limit:
            break
    return implications


def _metadata_value(metadata: list[BriefMetadataItem], label: str) -> str:
    normalized = label.strip().lower()
    for item in metadata:
        if item.label.strip().lower() == normalized and item.value.strip():
            return item.value.strip()
    return ""


def _first_non_empty(values: Iterable[str]) -> str:
    for value in values:
        text = value.strip()
        if text:
            return text
    return ""
