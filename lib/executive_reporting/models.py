"""
Generic executive-brief data contracts.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


ConfidenceLabel = Literal["high", "medium", "low", "directional"]
ColumnAlignment = Literal["left", "center", "right"]
AuditSeverity = Literal["info", "warning", "critical"]


class BriefingModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BriefMetadataItem(BriefingModel):
    label: str
    value: str


class EvidenceMetric(BriefingModel):
    label: str
    value: str
    source: str = ""
    note: str = ""


class EvidenceObservation(BriefingModel):
    title: str
    summary: str
    evidence_points: list[str] = Field(default_factory=list)
    significance: str = ""
    confidence: ConfidenceLabel = "directional"
    source_refs: list[str] = Field(default_factory=list)


class EvidenceQuote(BriefingModel):
    title: str
    text: str
    attribution: str = ""
    significance: str = ""


class EvidenceTableColumn(BriefingModel):
    key: str
    label: str
    align: ColumnAlignment = "left"


class EvidenceTableRow(BriefingModel):
    cells: dict[str, str] = Field(default_factory=dict)


class EvidenceTable(BriefingModel):
    title: str
    intro: str = ""
    columns: list[EvidenceTableColumn] = Field(default_factory=list)
    rows: list[EvidenceTableRow] = Field(default_factory=list)
    source: str = ""


class AuditRecord(BriefingModel):
    title: str
    summary: str
    severity: AuditSeverity = "info"
    details: str = ""


class EvidencePackage(BriefingModel):
    package_id: str = ""
    subject: str
    governing_question: str = ""
    governing_insight: str = ""
    summary_metrics: list[EvidenceMetric] = Field(default_factory=list)
    observations: list[EvidenceObservation] = Field(default_factory=list)
    evidence_tables: list[EvidenceTable] = Field(default_factory=list)
    excerpts: list[EvidenceQuote] = Field(default_factory=list)
    methodology: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    audit_records: list[AuditRecord] = Field(default_factory=list)
    metadata: list[BriefMetadataItem] = Field(default_factory=list)


class BriefFinding(BriefingModel):
    title: str
    claim: str
    evidence_points: list[str] = Field(default_factory=list)
    implication: str = ""
    confidence: ConfidenceLabel = "directional"
    supporting_metrics: list[EvidenceMetric] = Field(default_factory=list)
    evidence_table: EvidenceTable | None = None
    quotations: list[EvidenceQuote] = Field(default_factory=list)


class BriefRecommendation(BriefingModel):
    action: str
    owner: str = ""
    timeline: str = ""
    expected_impact: str = ""
    key_risk: str = ""


class ExecutiveBrief(BriefingModel):
    brief_id: str = ""
    title: str
    subtitle: str = ""
    kicker: str = "Strategic Analysis"
    organization: str = ""
    publication_label: str = ""
    date_label: str = ""
    headline: str = ""
    governing_question: str = ""
    governing_insight: str = ""
    executive_summary: list[str] = Field(default_factory=list)
    top_metrics: list[EvidenceMetric] = Field(default_factory=list)
    key_findings: list[BriefFinding] = Field(default_factory=list)
    decision_implications: list[str] = Field(default_factory=list)
    recommendations: list[BriefRecommendation] = Field(default_factory=list)
    methodology: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    appendix_reference_text: str = ""
    appendix_reference_table: EvidenceTable | None = None
    appendix_audit_records: list[AuditRecord] = Field(default_factory=list)
    appendix_excerpts: list[EvidenceQuote] = Field(default_factory=list)
    metadata: list[BriefMetadataItem] = Field(default_factory=list)
