"""
Reusable engine for profile-driven executive report generation.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel
from lib.executive_reporting.weasyprint_runtime import load_weasyprint_html

try:
    from jinja2 import Environment, FileSystemLoader
except ModuleNotFoundError:  # pragma: no cover - optional dependency guard
    Environment = None  # type: ignore[assignment]
    FileSystemLoader = None  # type: ignore[assignment]

HTML, WEASYPRINT_IMPORT_ERROR = load_weasyprint_html()
_USE_MODULE_DEFAULT = object()


logger = logging.getLogger(__name__)

SingleReportT = TypeVar("SingleReportT", bound=BaseModel)
ComparisonReportT = TypeVar("ComparisonReportT", bound=BaseModel)


class ExecutiveReportProfile(ABC, Generic[SingleReportT, ComparisonReportT]):
    """Project-specific policy for composing executive-report contexts."""

    single_template_name: str
    comparison_template_name: str
    single_unavailable_message = (
        "PDF generation is unavailable because WeasyPrint could not load its native "
        "dependencies and no native fallback backend is installed."
    )
    comparison_unavailable_message = "Comparison PDF generation unavailable"

    @abstractmethod
    def build_single_report(
        self,
        run_data: dict[str, Any],
        paradox: dict[str, Any],
        insight: Optional[dict[str, Any]] = None,
        narrative: Optional[dict[str, str]] = None,
        *,
        theme: str = "light",
    ) -> SingleReportT:
        """Compose a single-run executive report."""

    @abstractmethod
    def build_comparison_report(
        self,
        runs: list[dict[str, Any]],
        paradox: dict[str, Any],
        insights: list[Optional[dict[str, Any]]],
        narrative: Optional[dict[str, str]] = None,
        *,
        theme: str = "dark",
    ) -> ComparisonReportT:
        """Compose a comparison executive report."""

    def native_single_available(self) -> bool:
        """Return True when the profile can render a single report natively."""
        return False

    def render_native_single(self, report: SingleReportT) -> bytes:
        """Render a single report without HTML/WeasyPrint."""
        raise RuntimeError(self.single_unavailable_message)


class ExecutiveReportEngine(Generic[SingleReportT, ComparisonReportT]):
    """Profile-driven rendering engine for executive reports."""

    def __init__(
        self,
        profile: ExecutiveReportProfile[SingleReportT, ComparisonReportT],
        *,
        templates_dir: str | Path = "templates",
        html_class: object = _USE_MODULE_DEFAULT,
        weasyprint_import_error: object = _USE_MODULE_DEFAULT,
    ) -> None:
        self.profile = profile
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

        self.pdf_available = self.html_class is not None or self.profile.native_single_available()

    def template_available(self, template_name: str) -> bool:
        """Return True when the named template can be loaded."""
        cached = self._template_cache.get(template_name)
        if cached is not None:
            return cached
        if self.env is None:
            self._template_cache[template_name] = False
            return False
        try:
            self.env.get_template(template_name)
        except Exception as exc:
            logger.warning("Executive report template unavailable (%s): %s", template_name, exc)
            self._template_cache[template_name] = False
            return False
        self._template_cache[template_name] = True
        return True

    def render_single_context(self, report: SingleReportT) -> bytes:
        """Render a prebuilt single-run report."""
        if self.html_class is not None and self.template_available(self.profile.single_template_name):
            try:
                return self.generate_weasyprint_pdf(self.profile.single_template_name, report)
            except Exception as exc:
                logger.warning("WeasyPrint PDF render failed, using native fallback: %s", exc)

        if not self.profile.native_single_available():
            raise RuntimeError(self.profile.single_unavailable_message) from self.weasyprint_import_error

        return self.profile.render_native_single(report)

    def render_comparison_context(self, report: ComparisonReportT) -> bytes:
        """Render a prebuilt comparison report."""
        if self.html_class is None or not self.template_available(self.profile.comparison_template_name):
            raise RuntimeError(self.profile.comparison_unavailable_message) from self.weasyprint_import_error

        try:
            return self.generate_weasyprint_pdf(self.profile.comparison_template_name, report)
        except Exception as exc:
            logger.warning("WeasyPrint comparison render failed: %s", exc)
            raise RuntimeError(self.profile.comparison_unavailable_message) from exc

    def generate_weasyprint_pdf(self, template_name: str, report: BaseModel) -> bytes:
        """Render a report model through Jinja2 + WeasyPrint."""
        if self.env is None or self.html_class is None:
            raise RuntimeError("WeasyPrint is unavailable") from self.weasyprint_import_error
        template = self.env.get_template(template_name)
        html_content = template.render(report=report)
        return self.html_class(string=html_content, base_url=str(self.templates_dir.parent)).write_pdf()
