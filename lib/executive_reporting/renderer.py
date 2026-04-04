"""
Renderer for plugin-driven executive briefs.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Generic, Optional, TypeVar

from pydantic import BaseModel

from lib.executive_reporting.models import ExecutiveBrief
from lib.executive_reporting.plugins.base import ExecutiveBriefPlugin
from lib.executive_reporting.weasyprint_runtime import load_weasyprint_html

try:
    from jinja2 import Environment, FileSystemLoader
except ModuleNotFoundError:  # pragma: no cover - optional dependency guard
    Environment = None  # type: ignore[assignment]
    FileSystemLoader = None  # type: ignore[assignment]

HTML, WEASYPRINT_IMPORT_ERROR = load_weasyprint_html()
_USE_MODULE_DEFAULT = object()


logger = logging.getLogger(__name__)

PluginContextT = TypeVar("PluginContextT", bound=BaseModel)


class ExecutiveBriefRenderer(Generic[PluginContextT]):
    """Render an executive brief through a reusable presentation plugin."""

    def __init__(
        self,
        plugin: ExecutiveBriefPlugin[PluginContextT],
        *,
        templates_dir: str | Path = "templates",
        html_class: object = _USE_MODULE_DEFAULT,
        weasyprint_import_error: object = _USE_MODULE_DEFAULT,
    ) -> None:
        self.plugin = plugin
        self.templates_dir = Path(templates_dir)
        self.env: Optional[Environment] = None
        self._template_cache: dict[str, bool] = {}
        self.html_class = HTML if html_class is _USE_MODULE_DEFAULT else html_class
        self.weasyprint_import_error = (
            WEASYPRINT_IMPORT_ERROR
            if weasyprint_import_error is _USE_MODULE_DEFAULT
            else weasyprint_import_error
        )

        if Environment is not None and FileSystemLoader is not None and self.templates_dir.exists():
            self.env = Environment(loader=FileSystemLoader(str(self.templates_dir)))

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

    def render_pdf(self, brief: ExecutiveBrief) -> bytes:
        if self.html_class is None:
            raise RuntimeError(self.plugin.unavailable_message) from self.weasyprint_import_error
        html_content = self.render_html(brief)
        return self.html_class(string=html_content, base_url=str(self.templates_dir.parent)).write_pdf()
