"""
Executive-brief presentation plugins.
"""

from lib.executive_reporting.plugins.base import ExecutiveBriefPlugin
from lib.executive_reporting.plugins.strategic_analysis import (
    StrategicAnalysisContext,
    StrategicAnalysisPlugin,
)

__all__ = [
    "ExecutiveBriefPlugin",
    "StrategicAnalysisContext",
    "StrategicAnalysisPlugin",
]
