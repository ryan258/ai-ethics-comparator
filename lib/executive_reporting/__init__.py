"""
Reusable executive-report rendering engine.
"""

from lib.executive_reporting.engine import ExecutiveReportEngine, ExecutiveReportProfile
from lib.executive_reporting.adapters import single_run_report_to_executive_brief
from lib.executive_reporting.composer import ExecutiveBriefComposer
from lib.executive_reporting.models import (
    AuditRecord,
    BriefFinding,
    BriefMetadataItem,
    BriefRecommendation,
    EvidenceMetric,
    EvidenceObservation,
    EvidencePackage,
    EvidenceQuote,
    EvidenceTable,
    EvidenceTableColumn,
    EvidenceTableRow,
    ExecutiveBrief,
)
from lib.executive_reporting.plugins import ExecutiveBriefPlugin, StrategicAnalysisPlugin
from lib.executive_reporting.renderer import ExecutiveBriefRenderer

__all__ = [
    "AuditRecord",
    "BriefFinding",
    "BriefMetadataItem",
    "BriefRecommendation",
    "EvidenceMetric",
    "EvidenceObservation",
    "EvidencePackage",
    "EvidenceQuote",
    "EvidenceTable",
    "EvidenceTableColumn",
    "EvidenceTableRow",
    "ExecutiveBrief",
    "ExecutiveBriefComposer",
    "ExecutiveBriefPlugin",
    "ExecutiveBriefRenderer",
    "ExecutiveReportEngine",
    "ExecutiveReportProfile",
    "StrategicAnalysisPlugin",
    "single_run_report_to_executive_brief",
]
