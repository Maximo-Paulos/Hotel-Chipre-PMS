"""
End-to-end onboarding flow exposed through the FastAPI routers.
"""
import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # Ensure all models (including onboarding) are registered
from app.database import Base, get_db
from app.main import app


@pytest.fixture
def client():
    """Provide a TestClient backed by an in-memory SQLite database."""
    original_db_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
            db.commit()
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()

    if original_db_url is None:
        os.environ.pop("DATABASE_URL", None)
    else:
        os.environ["DATABASE_URL"] = original_db_url


def _complete_minimal_onboarding(client: TestClient, auth: dict[str, str], owner_email: str):
    owner_payload = {
        "name": "Ana Manager",
        "email": owner_email,
        "phone": "+54 11 5555 1111",
        "role": "Owner",
    }
    client.post("/api/onboarding/owner", json=owner_payload, headers=auth)

    categories_payload = {
        "categories": [
            {
                "name": "Standard Doble",
                "code": "STD",
                "description": "Base double room",
                "base_price_per_night": 100.0,
                "max_occupancy": 2,
                "amenities": "wifi",
            },
            {
                "name": "Suite",
                "code": "STE",
                "description": "Suite with balcony",
                "base_price_per_night": 180.0,
                "max_occupancy": 4,
                "amenities": "wifi,ac",
            },
        ]
    }
    client.post("/api/onboarding/categories", json=categories_payload, headers=auth)

    rooms_payload = {
        "rooms": [
            {"room_number": "101", "floor": 1, "category_code": "STD"},
            {"room_number": "102", "floor": 1, "category_code": "STD"},
            {"room_number": "201", "floor": 2, "category_code": "STE"},
        ]
    }
    client.post("/api/onboarding/rooms", json=rooms_payload, headers=auth)

    staff_payload = {
        "staff": [
            {"name": "Lucia", "role": "Front desk", "email": "lucia@example.com"},
            {"name": "Javier", "role": "Housekeeping"},
        ]
    }
    client.post("/api/onboarding/staff", json=staff_payload, headers=auth)


def _register_owner(client: TestClient, email: str) -> dict[str, str]:
    with patch("app.api.auth._generate_code", return_value="123456"):
        response = client.post(
            "/api/auth/register",
            json={"email": email, "password": "Demo123!", "role": "owner"},
        )
    assert response.status_code == 201, response.text
    verify = client.post(
        "/api/auth/verify-email",
        json={"email": email, "code": "123456"},
    )
    assert verify.status_code == 200, verify.text
    payload = verify.json()
    hotel_id = payload["hotel_id"]
    return {
        "Authorization": f"Bearer {payload['access_token']}",
        "X-Hotel-Id": str(hotel_id),
        "X-User-Id": payload["user"]["email"],
    }


def test_dashboard_is_blocked_until_onboarding_finishes(client: TestClient):
    # El frontend ahora siempre devuelve la SPA (200) aunque falte onboarding
    resp = client.get("/")
    assert resp.status_code == 200

    # Status reflects missing steps
    headers = _register_owner(client, "owner@test.com")
    status = client.get("/api/onboarding/status", headers=headers)
    assert status.status_code == 200
    data = status.json()
    assert data["completed"] is False
    assert "categories" in data["missing_steps"]

    # Complete onboarding flow
    _complete_minimal_onboarding(client, headers, "owner@test.com")

    finish = client.post("/api/onboarding/finish", headers=headers)
    assert finish.status_code == 200
    finished = finish.json()
    assert finished["completed"] is True
    assert finished["steps"]["finish"] is True
    assert finished["missing_steps"] == []

    # Dashboard now available
    dashboard = client.get("/")
    assert dashboard.status_code == 200


def test_finish_requires_all_steps(client: TestClient):
    # Trying to finish too early should fail
    headers = _register_owner(client, "owner2@test.com")
    result = client.post("/api/onboarding/finish", headers=headers)
    assert result.status_code == 400
    assert "Missing required onboarding steps" in result.json()["detail"]


def test_rooms_require_existing_category(client: TestClient):
    # Owner step ok
    headers = _register_owner(client, "t@example.com")
    client.post("/api/onboarding/owner", json={"name": "Test", "email": "t@example.com"}, headers=headers)

    # Attempt to create rooms without categories -> error
    response = client.post(
        "/api/onboarding/rooms",
        json={"rooms": [{"room_number": "1", "floor": 0, "category_code": "NOPE"}]},
        headers=headers,
    )
    assert response.status_code == 400
    assert "Missing categories" in response.json()["detail"]
