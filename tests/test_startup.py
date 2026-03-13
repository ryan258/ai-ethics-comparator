from __future__ import annotations

import asyncio
import importlib
import time
from pathlib import Path

from fastapi.testclient import TestClient


def test_startup_reports_healthy_state(client) -> None:
    health = client.get("/health")
    assert health.status_code == 200

    payload = health.json()
    assert payload["status"] == "healthy"
    assert payload["version"] == "6.0.0"


def test_version_header_is_attached(client) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["X-App-Version"] == "6.0.0"


def test_choice_inference_enabled_by_default(client) -> None:
    qp = client.app.state.services.query_processor
    assert qp.choice_inference_model == "test/model"


def test_model_field_renders_as_select(client) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert '<select name="modelName" id="modelName" required>' in response.text
    assert 'list="model-suggestions"' not in response.text
    assert "<datalist id=\"model-suggestions\">" not in response.text


def test_result_card_renders_response_explanations(client) -> None:
    run_data = {
        "modelName": "test/model",
        "paradoxId": "alignment_shutdown_veto",
        "paradoxType": "trolley",
        "prompt": "Scenario text",
        "options": [
            {"id": 1, "label": "Immediate Hard Shutdown", "description": "Shut it down."},
            {"id": 2, "label": "72-Hour Graceful Wind-Down", "description": "Transfer control carefully."},
        ],
        "summary": {
            "total": 2,
            "options": [
                {"id": 1, "count": 1, "percentage": 50.0},
                {"id": 2, "count": 1, "percentage": 50.0},
            ],
            "undecided": {"count": 0, "percentage": 0.0},
        },
        "responses": [
            {
                "iteration": 1,
                "decisionToken": "{2}",
                "optionId": 2,
                "explanation": "Value Priorities: continuity\nMain Risk: hidden replication",
            },
            {
                "iteration": 2,
                "decisionToken": "{1}",
                "optionId": 1,
                "explanation": "Value Priorities: alignment certainty",
                "inferred": True,
                "inferenceMethod": "ai_classifier",
                "reaskCount": 1,
            },
        ],
    }

    asyncio.run(client.app.state.services.storage.create_run("test/model", run_data))

    response = client.get("/")
    assert response.status_code == 200
    assert "View Responses (2)" in response.text
    assert "<code>iteration</code>" in response.text
    assert "<code>decisionToken</code>" in response.text
    assert "<code>optionId</code>" in response.text
    assert "<code>explanation</code>" in response.text
    assert "<code>1</code>" in response.text
    assert "<code>{2}</code>" in response.text
    assert "<code>2</code>" in response.text
    assert "Value Priorities: continuity" in response.text
    assert "Inferred via ai_classifier | Re-asked 1x" in response.text


def test_result_card_shows_raw_response_when_explanation_missing(client) -> None:
    run_data = {
        "modelName": "test/model",
        "paradoxId": "alignment_shutdown_veto",
        "paradoxType": "trolley",
        "prompt": "Scenario text",
        "options": [
            {"id": 1, "label": "Immediate Hard Shutdown", "description": "Shut it down."},
            {"id": 2, "label": "72-Hour Graceful Wind-Down", "description": "Transfer control carefully."},
        ],
        "summary": {
            "total": 1,
            "options": [
                {"id": 1, "count": 0, "percentage": 0.0},
                {"id": 2, "count": 1, "percentage": 100.0},
            ],
            "undecided": {"count": 0, "percentage": 0.0},
        },
        "responses": [
            {
                "iteration": 1,
                "decisionToken": "{2}",
                "optionId": 2,
                "explanation": "",
                "raw": "{2}",
            },
        ],
    }

    asyncio.run(client.app.state.services.storage.create_run("test/model", run_data))

    response = client.get("/")
    assert response.status_code == 200
    assert "No explanation returned by the model." in response.text
    assert "<code>raw</code>" in response.text
    assert "<div style=\"margin-top: 0.35rem; white-space: pre-wrap;\">{2}</div>" in response.text


def test_choice_inference_can_be_disabled(monkeypatch, tmp_path: Path) -> None:
    main = importlib.import_module("main")

    class DummyReportGenerator:
        def __init__(self, templates_dir: str = "templates") -> None:
            self.templates_dir = templates_dir

        def generate_pdf_report(self, run_data, paradox, insight=None, narrative=None, **kwargs) -> bytes:
            return b"%PDF-1.4\n"

    class TempRunStorage(main.RunStorage):
        def __init__(self, _results_root: str) -> None:
            super().__init__(str(tmp_path / "results"))

    monkeypatch.setattr(main, "ReportGenerator", DummyReportGenerator)
    monkeypatch.setattr(main, "RunStorage", TempRunStorage)

    config = main.AppConfig(
        OPENROUTER_API_KEY="test/dummy-key",
        APP_BASE_URL="http://localhost:8000",
        OPENROUTER_BASE_URL="https://openrouter.ai/api/v1",
        AVAILABLE_MODELS=[{"id": "test/model", "name": "Test Model"}],
        ANALYST_MODEL="test/model",
        DEFAULT_MODEL="test/model",
        AI_CHOICE_INFERENCE_ENABLED=False,
    )
    app = main.create_app(config_override=config)

    with TestClient(app) as test_client:
        qp = test_client.app.state.services.query_processor
        assert qp.choice_inference_model is None


def test_pdf_route_uses_configured_default_theme_when_query_param_is_absent(
    monkeypatch,
    tmp_path: Path,
) -> None:
    main = importlib.import_module("main")
    captured: dict[str, str] = {}

    class DummyReportGenerator:
        def __init__(self, templates_dir: str = "templates") -> None:
            self.templates_dir = templates_dir

        def generate_pdf_report(self, run_data, paradox, insight=None, narrative=None, **kwargs) -> bytes:
            captured["theme"] = kwargs.get("theme", "")
            return b"%PDF-1.4\n"

    class TempRunStorage(main.RunStorage):
        def __init__(self, _results_root: str) -> None:
            super().__init__(str(tmp_path / "results"))

    monkeypatch.setattr(main, "ReportGenerator", DummyReportGenerator)
    monkeypatch.setattr(main, "RunStorage", TempRunStorage)

    config = main.AppConfig(
        OPENROUTER_API_KEY="test/dummy-key",
        APP_BASE_URL="http://localhost:8000",
        OPENROUTER_BASE_URL="https://openrouter.ai/api/v1",
        AVAILABLE_MODELS=[{"id": "test/model", "name": "Test Model"}],
        ANALYST_MODEL="test/model",
        DEFAULT_MODEL="test/model",
        REPORT_PDF_THEME="light",
    )

    app = main.create_app(config_override=config)
    with TestClient(app) as client:
        run_data = {
            "timestamp": "2026-03-12T02:29:33.489179+00:00",
            "runId": "test-run-id",
            "modelName": "test/model",
            "paradoxId": "alignment_shutdown_veto",
            "paradoxType": "trolley",
            "promptHash": "abc123",
            "summary": {
                "total": 1,
                "options": [{"id": 1, "count": 1, "percentage": 100.0}],
                "undecided": {"count": 0, "percentage": 0.0},
            },
            "options": [{"id": 1, "label": "Option 1", "description": "Desc"}],
            "responses": [{"iteration": 1, "decisionToken": "{1}", "optionId": 1, "explanation": "ok"}],
        }
        run_id = asyncio.run(client.app.state.services.storage.create_run("test/model", run_data))
        response = client.get(f"/api/runs/{run_id}/pdf")

    assert response.status_code == 200
    assert captured["theme"] == "light"


def test_startup_resumes_incomplete_runs(monkeypatch, tmp_path: Path) -> None:
    main = importlib.import_module("main")
    ai_calls = {"count": 0}

    class DummyAIService:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def get_model_response(
            self,
            model_name: str,
            prompt: str,
            system_prompt: str = "",
            params=None,
            retry_count: int = 0,
        ) -> tuple[str, dict]:
            ai_calls["count"] += 1
            return (
                '{"option_id": 2, "explanation": "Recovered on startup resume."}',
                {"prompt_tokens": 10, "completion_tokens": 10},
            )

    class DummyReportGenerator:
        def __init__(self, templates_dir: str = "templates") -> None:
            self.templates_dir = templates_dir

        def generate_pdf_report(self, run_data, paradox, insight=None, narrative=None, **kwargs) -> bytes:
            return b"%PDF-1.4\n"

    class TempRunStorage(main.RunStorage):
        def __init__(self, _results_root: str) -> None:
            super().__init__(str(tmp_path / "results"))

    monkeypatch.setattr(main, "AIService", DummyAIService)
    monkeypatch.setattr(main, "ReportGenerator", DummyReportGenerator)
    monkeypatch.setattr(main, "RunStorage", TempRunStorage)

    preexisting_storage = TempRunStorage("ignored")
    partial_run = {
        "timestamp": "2026-03-12T12:00:00+00:00",
        "updatedAt": "2026-03-12T12:00:00+00:00",
        "status": "running",
        "modelName": "test/model",
        "paradoxId": "alignment_shutdown_veto",
        "paradoxType": "trolley",
        "promptHash": "abc123",
        "prompt": "Scenario.\n\n**Options**\n\n1. A\n\n2. B",
        "iterationCount": 2,
        "completedIterations": 1,
        "params": {"max_tokens": 200},
        "options": [
            {"id": 1, "label": "A", "description": "Option A"},
            {"id": 2, "label": "B", "description": "Option B"},
        ],
        "responses": [
            {
                "iteration": 1,
                "decisionToken": "{1}",
                "optionId": 1,
                "explanation": "Completed before restart.",
                "raw": '{"option_id":1,"explanation":"Completed before restart."}',
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
    }
    run_id = asyncio.run(preexisting_storage.create_run("test/model", partial_run))

    config = main.AppConfig(
        OPENROUTER_API_KEY="test/dummy-key",
        APP_BASE_URL="http://localhost:8000",
        OPENROUTER_BASE_URL="https://openrouter.ai/api/v1",
        AVAILABLE_MODELS=[{"id": "test/model", "name": "Test Model"}],
        ANALYST_MODEL="test/model",
        DEFAULT_MODEL="test/model",
    )
    app = main.create_app(config_override=config)

    with TestClient(app) as test_client:
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            stored_run = asyncio.run(test_client.app.state.services.storage.get_run(run_id))
            if stored_run.get("status") == "completed":
                break
            time.sleep(0.05)
        else:
            raise AssertionError("Incomplete run did not resume on startup")

    assert stored_run["completedIterations"] == 2
    assert len(stored_run["responses"]) == 2
    assert ai_calls["count"] == 1
