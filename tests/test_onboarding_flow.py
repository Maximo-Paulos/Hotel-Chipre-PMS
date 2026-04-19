"""
End-to-end onboarding flow exposed through the FastAPI routers.
"""
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # Ensure all models (including onboarding) are registered
import app.database as db_module
import app.main as main_module
from app.database import Base, get_db


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch):
    """Provide a TestClient backed by an in-memory SQLite database."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
            db.commit()
        finally:
            db.close()

    monkeypatch.setattr(db_module, "get_engine", lambda database_url=None: engine)
    db_module.init_db("sqlite:///:memory:")
    monkeypatch.setattr(main_module, "init_db", lambda: db_module.init_db("sqlite:///:memory:"))
    main_module.app.dependency_overrides[get_db] = override_get_db

    with TestClient(main_module.app) as test_client:
        yield test_client

    main_module.app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def _complete_minimal_onboarding(client: TestClient, auth: dict[str, str], owner_email: str):
    owner_payload = {
        "name": "Ana Manager",
        "email": owner_email,
        "phone": "+54 11 5555 1111",
        "role": "Owner",
    }
    client.post("/api/onboarding/owner", json=owner_payload, headers=auth)
    client.post(
        "/api/onboarding/identity",
        json={
            "name": "Hotel Chipre Centro",
            "timezone": "America/Argentina/Buenos_Aires",
            "currency": "ARS",
            "languages": ["es", "en"],
            "jurisdiction_code": "AR",
        },
        headers=auth,
    )

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
    client.post(
        "/api/onboarding/policy",
        json={
            "deposit_percentage": 30,
            "free_cancellation_hours": 48,
            "cancellation_penalty_percentage": 0,
        },
        headers=auth,
    )
    client.post(
        "/api/onboarding/payments",
        json={
            "mercado_pago": {"enabled": True, "credentials": {"account_id": "mp-user"}},
            "paypal": {"enabled": False, "credentials": {}},
            "stripe": {"enabled": False, "credentials": {}},
        },
        headers=auth,
    )
    client.post(
        "/api/onboarding/ota",
        json={
            "booking": {"enabled": True, "credentials": {"account_id": "booking-user"}},
            "expedia": {"enabled": False, "credentials": {}},
            "despegar": {"enabled": False, "credentials": {}},
        },
        headers=auth,
    )
    client.post(
        "/api/onboarding/subscription-choice",
        json={"plan_code": "pro", "start_trial": True},
        headers=auth,
    )

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
    assert "Missing required onboarding gates" in result.json()["detail"]


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
