"""
Presentation plugin interfaces for executive briefs.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from pydantic import BaseModel

from lib.executive_reporting.models import ExecutiveBrief


PluginContextT = TypeVar("PluginContextT", bound=BaseModel)


class ExecutiveBriefPlugin(ABC, Generic[PluginContextT]):
    """Style-specific rendering policy for an executive brief."""

    plugin_id: str
    display_name: str
    template_name: str
    unavailable_message = "Executive brief rendering unavailable"

    @abstractmethod
    def build_context(self, brief: ExecutiveBrief) -> PluginContextT:
        """Build the template context for a brief."""
