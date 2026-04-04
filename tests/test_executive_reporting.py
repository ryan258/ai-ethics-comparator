from __future__ import annotations

import os
import sys

from pydantic import BaseModel

import lib.executive_reporting.engine as engine_module
from lib.executive_reporting import ExecutiveReportEngine, ExecutiveReportProfile
from lib.executive_reporting.weasyprint_runtime import ensure_weasyprint_runtime_environment


class _StubSingleReport(BaseModel):
    theme: str = "dark"


class _StubComparisonReport(BaseModel):
    theme: str = "dark"


class _StubProfile(ExecutiveReportProfile[_StubSingleReport, _StubComparisonReport]):
    single_template_name = "missing-single.html"
    comparison_template_name = "missing-comparison.html"

    def build_single_report(
        self,
        run_data: dict[str, object],
        paradox: dict[str, object],
        insight: dict[str, object] | None = None,
        narrative: dict[str, str] | None = None,
        *,
        theme: str = "light",
    ) -> _StubSingleReport:
        return _StubSingleReport(theme=theme)

    def build_comparison_report(
        self,
        runs: list[dict[str, object]],
        paradox: dict[str, object],
        insights: list[dict[str, object] | None],
        narrative: dict[str, str] | None = None,
        *,
        theme: str = "dark",
    ) -> _StubComparisonReport:
        return _StubComparisonReport(theme=theme)

    def native_single_available(self) -> bool:
        return True

    def render_native_single(self, report: _StubSingleReport) -> bytes:
        return f"NATIVE:{report.theme}".encode("utf-8")


def test_executive_report_engine_uses_profile_native_single_fallback(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(engine_module, "HTML", None)

    engine = ExecutiveReportEngine(_StubProfile(), templates_dir=tmp_path)

    rendered = engine.render_single_context(_StubSingleReport(theme="light"))

    assert rendered == b"NATIVE:light"


def test_executive_report_engine_allows_explicit_weasyprint_override(tmp_path) -> None:
    engine = ExecutiveReportEngine(_StubProfile(), templates_dir=tmp_path, html_class=None)

    rendered = engine.render_single_context(_StubSingleReport(theme="dark"))

    assert rendered == b"NATIVE:dark"


def test_weasyprint_runtime_adds_homebrew_library_path_on_macos(monkeypatch) -> None:
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setenv("DYLD_FALLBACK_LIBRARY_PATH", "/existing/lib")
    monkeypatch.setattr(
        "lib.executive_reporting.weasyprint_runtime._candidate_macos_library_dirs",
        lambda: ["/opt/homebrew/lib", "/usr/local/lib"],
    )

    ensure_weasyprint_runtime_environment()

    assert os.environ["DYLD_FALLBACK_LIBRARY_PATH"] == "/opt/homebrew/lib:/usr/local/lib:/existing/lib"
