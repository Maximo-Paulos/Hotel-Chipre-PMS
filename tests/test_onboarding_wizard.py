"""
API coverage for the expanded onboarding wizard.
"""
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models
import app.database as db_module
import app.main as main_module
from app.database import Base, get_db


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch):
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
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = testing_session_local()
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


def _register_owner(client: TestClient, email: str) -> dict[str, str]:
    with patch("app.api.auth._generate_code", return_value="123456"):
        response = client.post(
            "/api/auth/register",
            json={"email": email, "password": "Demo123!", "role": "owner"},
        )
    assert response.status_code == 201, response.text

    verify = client.post("/api/auth/verify-email", json={"email": email, "code": "123456"})
    assert verify.status_code == 200, verify.text
    payload = verify.json()
    return {
        "Authorization": f"Bearer {payload['access_token']}",
        "X-Hotel-Id": str(payload["hotel_id"]),
        "X-User-Id": payload["user"]["email"],
    }


def _complete_onboarding_setup(client: TestClient, auth: dict[str, str], owner_email: str):
    client.post(
        "/api/onboarding/owner",
        json={"name": "Ana Manager", "email": owner_email, "phone": "+54 11 5555 1111", "role": "Owner"},
        headers=auth,
    )
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
    client.post(
        "/api/onboarding/categories",
        json={
            "categories": [
                {
                    "name": "Standard Doble",
                    "code": "STD",
                    "description": "Base double room",
                    "base_price_per_night": 100.0,
                    "max_occupancy": 2,
                    "amenities": "wifi",
                }
            ]
        },
        headers=auth,
    )
    client.post(
        "/api/onboarding/rooms",
        json={"rooms": [{"room_number": "101", "floor": 1, "category_code": "STD"}]},
        headers=auth,
    )
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
            "mercado_pago": {"enabled": True, "credentials": {"account_id": "mp-user", "secret": "mp-secret"}},
            "paypal": {"enabled": True, "credentials": {"account_id": "pp-user"}},
            "stripe": {"enabled": False, "credentials": {}},
        },
        headers=auth,
    )
    client.post(
        "/api/onboarding/ota",
        json={
            "booking": {"enabled": True, "credentials": {"account_id": "booking-user"}},
            "expedia": {"enabled": False, "credentials": {}},
            "despegar": {"enabled": True, "credentials": {"account_id": "despegar-user"}},
        },
        headers=auth,
    )
    client.post(
        "/api/onboarding/subscription-choice",
        json={"plan_code": "pro", "start_trial": True},
        headers=auth,
    )
    client.post(
        "/api/onboarding/staff",
        json={"staff": [{"name": "Lucia", "role": "Front desk", "email": "lucia@example.com"}]},
        headers=auth,
    )


def test_each_step_persists(client: TestClient):
    headers = _register_owner(client, "wizard@test.com")

    owner = client.post(
        "/api/onboarding/owner",
        json={"name": "Ana Manager", "email": "wizard@test.com", "phone": "+54 11 5555 1111", "role": "Owner"},
        headers=headers,
    )
    assert owner.status_code == 200, owner.text

    identity = client.post(
        "/api/onboarding/identity",
        json={
            "name": "Hotel Chipre Centro",
            "timezone": "America/Argentina/Buenos_Aires",
            "currency": "ARS",
            "languages": ["es", "en"],
            "jurisdiction_code": "AR",
        },
        headers=headers,
    )
    assert identity.status_code == 200, identity.text
    assert identity.json()["steps"]["identity"] is True

    policy = client.post(
        "/api/onboarding/policy",
        json={
            "deposit_percentage": 25,
            "free_cancellation_hours": 72,
            "cancellation_penalty_percentage": 10,
        },
        headers=headers,
    )
    assert policy.status_code == 200, policy.text
    assert policy.json()["deposit_policy"]["deposit_percentage"] == 25

    payments = client.post(
        "/api/onboarding/payments",
        json={
            "mercado_pago": {"enabled": True, "credentials": {"account_id": "mp-user"}},
            "paypal": {"enabled": False, "credentials": {}},
            "stripe": {"enabled": False, "credentials": {}},
        },
        headers=headers,
    )
    assert payments.status_code == 200, payments.text
    assert payments.json()["payment_methods"]["mercado_pago"]["enabled"] is True
    assert payments.json()["payment_methods"]["mercado_pago"]["has_credentials"] is True

    ota = client.post(
        "/api/onboarding/ota",
        json={
            "booking": {"enabled": True, "credentials": {"account_id": "booking-user"}},
            "expedia": {"enabled": True, "credentials": {}},
            "despegar": {"enabled": False, "credentials": {}},
        },
        headers=headers,
    )
    assert ota.status_code == 200, ota.text
    assert ota.json()["ota_channels"]["booking"]["enabled"] is True


def test_invalid_data_blocks_advancement(client: TestClient):
    headers = _register_owner(client, "wizard-invalid@test.com")

    invalid_identity = client.post(
        "/api/onboarding/identity",
        json={
            "name": "Hotel",
            "timezone": "America/Argentina/Buenos_Aires",
            "currency": "ARS",
            "languages": [],
            "jurisdiction_code": "AR",
        },
        headers=headers,
    )
    assert invalid_identity.status_code == 422

    client.post(
        "/api/onboarding/payments",
        json={
            "mercado_pago": {"enabled": False, "credentials": {}},
            "paypal": {"enabled": False, "credentials": {}},
            "stripe": {"enabled": True, "credentials": {"account_id": "acct_123"}},
        },
        headers=headers,
    )

    invalid_subscription = client.post(
        "/api/onboarding/subscription-choice",
        json={"plan_code": "starter", "start_trial": False},
        headers=headers,
    )
    assert invalid_subscription.status_code == 400
    assert "Stripe" in invalid_subscription.json()["detail"]


def test_complete_nine_step_flow_works(client: TestClient):
    headers = _register_owner(client, "wizard-complete@test.com")
    _complete_onboarding_setup(client, headers, "wizard-complete@test.com")

    status_before_finish = client.get("/api/onboarding/status", headers=headers)
    assert status_before_finish.status_code == 200, status_before_finish.text
    assert status_before_finish.json()["gates"]["can_finish"] is True

    finish = client.post("/api/onboarding/finish", headers=headers)
    assert finish.status_code == 200, finish.text
    payload = finish.json()
    assert payload["completed"] is True
    assert payload["steps"]["finish"] is True
    assert payload["missing_steps"] == []


def test_idempotent_step_updates_do_not_duplicate_records(client: TestClient):
    headers = _register_owner(client, "wizard-idempotent@test.com")

    category_payload = {
        "categories": [
            {
                "name": "Standard Doble",
                "code": "STD",
                "description": "Base double room",
                "base_price_per_night": 100.0,
                "max_occupancy": 2,
                "amenities": "wifi",
            }
        ]
    }
    room_payload = {"rooms": [{"room_number": "101", "floor": 1, "category_code": "STD"}]}

    first_categories = client.post("/api/onboarding/categories", json=category_payload, headers=headers)
    second_categories = client.post("/api/onboarding/categories", json=category_payload, headers=headers)
    assert first_categories.status_code == 201, first_categories.text
    assert second_categories.status_code == 201, second_categories.text
    assert second_categories.json()["counts"]["categories"] == 1

    first_rooms = client.post("/api/onboarding/rooms", json=room_payload, headers=headers)
    second_rooms = client.post("/api/onboarding/rooms", json=room_payload, headers=headers)
    assert first_rooms.status_code == 201, first_rooms.text
    assert second_rooms.status_code == 201, second_rooms.text
    assert second_rooms.json()["counts"]["rooms"] == 1

    payments = client.post(
        "/api/onboarding/payments",
        json={
            "mercado_pago": {"enabled": True, "credentials": {"account_id": "mp-user"}},
            "paypal": {"enabled": False, "credentials": {}},
            "stripe": {"enabled": False, "credentials": {}},
        },
        headers=headers,
    )
    repeated_payments = client.post(
        "/api/onboarding/payments",
        json={
            "mercado_pago": {"enabled": True, "credentials": {"account_id": "mp-user"}},
            "paypal": {"enabled": False, "credentials": {}},
            "stripe": {"enabled": False, "credentials": {}},
        },
        headers=headers,
    )
    assert payments.status_code == 200, payments.text
    assert repeated_payments.status_code == 200, repeated_payments.text
    assert repeated_payments.json()["steps"]["payments"] is True
