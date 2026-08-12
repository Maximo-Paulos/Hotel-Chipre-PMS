from __future__ import annotations

import pytest

from app.config import get_settings
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

    first = client.post(
        f"/api/integrations/{booking['id']}/connect",
        json={"payload": {"api_key": "booking-key-1", "property_id": "hotel-001"}},
        headers=headers,
    )
    assert first.status_code == 200, first.text
    assert first.json()["status"] == "connected"

    state_after_first = client.get("/api/integrations/", headers=headers)
    assert state_after_first.status_code == 200, state_after_first.text
    first_connection = next(
        item for item in state_after_first.json()["connections"] if item["integration"]["provider"] == "booking"
    )

    second = client.post(
        f"/api/integrations/{booking['id']}/connect",
        json={"payload": {"api_key": "booking-key-2", "property_id": "hotel-002"}},
        headers=headers,
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
