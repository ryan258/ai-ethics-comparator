"""
Drop-in executive briefing component.
"""

from __future__ import annotations

from pathlib import Path
from typing import Generic, TypeVar, cast

from pydantic import BaseModel

from lib.executive_reporting.composer import ExecutiveBriefComposer
from lib.executive_reporting.default_composer import EvidencePackageComposer
from lib.executive_reporting.models import EvidencePackage, ExecutiveBrief
from lib.executive_reporting.plugins import (
    ExecutiveBriefPlugin,
    StrategicAnalysisPlugin,
)
from lib.executive_reporting.renderer import ExecutiveBriefRenderer

PluginContextT = TypeVar("PluginContextT", bound=BaseModel)


class ExecutiveBriefingComponent(Generic[PluginContextT]):
    """Compose and render executive briefs from reusable evidence packages."""

    def __init__(
        self,
        *,
        composer: ExecutiveBriefComposer | None = None,
        plugin: ExecutiveBriefPlugin[PluginContextT] | None = None,
        templates_dir: str | Path = "templates",
    ) -> None:
        self.composer = composer or EvidencePackageComposer()
        self.plugin = plugin or cast(ExecutiveBriefPlugin[PluginContextT], StrategicAnalysisPlugin())

        self.renderer = ExecutiveBriefRenderer(self.plugin, templates_dir=templates_dir)

    def build_brief(self, item: EvidencePackage | ExecutiveBrief) -> ExecutiveBrief:
        if isinstance(item, ExecutiveBrief):
            return item
        return self.composer.compose(item)

    def render_context(self, item: EvidencePackage | ExecutiveBrief) -> PluginContextT:
        return self.renderer.render_context(self.build_brief(item))

    def render_html(self, item: EvidencePackage | ExecutiveBrief) -> str:
        return self.renderer.render_html(self.build_brief(item))
