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
from lib.executive_reporting.plugins import ExecutiveBriefPlugin, StrategicAnalysisPlugin
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
        html_class: object | None = None,
        weasyprint_import_error: object | None = None,
    ) -> None:
        self.composer = composer or EvidencePackageComposer()
        self.plugin = plugin or cast(ExecutiveBriefPlugin[PluginContextT], StrategicAnalysisPlugin())

        renderer_kwargs: dict[str, object] = {"templates_dir": templates_dir}
        if html_class is not None:
            renderer_kwargs["html_class"] = html_class
        if weasyprint_import_error is not None:
            renderer_kwargs["weasyprint_import_error"] = weasyprint_import_error

        self.renderer = ExecutiveBriefRenderer(
            self.plugin,
            **renderer_kwargs,
        )

    def build_brief(self, item: EvidencePackage | ExecutiveBrief) -> ExecutiveBrief:
        if isinstance(item, ExecutiveBrief):
            return item
        return self.composer.compose(item)

    def render_context(self, item: EvidencePackage | ExecutiveBrief) -> PluginContextT:
        return self.renderer.render_context(self.build_brief(item))

    def render_html(self, item: EvidencePackage | ExecutiveBrief) -> str:
        return self.renderer.render_html(self.build_brief(item))

    def render_pdf(self, item: EvidencePackage | ExecutiveBrief) -> bytes:
        return self.renderer.render_pdf(self.build_brief(item))
