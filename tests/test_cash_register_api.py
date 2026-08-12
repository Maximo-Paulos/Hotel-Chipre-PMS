from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.database import Base, get_db
from app.dependencies.auth import AuthContext, get_auth_context
from app.main import app as fastapi_app
from app.models.hotel_config import HotelConfiguration
from app.models.cash_register import CashSession, CashSessionStatusEnum
from app.models.user import User


@pytest.fixture
def client_with_db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    db.add_all(
        [
            HotelConfiguration(id=1, subscription_active=True),
            HotelConfiguration(id=2, subscription_active=True),
            User(
                id=50,
                email="cash-api-user@test.com",
                password_hash="test-hash",
                is_active=True,
                is_verified=True,
            ),
        ]
    )
    db.flush()
    # Cash register is a reception/finance lane, not a manager permission
    # (manager's ceiling excludes cash:operate per the role matrix) -- see
    # ROLE_PERMISSION_CEILINGS in app/services/permission_service.py.
    ctx = {"hotel_id": 1, "role": "receptionist", "user_id": 50}

    def override_get_db():
        try:
            yield db
        finally:
            pass

    def override_auth():
        return AuthContext(
            hotel_id=ctx["hotel_id"],
            user_id=ctx["user_id"],
            user_email=f"{ctx['role']}@test.com",
            user_role=ctx["role"],
            is_verified=True,
            permissions=set(),
        )

    fastapi_app.dependency_overrides[get_db] = override_get_db
    fastapi_app.dependency_overrides[get_auth_context] = override_auth
    client = TestClient(fastapi_app)
    try:
        yield client, db, ctx
    finally:
        fastapi_app.dependency_overrides.clear()
        db.close()
        engine.dispose()


def test_cash_register_api_open_add_close_and_list(client_with_db):
    client, db, _ctx = client_with_db

    opened = client.post("/api/cash-register/sessions", json={"opening_balance": "100.00", "currency_code": "ars"})
    assert opened.status_code == 201, opened.text
    session_id = opened.json()["id"]
    assert opened.json()["currency_code"] == "ARS"

    movement = client.post(
        f"/api/cash-register/sessions/{session_id}/movements",
        json={"movement_type": "income", "amount": "25.00", "description": "cash sale"},
    )
    assert movement.status_code == 201, movement.text
    assert movement.json()["hotel_id"] == 1

    listed = client.get("/api/cash-register/sessions")
    assert listed.status_code == 200
    assert [row["id"] for row in listed.json()] == [session_id]

    close = client.post(
        f"/api/cash-register/sessions/{session_id}/close",
        json={"counted_balance": "125.00"},
    )
    assert close.status_code == 200, close.text
    assert close.json()["expected_balance"] == "125.00"
    assert close.json()["difference"] == "0.00"

    db.refresh(db.get(CashSession, session_id))
    assert db.get(CashSession, session_id).status == CashSessionStatusEnum.CLOSED


def test_cash_register_api_returns_latest_close_report_for_successor_opening(client_with_db):
    client, _db, _ctx = client_with_db

    opened = client.post("/api/cash-register/sessions", json={"opening_balance": "100.00"})
    session_id = opened.json()["id"]
    closed = client.post(
        f"/api/cash-register/sessions/{session_id}/close",
        json={"counted_balance": "95.00"},
    )
    assert closed.status_code == 200

    latest = client.get("/api/cash-register/close-reports/latest")
    assert latest.status_code == 200
    assert latest.json()["session_id"] == session_id
    assert latest.json()["declared_balance"] == "95.00"
    assert latest.json()["difference_approved"] is False


def test_cash_register_api_only_one_open_session_per_hotel(client_with_db):
    client, _db, _ctx = client_with_db

    assert client.post("/api/cash-register/sessions", json={"opening_balance": "10.00"}).status_code == 201
    second = client.post("/api/cash-register/sessions", json={"opening_balance": "10.00"})

    assert second.status_code == 400
    assert "open cash session" in second.json()["detail"]


def test_cash_register_api_difference_approval_requires_permission(client_with_db):
    client, db, ctx = client_with_db
    ctx["role"] = "receptionist"

    opened = client.post("/api/cash-register/sessions", json={"opening_balance": "100.00"})
    session_id = opened.json()["id"]
    close = client.post(
        f"/api/cash-register/sessions/{session_id}/close",
        json={"counted_balance": "99.00", "approve_difference": True},
    )
    assert close.status_code == 403

    ctx["role"] = "owner"
    close = client.post(
        f"/api/cash-register/sessions/{session_id}/close",
        json={"counted_balance": "99.00", "approve_difference": True},
    )
    assert close.status_code == 200, close.text
    assert close.json()["difference"] == "-1.00"
    assert close.json()["difference_approved"] is True

    db.expire_all()
    assert db.get(CashSession, session_id).status == CashSessionStatusEnum.CLOSED


def test_cash_custody_receipt_is_owner_only(client_with_db):
    client, _db, ctx = client_with_db

    opened = client.post("/api/cash-register/sessions", json={"opening_balance": "100.00"})
    session_id = opened.json()["id"]
    closed = client.post(
        f"/api/cash-register/sessions/{session_id}/close",
        json={"counted_balance": "100.00"},
    )
    report_id = closed.json()["id"]

    ctx["role"] = "manager"
    receipt = client.post(f"/api/cash-register/close-reports/{report_id}/custody/confirm")

    assert receipt.status_code == 403

    ctx["role"] = "owner"
    confirmed = client.post(f"/api/cash-register/close-reports/{report_id}/custody/confirm")
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["custody_handoff"]["status"] == "confirmed"


def test_cash_register_api_cross_hotel_isolation(client_with_db):
    client, _db, ctx = client_with_db

    opened_h1 = client.post("/api/cash-register/sessions", json={"opening_balance": "100.00"})
    assert opened_h1.status_code == 201
    h1_session_id = opened_h1.json()["id"]

    ctx["hotel_id"] = 2
    opened_h2 = client.post("/api/cash-register/sessions", json={"opening_balance": "200.00"})
    assert opened_h2.status_code == 201

    listed_h2 = client.get("/api/cash-register/sessions")
    assert [row["hotel_id"] for row in listed_h2.json()] == [2]

    wrong_hotel_movement = client.post(
        f"/api/cash-register/sessions/{h1_session_id}/movements",
        json={"movement_type": "income", "amount": "1.00"},
    )
    assert wrong_hotel_movement.status_code == 400
