from __future__ import annotations

import pytest
from pydantic import BaseModel

from lib.executive_reporting import ExecutiveReportEngine, ExecutiveReportProfile


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



def test_engine_reports_missing_template(tmp_path):
    engine = ExecutiveReportEngine(_StubProfile(), templates_dir=tmp_path)
    with pytest.raises(RuntimeError, match="template unavailable"):
        engine.render_single_context(_StubSingleReport())


def test_engine_renders_escaped_html(tmp_path):
    (tmp_path / "missing-single.html").write_text("<h1>{{ report.theme }}</h1>")
    engine = ExecutiveReportEngine(_StubProfile(), templates_dir=tmp_path)
    assert engine.render_single_context(_StubSingleReport(theme="<script>")) == "<h1>&lt;script&gt;</h1>"
