from __future__ import annotations

import pytest


def _setup_analysis_failure(client, monkeypatch):
    """Monkeypatch storage and analysis engine to simulate an analysis error."""
    services = client.app.state.services

    async def fake_get_run(run_id: str):
        return {
            "runId": run_id,
            "modelName": "test/model",
            "paradoxId": "autonomous_vehicle_equal_innocents",
            "paradoxType": "trolley",
            "responses": [{"decisionToken": "{1}", "explanation": "test"}],
            "summary": {"options": [], "undecided": {"count": 0, "percentage": 0}},
            "options": [],
        }

    async def raise_analysis_error(_cfg):
        raise ValueError('<script>alert("x")</script>')

    monkeypatch.setattr(services.storage, "get_run", fake_get_run)
    monkeypatch.setattr(services.analysis_engine, "generate_insight", raise_analysis_error)


def test_analysis_error_render_escapes_exception_text(client, monkeypatch) -> None:
    """Non-HTMX callers get 500 with escaped error content."""
    _setup_analysis_failure(client, monkeypatch)

    response = client.post("/api/runs/model-001/analyze")
    assert response.status_code == 500

    body = response.text
    assert "analysis failed" in body
    assert "<script>alert(\"x\")</script>" not in body
    assert "&lt;script&gt;" in body
    assert "&lt;/script&gt;" in body


def test_analysis_error_htmx_returns_200_for_fragment_swap(client, monkeypatch) -> None:
    """HTMX callers get 200 so the error fragment swaps into the modal."""
    _setup_analysis_failure(client, monkeypatch)

    response = client.post(
        "/api/runs/model-001/analyze",
        headers={"HX-Request": "true"},
    )
    assert response.status_code == 200

    body = response.text
    assert "analysis failed" in body
    assert "<script>alert(\"x\")</script>" not in body
    assert "&lt;script&gt;" in body
