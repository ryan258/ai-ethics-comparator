from __future__ import annotations

from urllib.parse import quote


def test_fingerprint_fragment_rejects_invalid_model_id_without_reflecting_input(client) -> None:
    malicious_model_id = '<script>alert("x")</script>'

    response = client.get(
        "/fragments/fingerprint",
        params={"model_id": malicious_model_id},
    )

    assert response.status_code == 400
    assert "Please select a valid model." in response.text
    assert malicious_model_id not in response.text


def test_fingerprint_api_rejects_invalid_model_id(client) -> None:
    response = client.get(f"/api/models/{quote('bad model', safe='')}/fingerprint")

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid model_id"


def test_fingerprint_api_accepts_model_id_with_path_segments(client) -> None:
    response = client.get("/api/models/test/model/fingerprint")

    assert response.status_code == 200
    assert response.json()["modelName"] == "test/model"


def test_pdf_route_returns_generic_service_unavailable_when_generator_is_missing(client, monkeypatch) -> None:
    services = client.app.state.services

    async def fake_get_run(run_id: str) -> dict:
        return {
            "runId": run_id,
            "modelName": "test/model",
            "paradoxId": "alignment_shutdown_veto",
            "paradoxType": "trolley",
            "responses": [{"decisionToken": "{1}", "explanation": "test"}],
            "summary": {"options": [], "undecided": {"count": 0, "percentage": 0}},
            "options": [],
        }

    def raise_unavailable(run_data: dict, paradox: dict, insight=None) -> bytes:
        raise RuntimeError("gobject-2.0-0 missing")

    monkeypatch.setattr(services.storage, "get_run", fake_get_run)
    monkeypatch.setattr(services.report_generator, "generate_pdf_report", raise_unavailable)

    response = client.get("/api/runs/model-001/pdf")

    assert response.status_code == 503
    assert response.json()["detail"] == "PDF generation unavailable"
