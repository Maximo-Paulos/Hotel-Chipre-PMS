from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.database as db_module
import app.main as main_module
from app.database import Base, get_db
from app.dependencies.auth import AuthContext, get_auth_context
from app.models.hotel_config import HotelConfiguration
from app.models.company import Company
from app.models.permission import HotelPermissionOverride
from app.models.user import User
from app.services.timezones import hotel_today


@pytest.fixture
def api_client(monkeypatch: pytest.MonkeyPatch):
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

    monkeypatch.setattr(db_module, "get_engine", lambda database_url=None: engine)
    db_module.init_db()
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    def override_auth_context():
        return AuthContext(
            hotel_id=1,
            user_id=1,
            user_email="owner@test.com",
            user_role="owner",
            is_verified=True,
            permissions=set(),
        )

    import app.services.analytics_service as analytics_service_module

    monkeypatch.setattr(
        analytics_service_module,
        "get_subscription_snapshot",
        lambda db, hotel_id: {"plan": "pro", "status": "active", "can_write": True, "enforcement_enabled": True},
    )

    main_module.app.dependency_overrides[get_db] = override_get_db
    main_module.app.dependency_overrides[get_auth_context] = override_auth_context

    with TestClient(main_module.app) as client:
        with SessionLocal() as db:
            db.add(HotelConfiguration(id=1, owner_email="owner@test.com", subscription_active=True))
            db.add(
                User(
                    id=1,
                    email="owner@test.com",
                    password_hash="test-hash",
                    role="owner",
                    is_active=True,
                    is_verified=True,
                )
            )
            db.commit()
        yield client, SessionLocal

    main_module.app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def test_company_create_and_patch_round_trips_commercial_fields(api_client):
    client, _SessionLocal = api_client

    create = client.post(
        "/api/companies",
        json={
            "legal_name": "Acme Travel SRL",
            "display_name": "Acme Travel",
            "tax_id": "30-11111111-1",
            "country_code": "ar",
            "contact_name": "Reservations Desk",
            "email": "reservations@acme.test",
            "base_price": 175.5,
            "payment_deferred": True,
        },
    )
    assert create.status_code == 201, create.text
    body = create.json()
    assert body["contact_name"] == "Reservations Desk"
    assert body["email"] == "reservations@acme.test"
    assert body["base_price"] is None
    assert body["payment_deferred"] is True

    listed = client.get("/api/companies")
    assert listed.status_code == 200, listed.text
    assert listed.json()[0]["id"] == body["id"]
    assert listed.json()[0]["display_name"] == "Acme Travel"

    patch = client.patch(
        f"/api/companies/{body['id']}",
        json={
            "contact_name": "Corporate Ops",
            "email": "ops@acme.test",
            "base_price": 190.0,
            "payment_deferred": False,
        },
    )
    assert patch.status_code == 200, patch.text
    updated = patch.json()
    assert updated["contact_name"] == "Corporate Ops"
    assert updated["email"] == "ops@acme.test"
    assert updated["base_price"] == "190.00"
    assert updated["payment_deferred"] is False


def test_reservation_company_options_return_only_minimal_fields(api_client):
    client, SessionLocal = api_client
    with SessionLocal() as db:
        db.add(
            Company(
                hotel_id=1,
                legal_name="Acme Travel SRL",
                display_name="Acme Travel",
                tax_id="30-11111111-1",
                contact_name="Reservations Desk",
                contact_email="desk@acme.test",
            )
        )
        db.commit()

    response = client.get("/api/companies/options")
    assert response.status_code == 200, response.text
    assert response.json() == [
        {
            "id": response.json()[0]["id"],
            "display_name": "Acme Travel",
            "legal_name": "Acme Travel SRL",
            "is_active": True,
            "payment_deferred": False,
        }
    ]
    assert "tax_id" not in response.text
    assert "contact_name" not in response.text
    assert "contact_email" not in response.text


def test_company_list_normalizes_legacy_null_deferred_days(api_client):
    client, SessionLocal = api_client
    with SessionLocal() as db:
        db.add(
            Company(
                hotel_id=1,
                legal_name="Legacy Travel SRL",
                display_name="Legacy Travel",
                deferred_days=None,
            )
        )
        db.commit()

    response = client.get("/api/companies")

    assert response.status_code == 200, response.text
    assert response.json()[0]["deferred_days"] == 0


def test_company_nightly_rate_routes_create_list_and_reject_retroactive_rates(api_client):
    client, SessionLocal = api_client
    company_response = client.post(
        "/api/companies",
        json={"legal_name": "Rate QA SRL", "display_name": "Rate QA"},
    )
    assert company_response.status_code == 201, company_response.text
    company_id = company_response.json()["id"]
    with SessionLocal() as db:
        today = hotel_today(db, 1)

    created = client.post(
        f"/api/companies/{company_id}/nightly-rates",
        json={"effective_from": today.isoformat(), "amount": "125.50"},
    )
    assert created.status_code == 201, created.text
    assert created.json()["company_id"] == company_id
    assert created.json()["effective_from"] == today.isoformat()
    assert created.json()["amount"] == "125.50"

    listed = client.get(f"/api/companies/{company_id}/nightly-rates")
    assert listed.status_code == 200, listed.text
    assert listed.json()["hotel_today"] == today.isoformat()
    assert len(listed.json()["rates"]) == 1
    assert listed.json()["rates"][0]["id"] == created.json()["id"]

    retroactive = client.post(
        f"/api/companies/{company_id}/nightly-rates",
        json={"effective_from": (today - timedelta(days=1)).isoformat(), "amount": "99.00"},
    )
    assert retroactive.status_code == 400, retroactive.text


def test_company_and_nightly_rate_reads_need_view_but_writes_need_manage(api_client):
    client, SessionLocal = api_client
    create_response = client.post(
        "/api/companies",
        json={"legal_name": "Read Only Travel", "display_name": "Read Only Travel"},
    )
    assert create_response.status_code == 201, create_response.text
    company_id = create_response.json()["id"]

    with SessionLocal() as db:
        today = hotel_today(db, 1)
        db.add(
            HotelPermissionOverride(
                hotel_id=1,
                role="owner",
                permission_code="company:manage",
                allowed=False,
            )
        )
        db.commit()

    assert client.get("/api/companies").status_code == 200
    assert client.get(f"/api/companies/{company_id}").status_code == 200
    assert client.get(f"/api/companies/{company_id}/nightly-rates").status_code == 200
    denied_rate_write = client.post(
        f"/api/companies/{company_id}/nightly-rates",
        json={"effective_from": today.isoformat(), "amount": "50.00"},
    )
    assert denied_rate_write.status_code == 403
    denied_company_edit = client.patch(
        f"/api/companies/{company_id}",
        json={"display_name": "Changed without manage"},
    )
    assert denied_company_edit.status_code == 403
