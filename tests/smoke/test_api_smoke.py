from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


def _register_owner(client: TestClient, email: str) -> tuple[dict[str, str], int]:
    with patch("app.api.auth._generate_code", return_value="123456"):
        response = client.post(
            "/api/auth/register",
            json={"email": email, "password": "Demo123!", "role": "owner"},
        )
    assert response.status_code == 201, response.text
    verify = client.post("/api/auth/verify-email", json={"email": email, "code": "123456"})
    assert verify.status_code == 200, verify.text
    payload = verify.json()
    hotel_id = payload["hotel_id"]
    headers = {
        "Authorization": f"Bearer {payload['access_token']}",
        "X-Hotel-Id": str(hotel_id),
        "X-User-Id": payload["user"]["email"],
    }
    return headers, hotel_id


def test_initial_state_is_empty(client: TestClient):
    health = client.get("/health")
    assert health.status_code == 200

    headers, _ = _register_owner(client, "owner1@example.com")
    status = client.get("/api/onboarding/status", headers=headers)
    assert status.status_code == 200, status.text
    data = status.json()
    assert data["steps"]["owner"] is False
    assert data["counts"]["categories"] == 0
    assert data["counts"]["rooms"] == 0


def test_onboarding_flow_complete(client: TestClient):
    headers, _ = _register_owner(client, "owner1@example.com")
    owner = client.post(
        "/api/onboarding/owner",
        json={"name": "Owner One", "email": "owner1@example.com", "phone": "123", "role": "owner"},
        headers=headers,
    )
    assert owner.status_code == 200, owner.text

    categories = client.post(
        "/api/onboarding/categories",
        json={
            "categories": [
                {"name": "Standard", "code": "STD", "description": "Std", "base_price_per_night": 100, "max_occupancy": 2},
                {"name": "Superior", "code": "SUP", "description": "Sup", "base_price_per_night": 150, "max_occupancy": 3},
            ]
        },
        headers=headers,
    )
    assert categories.status_code == 201, categories.text

    rooms = client.post(
        "/api/onboarding/rooms",
        json={
            "rooms": [
                {"room_number": "101", "floor": 1, "category_code": "STD"},
                {"room_number": "201", "floor": 2, "category_code": "SUP"},
            ]
        },
        headers=headers,
    )
    assert rooms.status_code == 201, rooms.text

    staff = client.post(
        "/api/onboarding/staff",
        json={"staff": [{"name": "Recep", "role": "receptionist", "email": "r@example.com"}]},
        headers=headers,
    )
    assert staff.status_code == 200, staff.text

    finish = client.post("/api/onboarding/finish", headers=headers)
    assert finish.status_code == 200, finish.text
    data = finish.json()
    assert data["completed"] is True
    assert all(data["steps"].values())


def test_multihotel_isolation_owner_state(client: TestClient):
    headers1, hotel1 = _register_owner(client, "h1@example.com")
    owner1 = client.post(
        "/api/onboarding/owner",
        json={"name": "Owner H1", "email": "h1@example.com", "phone": "123", "role": "owner"},
        headers=headers1,
    )
    assert owner1.status_code == 200, owner1.text

    headers2, hotel2 = _register_owner(client, "h2@example.com")
    owner2 = client.post(
        "/api/onboarding/owner",
        json={"name": "Owner H2", "email": "h2@example.com", "phone": "456", "role": "owner"},
        headers=headers2,
    )
    assert owner2.status_code == 200, owner2.text

    status1 = client.get("/api/onboarding/status", headers=headers1)
    status2 = client.get("/api/onboarding/status", headers=headers2)
    assert status1.status_code == 200 and status2.status_code == 200

    assert status1.json()["owner"]["email"] == "h1@example.com"
    assert status2.json()["owner"]["email"] == "h2@example.com"
    assert hotel1 != hotel2
    assert status1.json()["hotel_id"] == hotel1
    assert status2.json()["hotel_id"] == hotel2


def test_permissions_headers_applied_to_config(client: TestClient):
    headers, hotel_id = _register_owner(client, "config-owner@example.com")
    cfg = client.get("/api/config/", headers=headers)
    assert cfg.status_code == 200, cfg.text
    assert cfg.json()["id"] == hotel_id

    # Update and read back
    update = client.patch(
        "/api/config/",
        json={"deposit_percentage": 35.0, "hotel_name": "Hotel Cinco"},
        headers=headers,
    )
    assert update.status_code == 200, update.text
    reget = client.get("/api/config/", headers=headers)
    assert reget.json()["deposit_percentage"] == 35.0
    assert reget.json()["hotel_name"] == "Hotel Cinco"


def test_connections_connect_endpoint(client: TestClient):
    resp = client.post("/api/connections/mercadopago/connect", json={"credentials": {"token": "abc"}})
    assert resp.status_code == 410
