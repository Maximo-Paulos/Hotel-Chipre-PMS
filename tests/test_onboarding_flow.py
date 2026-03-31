"""
End-to-end onboarding flow exposed through the FastAPI routers.
"""
import os

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


def _complete_minimal_onboarding(client: TestClient):
    owner_payload = {
        "name": "Ana Manager",
        "email": "ana@example.com",
        "phone": "+54 11 5555 1111",
        "role": "Owner",
    }
    client.post("/api/onboarding/owner", json=owner_payload)

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
    client.post("/api/onboarding/categories", json=categories_payload)

    rooms_payload = {
        "rooms": [
            {"room_number": "101", "floor": 1, "category_code": "STD"},
            {"room_number": "102", "floor": 1, "category_code": "STD"},
            {"room_number": "201", "floor": 2, "category_code": "STE"},
        ]
    }
    client.post("/api/onboarding/rooms", json=rooms_payload)

    staff_payload = {
        "staff": [
            {"name": "Lucia", "role": "Front desk", "email": "lucia@example.com"},
            {"name": "Javier", "role": "Housekeeping"},
        ]
    }
    client.post("/api/onboarding/staff", json=staff_payload)


def test_dashboard_is_blocked_until_onboarding_finishes(client: TestClient):
    # El frontend ahora siempre devuelve la SPA (200) aunque falte onboarding
    resp = client.get("/")
    assert resp.status_code == 200

    # Status reflects missing steps
    status = client.get("/api/onboarding/status")
    assert status.status_code == 200
    data = status.json()
    assert data["completed"] is False
    assert "categories" in data["missing_steps"]

    # Complete onboarding flow
    _complete_minimal_onboarding(client)

    finish = client.post("/api/onboarding/finish")
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
    result = client.post("/api/onboarding/finish")
    assert result.status_code == 400
    assert "Missing required onboarding steps" in result.json()["detail"]


def test_rooms_require_existing_category(client: TestClient):
    # Owner step ok
    client.post("/api/onboarding/owner", json={"name": "Test", "email": "t@example.com"})

    # Attempt to create rooms without categories -> error
    response = client.post(
        "/api/onboarding/rooms",
        json={"rooms": [{"room_number": "1", "floor": 0, "category_code": "NOPE"}]},
    )
    assert response.status_code == 400
    assert "Missing categories" in response.json()["detail"]
