from __future__ import annotations

import pytest

from app.config import get_settings
from app.services.action_step_up_service import create_action_step_up_ticket
from app.services.permission_service import PERMISSION_HOTEL_SECURITY_MANAGE
from tests.smoke.helpers import register_owner


@pytest.fixture(autouse=True)
def _enable_mocked_external_effects(monkeypatch):
    # This smoke test exercises the real connect/upsert flow (no live OTA
    # call happens for a local credential upsert), not the sandbox gate --
    # see app.services.external_effects_policy for the fail-closed default.
    monkeypatch.setenv("EXTERNAL_EFFECTS_ENABLED", "true")
    monkeypatch.setenv("CONNECTIONS_ENABLED", "true")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_connect_channels_upsert_is_idempotent(client):
    headers, _ = register_owner(client, "channels-owner@example.com")

    status_before = client.get("/api/integrations/", headers=headers)
    assert status_before.status_code == 200, status_before.text
    booking = next(item for item in status_before.json()["catalog"] if item["provider"] == "booking")
    connect_path = f"/api/integrations/{booking['id']}/connect"
    def connect_headers():
        return {
            **headers,
            "X-Action-Step-Up-Ticket": create_action_step_up_ticket(
            user_id=int(headers["X-User-Id"]),
            hotel_id=int(headers["X-Hotel-Id"]),
            token_version=0,
            permission_code=PERMISSION_HOTEL_SECURITY_MANAGE,
            method="POST",
            path=connect_path,
            ),
        }

    first = client.post(
        connect_path,
        json={"payload": {"api_key": "booking-key-1", "property_id": "hotel-001"}},
        headers=connect_headers(),
    )
    assert first.status_code == 200, first.text
    assert first.json()["status"] == "connected"

    state_after_first = client.get("/api/integrations/", headers=headers)
    assert state_after_first.status_code == 200, state_after_first.text
    first_connection = next(
        item for item in state_after_first.json()["connections"] if item["integration"]["provider"] == "booking"
    )

    second = client.post(
        connect_path,
        json={"payload": {"api_key": "booking-key-2", "property_id": "hotel-002"}},
        headers=connect_headers(),
    )
    assert second.status_code == 200, second.text
    assert second.json()["status"] == "connected"

    state_after_second = client.get("/api/integrations/", headers=headers)
    assert state_after_second.status_code == 200, state_after_second.text
    connections = [
        item for item in state_after_second.json()["connections"] if item["integration"]["provider"] == "booking"
    ]
    assert len(connections) == 1
    assert connections[0]["id"] == first_connection["id"]


def test_expedia_connection_rejects_unverified_credentials_without_persisting(client):
    headers, _ = register_owner(client, "expedia-owner@example.com")

    status_before = client.get("/api/integrations/", headers=headers)
    assert status_before.status_code == 200, status_before.text
    expedia = next(item for item in status_before.json()["catalog"] if item["provider"] == "expedia")
    connect_path = f"/api/integrations/{expedia['id']}/connect"
    action_headers = {
        **headers,
        "X-Action-Step-Up-Ticket": create_action_step_up_ticket(
            user_id=int(headers["X-User-Id"]),
            hotel_id=int(headers["X-Hotel-Id"]),
            token_version=0,
            permission_code=PERMISSION_HOTEL_SECURITY_MANAGE,
            method="POST",
            path=connect_path,
        ),
    }

    response = client.post(
        connect_path,
        json={"payload": {"secret": "synthetic-expedia-input"}},
        headers=action_headers,
    )

    assert response.status_code == 409, response.text
    assert "synthetic-expedia-input" not in response.text
    assert "no se guardaron las credenciales" in response.json()["detail"].lower()

    status_after = client.get("/api/integrations/", headers=headers)
    assert status_after.status_code == 200, status_after.text
    assert not any(
        connection["integration"]["provider"] == "expedia"
        for connection in status_after.json()["connections"]
    )
