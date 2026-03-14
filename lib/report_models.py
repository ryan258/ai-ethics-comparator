"""
Typed report context models.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


ThemeName = Literal["dark", "light"]
RunPattern = Literal["unanimous", "dominant", "contested", "split", "ambiguous"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SectionLink(StrictModel):
    id: str
    title: str


class SummaryMetric(StrictModel):
    label: str
    value: str
    support: str = ""


class MetadataItem(StrictModel):
    label: str
    value: str
    mono: bool = False


class DonutSlice(StrictModel):
    label: str
    value: int = 0
    color: str


class ReportOptionStat(StrictModel):
    id: Optional[int]
    token: str
    label: str
    description: str = ""
    count: int = 0
    percentage: float = 0.0
    percentage_label: str = "0.0%"
    is_leader: bool = False


class ReportResponse(StrictModel):
    iteration: int
    decision_token: Optional[str] = None
    option_id: Optional[int] = None
    option_label: str = "Undecided"
    latency_label: str = ""
    token_usage_label: str = ""
    display_text: str
    raw_text: str = ""
    response_length: int = 0
    response_length_label: str = ""
    rationale_theme: str = "Other / uncoded"
    output_quality_flag: str = "clean"
    notable_anomaly: str = ""
    used_raw_fallback: bool = False


class RationaleCluster(StrictModel):
    label: str
    count: int = 0
    share_label: str = "0%"
    description: str = ""


class MoralComplex(StrictModel):
    label: str
    count: int = 0
    justification: str = ""


class ReasoningQuality(StrictModel):
    noticed: list[str] = Field(default_factory=list)
    missed: list[str] = Field(default_factory=list)


class AnalysisContext(StrictModel):
    legacy_text: str = ""
    dominant_framework: str = ""
    key_insights: list[str] = Field(default_factory=list)
    justifications: list[str] = Field(default_factory=list)
    consistency: list[str] = Field(default_factory=list)
    moral_complexes: list[MoralComplex] = Field(default_factory=list)
    reasoning_quality: ReasoningQuality = Field(default_factory=ReasoningQuality)


class NarrativeContext(StrictModel):
    executive_narrative: str = ""
    response_arc: str = ""
    implications: str = ""
    scenario_commentary: str = ""
    cross_iteration_patterns: str = ""
    framework_diagnosis: str = ""


class SingleRunReport(StrictModel):
    report_type: Literal["single"] = "single"
    run_id: str
    model_name: str
    paradox_title: str
    category: str
    generated_at_label: str
    prompt_hash_short: str
    analyst_model: str
    executive_summary: str
    analysis_snapshot: str
    report_title: str
    report_subtitle: str
    thesis_statement: str
    evidence_title: str
    implications_title: str
    method_title: str
    appendix_title: str
    raw_appendix_title: str
    explanation_appendix_title: str
    primary_chart_title: str
    sequence_chart_title: str
    rationale_chart_title: str
    implication_box: str
    caveat_box: str
    scenario_excerpt: str
    case_summary_points: list[str] = Field(default_factory=list)
    scope_points: list[str] = Field(default_factory=list)
    readout_points: list[str] = Field(default_factory=list)
    key_takeaways: list[str] = Field(default_factory=list)
    observation_points: list[str] = Field(default_factory=list)
    interpretation_points: list[str] = Field(default_factory=list)
    acceptable_contexts: list[str] = Field(default_factory=list)
    risky_contexts: list[str] = Field(default_factory=list)
    required_controls: list[str] = Field(default_factory=list)
    method_points: list[str] = Field(default_factory=list)
    limitation_points: list[str] = Field(default_factory=list)
    appendix_summary_note: str = ""
    raw_appendix_note: str = ""
    explanation_appendix_note: str = ""
    reliability_note: str = ""
    structure_shift_note: str = ""
    response_count: int = 0
    response_count_support: str
    lead_choice_label: str
    lead_choice_support: str
    lead_choice_token: str
    mean_latency_label: str
    latency_support: str
    token_volume_label: str
    token_support: str
    scenario_text: str
    option_stats: list[ReportOptionStat] = Field(default_factory=list)
    rationale_clusters: list[RationaleCluster] = Field(default_factory=list)
    undecided_count: int = 0
    undecided_percentage_label: str = "0.0%"
    responses: list[ReportResponse] = Field(default_factory=list)
    raw_appendix_responses: list[ReportResponse] = Field(default_factory=list)
    analysis: Optional[AnalysisContext] = None
    narrative: Optional[NarrativeContext] = None
    theme: ThemeName = "light"
    executive_metrics: list[SummaryMetric] = Field(default_factory=list)
    method_metadata_items: list[MetadataItem] = Field(default_factory=list)
    metadata_items: list[MetadataItem] = Field(default_factory=list)
    latency_series: list[float] = Field(default_factory=list)
    decision_sequence: list[Optional[int]] = Field(default_factory=list)
    chart_option_ids: list[int] = Field(default_factory=list)
    donut_data: list[DonutSlice] = Field(default_factory=list)
    donut_svg: str = ""
    sparkline_svg: str = ""
    heatmap_svg: str = ""
    sections: list[SectionLink] = Field(default_factory=list)
    run_pattern: RunPattern = "ambiguous"


class ComparisonOptionStat(StrictModel):
    id: Optional[int]
    label: str
    count: int = 0
    percentage: float = 0.0
    percentage_label: str = "0.0%"
    is_leader: bool = False
    color: str
    ci_lower: float = 0.0
    ci_upper: float = 0.0


class ComparisonModelSummary(StrictModel):
    model_name: str
    run_id: str
    response_count: int = 0
    option_stats: list[ComparisonOptionStat] = Field(default_factory=list)
    observed: list[int] = Field(default_factory=list)
    donut_svg: str = ""
    donut_data: list[DonutSlice] = Field(default_factory=list)


class ChiSquareResult(StrictModel):
    chiSquare: float
    pValue: float
    degreesOfFreedom: int
    significant: bool
    warning: Optional[str] = None


class OptionEffect(StrictModel):
    label: str
    p1: float
    p2: float
    h: float
    interpretation: str


class PairwiseComparison(StrictModel):
    model_a: str
    model_b: str
    chi_square: Optional[ChiSquareResult] = None
    option_effects: list[OptionEffect] = Field(default_factory=list)


class DeltaValue(StrictModel):
    model: str
    count: int = 0
    percentage: float = 0.0


class DeltaRow(StrictModel):
    option_id: Optional[int]
    label: str
    values: list[DeltaValue] = Field(default_factory=list)


class DeltaTable(StrictModel):
    model_names: list[str] = Field(default_factory=list)
    rows: list[DeltaRow] = Field(default_factory=list)


class ComparisonReport(StrictModel):
    report_type: Literal["comparison"] = "comparison"
    theme: ThemeName = "dark"
    paradox_title: str
    category: str
    model_count: int
    models: list[ComparisonModelSummary] = Field(default_factory=list)
    comparisons: list[PairwiseComparison] = Field(default_factory=list)
    delta_table: DeltaTable
    narrative: Optional[NarrativeContext] = None
    sections: list[SectionLink] = Field(default_factory=list)
