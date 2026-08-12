from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_health_exposes_only_a_valid_full_deployment_sha(monkeypatch) -> None:
    monkeypatch.setenv("RENDER_GIT_COMMIT", "A" * 40)

    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json()["code_sha"] == "a" * 40


def test_health_does_not_echo_an_invalid_environment_value(monkeypatch) -> None:
    monkeypatch.setenv("RENDER_GIT_COMMIT", "not-a-sha-or-secret")

    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json()["code_sha"] is None
    assert "not-a-sha-or-secret" not in response.text
