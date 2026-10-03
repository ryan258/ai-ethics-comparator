"""
Executive-brief presentation plugins.
"""

from presentation.executive_reporting.plugins.base import ExecutiveBriefPlugin
from presentation.executive_reporting.plugins.strategic_analysis import (
    StrategicAnalysisContext,
    StrategicAnalysisPlugin,
)

__all__ = [
    "ExecutiveBriefPlugin",
    "StrategicAnalysisContext",
    "StrategicAnalysisPlugin",
]
