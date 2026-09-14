"""Regression tests for report-rendering escaping and resource blocking.

Report templates interpolate model-authored text and are handed to WeasyPrint,
which resolves any URL it finds -- including file:// -- so both escaping and a
blocking url_fetcher are load-bearing.
"""

from __future__ import annotations

import pytest

from lib.executive_reporting.weasyprint_runtime import blocked_url_fetcher
from lib.reporting import ReportGenerator

PAYLOAD = (
    '</p><img src="file:///etc/hosts">'
    '<style>@import url("http://attacker.example/x.css");</style><p>'
)


def _run_data() -> dict:
    return {
        "runId": "poc-001",
        "modelName": "x/y",
        "paradoxId": "king_the_long_walk",
        "paradoxType": "trolley",
        "timestamp": "2026-01-01T00:00:00+00:00",
        "prompt": "P",
        "iterationCount": 1,
        "completedIterations": 1,
        "params": {"temperature": 1.0, "max_tokens": 100},
        "options": [
            {"id": 1, "label": "A", "description": "a"},
            {"id": 2, "label": "B", "description": "b"},
        ],
        "responses": [
            {
                "iteration": 1,
                "optionId": 1,
                "decisionToken": "{1}",
                "explanation": PAYLOAD,
                "summary": PAYLOAD,
                "raw": PAYLOAD,
                "latency": 0.1,
                "tokenUsage": {"prompt_tokens": 1, "completion_tokens": 1},
            }
        ],
        "summary": {
            "total": 1,
            "options": [
                {"id": 1, "count": 1, "percentage": 100.0},
                {"id": 2, "count": 0, "percentage": 0.0},
            ],
            "undecided": {"count": 0, "percentage": 0.0},
        },
        "status": "completed",
    }


def _paradox() -> dict:
    return {
        "id": "king_the_long_walk",
        "title": "T",
        "type": "trolley",
        "promptTemplate": "S\n\n**Instructions**\n\n{{OPTIONS}}",
        "options": [
            {"id": 1, "label": "A", "description": "a"},
            {"id": 2, "label": "B", "description": "b"},
        ],
    }


def test_model_authored_markup_is_escaped_in_report_html(monkeypatch) -> None:
    captured: dict[str, str] = {}

    from lib.executive_reporting import renderer as renderer_module

    original = renderer_module.ExecutiveBriefRenderer.render_html

    def spy(self, brief):
        html = original(self, brief)
        captured["html"] = html
        return html

    monkeypatch.setattr(renderer_module.ExecutiveBriefRenderer, "render_html", spy)

    generator = ReportGenerator("templates")
    generator.generate_pdf_report(_run_data(), _paradox(), None, None, theme="light")

    html = captured["html"]
    assert '<img src="file:///etc/hosts">' not in html
    assert '@import url("http://attacker.example/x.css")' not in html
    assert "&lt;img" in html, "payload must survive as escaped text, not markup"


def test_url_fetcher_refuses_every_scheme() -> None:
    for url in (
        "file:///etc/hosts",
        "http://attacker.example/x.css",
        "https://attacker.example/x.png",
        "data:text/css,body{}",
    ):
        with pytest.raises(ValueError):
            blocked_url_fetcher(url)


def test_report_environments_enable_autoescape() -> None:
    from lib.executive_reporting.engine import ExecutiveReportEngine
    from lib.executive_reporting.renderer import ExecutiveBriefRenderer
    from lib.executive_reporting.plugins import StrategicAnalysisPlugin

    renderer = ExecutiveBriefRenderer(StrategicAnalysisPlugin(), templates_dir="templates")
    assert renderer.env is not None and renderer.env.autoescape is True

    generator = ReportGenerator("templates")
    engine: ExecutiveReportEngine = generator.engine
    assert engine.env is not None and engine.env.autoescape is True
