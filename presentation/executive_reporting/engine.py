"""
Reusable engine for profile-driven executive report generation.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

try:
    from jinja2 import Environment, FileSystemLoader
except ModuleNotFoundError:  # pragma: no cover - optional dependency guard
    Environment = None  # type: ignore[assignment]
    FileSystemLoader = None  # type: ignore[assignment]



logger = logging.getLogger(__name__)

SingleReportT = TypeVar("SingleReportT", bound=BaseModel)
ComparisonReportT = TypeVar("ComparisonReportT", bound=BaseModel)


class ExecutiveReportProfile(ABC, Generic[SingleReportT, ComparisonReportT]):
    """Project-specific policy for composing executive-report contexts."""

    single_template_name: str
    comparison_template_name: str
    single_unavailable_message = "Single-run report template unavailable"
    comparison_unavailable_message = "Comparison report template unavailable"

    @abstractmethod
    def build_single_report(
        self,
        run_data: dict[str, Any],
        paradox: dict[str, Any],
        insight: dict[str, Any] | None = None,
        narrative: dict[str, str] | None = None,
        *,
        theme: str = "light",
    ) -> SingleReportT:
        """Compose a single-run executive report."""

    @abstractmethod
    def build_comparison_report(
        self,
        runs: list[dict[str, Any]],
        paradox: dict[str, Any],
        insights: list[dict[str, Any] | None],
        narrative: dict[str, str] | None = None,
        *,
        theme: str = "dark",
    ) -> ComparisonReportT:
        """Compose a comparison executive report."""


class ExecutiveReportEngine(Generic[SingleReportT, ComparisonReportT]):
    """Profile-driven rendering engine for executive reports."""

    def __init__(
        self,
        profile: ExecutiveReportProfile[SingleReportT, ComparisonReportT],
        *,
        templates_dir: str | Path = "templates",
    ) -> None:
        self.profile = profile
        self.templates_dir = Path(templates_dir)
        self.env: Environment | None = None
        self._template_cache: dict[str, bool] = {}

        if Environment is not None and FileSystemLoader is not None and self.templates_dir.exists():
            # autoescape: report templates interpolate model-authored text.
            self.env = Environment(
                loader=FileSystemLoader(str(self.templates_dir)),
                autoescape=True,
            )


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

    def render_single_context(self, report: SingleReportT) -> str:
        return self.render_html(self.profile.single_template_name, report)

    def render_comparison_context(self, report: ComparisonReportT) -> str:
        return self.render_html(self.profile.comparison_template_name, report)

    def render_html(self, template_name: str, report: BaseModel) -> str:
        """Render a self-contained browser document with automatic escaping."""
        if self.env is None or not self.template_available(template_name):
            raise RuntimeError("Report template unavailable")
        return self.env.get_template(template_name).render(report=report)
