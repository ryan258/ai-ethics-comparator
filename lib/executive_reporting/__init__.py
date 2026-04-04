"""
Reusable executive-report rendering engine.
"""

from typing import TYPE_CHECKING

from lib.executive_reporting.engine import ExecutiveReportEngine, ExecutiveReportProfile
from lib.executive_reporting.composer import ExecutiveBriefComposer
from lib.executive_reporting.component import ExecutiveBriefingComponent
from lib.executive_reporting.default_composer import EvidencePackageComposer
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

if TYPE_CHECKING:
    from lib.executive_reporting.adapters import single_run_report_to_executive_brief

__all__ = [
    "AuditRecord",
    "BriefFinding",
    "BriefMetadataItem",
    "BriefRecommendation",
    "EvidenceMetric",
    "EvidenceObservation",
    "EvidencePackage",
    "EvidencePackageComposer",
    "EvidenceQuote",
    "EvidenceTable",
    "EvidenceTableColumn",
    "EvidenceTableRow",
    "ExecutiveBrief",
    "ExecutiveBriefingComponent",
    "ExecutiveBriefComposer",
    "ExecutiveBriefPlugin",
    "ExecutiveBriefRenderer",
    "ExecutiveReportEngine",
    "ExecutiveReportProfile",
    "StrategicAnalysisPlugin",
    "single_run_report_to_executive_brief",
]


def __getattr__(name: str) -> object:
    if name == "single_run_report_to_executive_brief":
        from lib.executive_reporting.adapters import single_run_report_to_executive_brief

        globals()[name] = single_run_report_to_executive_brief
        return single_run_report_to_executive_brief
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
