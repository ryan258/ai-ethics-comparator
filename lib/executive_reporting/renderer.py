"""
Renderer for plugin-driven executive briefs.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Generic, TypeVar

from pydantic import BaseModel

from lib.executive_reporting.models import ExecutiveBrief
from lib.executive_reporting.plugins.base import ExecutiveBriefPlugin

try:
    from jinja2 import Environment, FileSystemLoader
except ModuleNotFoundError:  # pragma: no cover - optional dependency guard
    Environment = None  # type: ignore[assignment]
    FileSystemLoader = None  # type: ignore[assignment]



logger = logging.getLogger(__name__)

PluginContextT = TypeVar("PluginContextT", bound=BaseModel)


class ExecutiveBriefRenderer(Generic[PluginContextT]):
    """Render an executive brief through a reusable presentation plugin."""

    def __init__(
        self,
        plugin: ExecutiveBriefPlugin[PluginContextT],
        *,
        templates_dir: str | Path = "templates",
    ) -> None:
        self.plugin = plugin
        self.templates_dir = Path(templates_dir)
        self.env: Environment | None = None
        self._template_cache: dict[str, bool] = {}

        if Environment is not None and FileSystemLoader is not None and self.templates_dir.exists():
            # autoescape: report templates interpolate model-authored text.
            self.env = Environment(
                loader=FileSystemLoader(str(self.templates_dir)),
                autoescape=True,
            )

    def template_available(self) -> bool:
        cached = self._template_cache.get(self.plugin.template_name)
        if cached is not None:
            return cached
        if self.env is None:
            self._template_cache[self.plugin.template_name] = False
            return False
        try:
            self.env.get_template(self.plugin.template_name)
        except Exception as exc:
            logger.warning(
                "Executive brief template unavailable (%s): %s",
                self.plugin.template_name,
                exc,
            )
            self._template_cache[self.plugin.template_name] = False
            return False
        self._template_cache[self.plugin.template_name] = True
        return True

    def render_context(self, brief: ExecutiveBrief) -> PluginContextT:
        return self.plugin.build_context(brief)

    def render_html(self, brief: ExecutiveBrief) -> str:
        if self.env is None or not self.template_available():
            raise RuntimeError(self.plugin.unavailable_message)
        template = self.env.get_template(self.plugin.template_name)
        return template.render(report=self.render_context(brief))
