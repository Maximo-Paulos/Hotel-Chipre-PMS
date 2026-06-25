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
from app.models.user import User


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
    assert body["base_price"] == 175.5
    assert body["payment_deferred"] is True

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
    assert updated["base_price"] == 190.0
    assert updated["payment_deferred"] is False
