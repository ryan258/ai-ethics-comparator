from __future__ import annotations


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
