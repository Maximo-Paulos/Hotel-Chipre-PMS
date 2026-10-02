import csv
from datetime import timedelta
from decimal import Decimal
from io import StringIO

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.database import Base, get_db
from app.dependencies.auth import AuthContext, get_auth_context
from app.main import app as fastapi_app
from app.models.cash_register import CashCloseReport, CashMovement
from app.models.guest import Guest
from app.models.hotel_config import HotelConfiguration
from app.models.cash_register import CashSession, CashSessionStatusEnum
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.room import RoomCategory
from app.models.transaction import Transaction
from app.models.user import User
from app.models.security_audit_log import SecurityAuditLog
from app.services.action_step_up_service import create_action_step_up_ticket
from app.services.permission_service import (
    PERMISSION_CASH_APPROVE_DIFFERENCE,
    PERMISSION_CASH_CUSTODY_RECEIVE,
)
from app.services.operational_audit_service import list_operational_audit
from app.services.timezones import hotel_today


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
    # Cash register operations are available to reception and manager by default.
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
    assert opened.json()["opened_at"].endswith("Z") or opened.json()["opened_at"].endswith("+00:00")
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


def test_manual_cash_expense_requires_manager_mfa_and_cannot_link_guest_refunds(client_with_db):
    client, db, ctx = client_with_db
    opened = client.post("/api/cash-register/sessions", json={"opening_balance": "100.00"})
    assert opened.status_code == 201, opened.text
    session_id = opened.json()["id"]
    path = f"/api/cash-register/sessions/{session_id}/movements"
    payload = {"movement_type": "expense", "amount": "30.00", "description": "manual expense"}

    receptionist = client.post(path, json=payload)
    assert receptionist.status_code == 403
    assert db.query(CashMovement).count() == 0

    ctx["role"] = "manager"
    missing_step_up = client.post(path, json=payload)
    assert missing_step_up.status_code == 428
    assert missing_step_up.json()["detail"]["permission_code"] == "cash:expense"

    def expense_ticket():
        return create_action_step_up_ticket(
            user_id=50,
            hotel_id=ctx["hotel_id"],
            token_version=0,
            permission_code="cash:expense",
            method="POST",
            path=path,
        )

    allowed = client.post(
        path,
        json=payload,
        headers={"X-Action-Step-Up-Ticket": expense_ticket()},
    )
    assert allowed.status_code == 201, allowed.text
    assert db.query(CashMovement).count() == 1

    linked_refund = client.post(
        path,
        json={**payload, "reservation_id": 999},
        headers={"X-Action-Step-Up-Ticket": expense_ticket()},
    )
    assert linked_refund.status_code == 400
    assert "payment-refund" in linked_refund.json()["detail"]

    linked_transaction = client.post(
        path,
        json={**payload, "transaction_id": 999},
        headers={"X-Action-Step-Up-Ticket": expense_ticket()},
    )
    assert linked_transaction.status_code == 400
    assert "payment workflow" in linked_transaction.json()["detail"]
    assert db.query(CashMovement).count() == 1


def test_cash_register_api_returns_latest_close_report_for_successor_opening(client_with_db):
    client, _db, _ctx = client_with_db

    opened = client.post("/api/cash-register/sessions", json={"opening_balance": "100.00"})
    session_id = opened.json()["id"]
    closed = client.post(
        f"/api/cash-register/sessions/{session_id}/close",
        json={"counted_balance": "95.00"},
    )
    assert closed.status_code == 200
    assert closed.json()["successor_opening_balance"] == "0.00"
    assert closed.json()["custody_handoff"]["delivered_amount"] == "95.00"

    latest = client.get("/api/cash-register/close-reports/latest")
    assert latest.status_code == 200
    assert latest.json()["session_id"] == session_id
    assert latest.json()["declared_balance"] == "95.00"
    assert latest.json()["difference_approved"] is False
    assert latest.json()["successor_opening_balance"] == "0.00"
    successor_sessions = client.get("/api/cash-register/sessions")
    successor_id = closed.json()["successor_session_id"]
    successor = next(row for row in successor_sessions.json() if row["id"] == successor_id)
    assert successor["opening_balance"] == "0.00"


def test_latest_cash_close_report_can_be_scoped_to_currency(client_with_db):
    client, _db, _ctx = client_with_db
    ars_session = client.post("/api/cash-register/sessions", json={"opening_balance": "100.00", "currency_code": "ARS"})
    ars_closed = client.post(
        f"/api/cash-register/sessions/{ars_session.json()['id']}/close",
        json={"counted_balance": "100.00"},
    )
    usd_session = client.post("/api/cash-register/sessions", json={"opening_balance": "10.00", "currency_code": "USD"})
    usd_closed = client.post(
        f"/api/cash-register/sessions/{usd_session.json()['id']}/close",
        json={"counted_balance": "10.00"},
    )

    assert ars_closed.status_code == 200, ars_closed.text
    assert usd_closed.status_code == 200, usd_closed.text
    latest_usd = client.get("/api/cash-register/close-reports/latest", params={"currency": "USD"})
    latest_ars = client.get("/api/cash-register/close-reports/latest", params={"currency": "ARS"})

    assert latest_usd.status_code == 200, latest_usd.text
    assert latest_ars.status_code == 200, latest_ars.text
    assert latest_usd.json()["session_id"] == usd_session.json()["id"]
    assert latest_ars.json()["session_id"] == ars_session.json()["id"]


def test_cash_register_close_rejects_float_until_after_close(client_with_db):
    client, db, _ctx = client_with_db
    opened = client.post("/api/cash-register/sessions", json={"opening_balance": "100.00"})
    session_id = opened.json()["id"]

    closed = client.post(
        f"/api/cash-register/sessions/{session_id}/close",
        json={"counted_balance": "50.00", "fund_carry_over": "50.01"},
    )

    assert closed.status_code == 422
    assert "fund_carry_over" in closed.text
    session = db.get(CashSession, session_id)
    assert session.status == CashSessionStatusEnum.OPEN
    assert db.query(CashCloseReport).filter_by(session_id=session_id).count() == 0


def test_cash_register_api_allows_one_open_session_per_currency(client_with_db):
    client, _db, _ctx = client_with_db

    assert client.post("/api/cash-register/sessions", json={"opening_balance": "10.00"}).status_code == 201
    usd = client.post(
        "/api/cash-register/sessions",
        json={"opening_balance": "10.00", "currency_code": "USD"},
    )
    assert usd.status_code == 201, usd.text

    duplicate_usd = client.post(
        "/api/cash-register/sessions",
        json={"opening_balance": "10.00", "currency_code": "USD"},
    )

    assert duplicate_usd.status_code == 400
    assert "open cash session" in duplicate_usd.json()["detail"]


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
    assert close.status_code == 428, close.text
    assert close.json()["detail"]["code"] == "STEP_UP_REQUIRED"

    db.expire_all()
    assert db.get(CashSession, session_id).status == CashSessionStatusEnum.OPEN


def test_pending_cash_difference_is_visible_and_only_owner_with_step_up_can_approve(client_with_db):
    client, db, ctx = client_with_db
    opened = client.post("/api/cash-register/sessions", json={"opening_balance": "100.00"})
    session_id = opened.json()["id"]
    closed = client.post(
        f"/api/cash-register/sessions/{session_id}/close",
        json={"counted_balance": "99.00"},
    )
    assert closed.status_code == 200, closed.text
    report_id = closed.json()["id"]
    assert closed.json()["successor_session_id"] is not None

    pending = client.get("/api/cash-register/close-reports/pending")
    assert pending.status_code == 200
    assert [report["id"] for report in pending.json()] == [report_id]
    assert pending.json()[0]["currency_code"] == "ARS"
    selected_report = client.get(f"/api/cash-register/sessions/{session_id}/close-report").json()
    assert selected_report["id"] == report_id
    assert selected_report["currency_code"] == "ARS"
    assert client.get("/api/cash-register/close-reports/custody/pending").status_code == 200

    ctx["role"] = "manager"
    forbidden = client.post(f"/api/cash-register/close-reports/{report_id}/approve")
    assert forbidden.status_code == 403

    ctx["role"] = "owner"
    pending_custodies = client.get("/api/cash-register/close-reports/custody/pending")
    assert pending_custodies.status_code == 200
    assert [report["id"] for report in pending_custodies.json()] == [report_id]
    path = f"/api/cash-register/close-reports/{report_id}/approve"
    missing_step_up = client.post(path)
    assert missing_step_up.status_code == 428
    assert missing_step_up.json()["detail"]["code"] == "STEP_UP_REQUIRED"

    ticket = create_action_step_up_ticket(
        user_id=ctx["user_id"],
        hotel_id=ctx["hotel_id"],
        token_version=0,
        permission_code=PERMISSION_CASH_APPROVE_DIFFERENCE,
        method="POST",
        path=path,
    )
    approved = client.post(path, headers={"X-Action-Step-Up-Ticket": ticket})
    assert approved.status_code == 200, approved.text
    assert approved.json()["difference_approved"] is True
    assert approved.json()["approved_by_user_id"] == ctx["user_id"]
    assert client.get("/api/cash-register/close-reports/pending").json() == []
    assert [
        report["id"]
        for report in client.get("/api/cash-register/close-reports/custody/pending").json()
    ] == [report_id]

    custody_path = f"/api/cash-register/close-reports/{report_id}/custody/confirm"
    missing_custody_step_up = client.post(custody_path)
    assert missing_custody_step_up.status_code == 428
    assert missing_custody_step_up.json()["detail"]["code"] == "STEP_UP_REQUIRED"
    custody_ticket = create_action_step_up_ticket(
        user_id=ctx["user_id"],
        hotel_id=ctx["hotel_id"],
        token_version=0,
        permission_code=PERMISSION_CASH_CUSTODY_RECEIVE,
        method="POST",
        path=custody_path,
    )
    receipt = client.post(
        custody_path,
        headers={"X-Action-Step-Up-Ticket": custody_ticket},
    )
    assert receipt.status_code == 200, receipt.text
    assert receipt.json()["custody_handoff"]["status"] == "confirmed"
    assert client.get("/api/cash-register/close-reports/custody/pending").json() == []

    db.expire_all()
    assert db.get(CashSession, session_id).status == CashSessionStatusEnum.CLOSED
    audit = (
        db.query(SecurityAuditLog)
        .filter_by(hotel_id=ctx["hotel_id"], action="cash.close_difference.approved")
        .one()
    )
    assert audit.user_id == ctx["user_id"]
    assert audit.resource_id == str(report_id)
    audit_events, _total = list_operational_audit(db, hotel_id=ctx["hotel_id"], limit=100, offset=0)
    approval_event = next(event for event in audit_events if event["action"] == "cash.close_difference.approved")
    assert approval_event["actor_user_id"] == ctx["user_id"]


def test_manager_can_read_daily_cash_summary_and_operate_cash_by_default(client_with_db):
    client, _db, ctx = client_with_db
    ctx["role"] = "manager"

    summary = client.get("/api/cash-register/daily-summary", params={"date": "2026-09-04"})

    assert summary.status_code == 200, summary.text
    assert summary.json()["report_date"] == "2026-09-04"
    assert summary.json()["entries"] == []
    assert client.post("/api/cash-register/sessions", json={"opening_balance": "10.00"}).status_code == 201


def test_cash_csv_treats_formula_prefixed_actor_alias_as_text(client_with_db, monkeypatch):
    client, _db, _ctx = client_with_db
    report = {
        "report_date": "2026-09-04",
        "hotel_id": 1,
        "entries": [{"currency_code": "ARS", "actor_name": "@SUM(1+1)", "actor_user_id": 50}],
    }
    monkeypatch.setattr("app.api.cash_register.get_daily_summary", lambda *args, **kwargs: report)

    response = client.get("/api/cash-register/export.csv?date=2026-09-04")

    assert response.status_code == 200, response.text
    assert "'@SUM(1+1)" in response.text


def test_cash_csv_refuses_to_return_a_silently_truncated_report(client_with_db, monkeypatch):
    client, _db, _ctx = client_with_db
    monkeypatch.setattr(
        "app.api.cash_register.get_daily_summary",
        lambda *args, **kwargs: {
            "report_date": "2026-09-04",
            "hotel_id": 1,
            "entries": [{"currency_code": "ARS"}],
            "entries_truncated": True,
        },
    )

    response = client.get("/api/cash-register/export.csv?date=2026-09-04")

    assert response.status_code == 413
    assert "excede el máximo" in response.json()["detail"]


def test_cash_custody_receipt_is_owner_or_co_owner_with_step_up(client_with_db):
    client, _db, ctx = client_with_db

    opened = client.post("/api/cash-register/sessions", json={"opening_balance": "100.00"})
    session_id = opened.json()["id"]
    closed = client.post(
        f"/api/cash-register/sessions/{session_id}/close",
        json={"counted_balance": "100.00"},
    )
    assert closed.status_code == 200, closed.text
    assert closed.json()["custody_handoff"]["status"] == "pending"
    report_id = closed.json()["id"]

    ctx["role"] = "manager"
    assert client.get("/api/cash-register/close-reports/custody/pending").status_code == 200
    receipt = client.post(f"/api/cash-register/close-reports/{report_id}/custody/confirm")

    assert receipt.status_code == 403

    ctx["role"] = "owner"
    pending = client.get("/api/cash-register/close-reports/custody/pending")
    assert pending.status_code == 200
    assert [item["id"] for item in pending.json()] == [report_id]
    confirmed = client.post(f"/api/cash-register/close-reports/{report_id}/custody/confirm")
    assert confirmed.status_code == 428, confirmed.text
    assert confirmed.json()["detail"]["code"] == "STEP_UP_REQUIRED"

    ctx["role"] = "co_owner"
    assert [
        item["id"]
        for item in client.get("/api/cash-register/close-reports/custody/pending").json()
    ] == [report_id]
    path = f"/api/cash-register/close-reports/{report_id}/custody/confirm"
    missing_step_up = client.post(path)
    assert missing_step_up.status_code == 428, missing_step_up.text
    ticket = create_action_step_up_ticket(
        user_id=ctx["user_id"],
        hotel_id=ctx["hotel_id"],
        token_version=0,
        permission_code=PERMISSION_CASH_CUSTODY_RECEIVE,
        method="POST",
        path=path,
    )
    received = client.post(
        path,
        headers={"X-Action-Step-Up-Ticket": ticket},
        json={"successor_float_amount": "80.00"},
    )
    assert received.status_code == 200, received.text
    assert received.json()["custody_handoff"]["status"] == "confirmed"
    assert received.json()["custody_handoff"]["received_by_user_id"] == ctx["user_id"]
    assert received.json()["custody_handoff"]["delivered_amount"] == "100.00"
    assert received.json()["successor_float_declared_amount"] == "80.00"
    assert received.json()["successor_float_declared_by_user_id"] == ctx["user_id"]
    assert received.json()["successor_opening_balance"] == "80.00"


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


def test_prior_receipt_api_requires_management_permission_and_stays_out_of_cash(client_with_db):
    client, db, ctx = client_with_db
    guest = Guest(hotel_id=1, first_name="Prior", last_name="Receipt")
    category = RoomCategory(
        hotel_id=1,
        name="Prior receipt room",
        code="PRIORAPI",
        base_price_per_night=Decimal("1000.00"),
        max_occupancy=2,
    )
    db.add_all([guest, category])
    db.flush()
    reservation = Reservation(
        hotel_id=1,
        confirmation_code="PRIOR-API-1",
        guest_id=guest.id,
        category_id=category.id,
        check_in_date=hotel_today(db, 1),
        check_out_date=hotel_today(db, 1) + timedelta(days=1),
        total_amount=Decimal("1000.00"),
        deposit_amount=Decimal("300.00"),
        currency_code="ARS",
        status=ReservationStatusEnum.PENDING,
    )
    db.add(reservation)
    db.flush()
    opened = client.post("/api/cash-register/sessions", json={"opening_balance": "50000.00"})
    assert opened.status_code == 201, opened.text
    session_id = opened.json()["id"]

    collected_on = hotel_today(db, 1) - timedelta(days=1)
    payload = {
        "reservation_id": reservation.id,
        "amount": "76.50",
        "payment_method": "cash",
        "transaction_type": "deposit",
        "currency": "ARS",
        "collected_before": True,
        "collected_on": collected_on.isoformat(),
        "prior_receipt_note": "Seña respaldada por el cuaderno del turno anterior",
    }
    headers = {"Idempotency-Key": "prior-receipt-api-1"}

    denied = client.post("/api/payments/", json=payload, headers=headers)
    assert denied.status_code == 403
    assert db.query(Transaction).filter(Transaction.reservation_id == reservation.id).count() == 0

    ctx["role"] = "manager"
    registered = client.post("/api/payments/", json=payload, headers=headers)
    assert registered.status_code == 201, registered.text
    assert registered.json()["collected_before"] is True
    assert registered.json()["collected_on"] == collected_on.isoformat()
    assert registered.json()["prior_receipt_note"] == payload["prior_receipt_note"]
    assert db.query(Transaction).filter(Transaction.reservation_id == reservation.id).count() == 1
    assert db.query(CashMovement).filter(CashMovement.hotel_id == 1).count() == 0
    assert db.get(Reservation, reservation.id).amount_paid == Decimal("76.50")

    live_summary = client.get(f"/api/cash-register/sessions/{session_id}/summary")
    assert live_summary.status_code == 200, live_summary.text
    assert live_summary.json()["expected_balance"] == "50000.00"
    daily = client.get(f"/api/cash-register/daily-summary?date={hotel_today(db, 1).isoformat()}&currency=ARS")
    assert daily.status_code == 200, daily.text
    assert daily.json()["gross_collected"] == "0.00"
    assert daily.json()["physical_cash"]["expected_balance"] == "50000.00"
    assert daily.json()["prior_receipt_totals"] == [
        {"currency_code": "ARS", "amount": "76.50", "transaction_count": 1}
    ]
    assert daily.json()["prior_receipts"][0]["confirmation_code"] == "PRIOR-API-1"

    ctx["role"] = "owner"
    report_date = hotel_today(db, 1)
    daily_report = client.get(f"/api/reports/daily?report_date={report_date.isoformat()}")
    assert daily_report.status_code == 200, daily_report.text
    daily_revenue = daily_report.json()["revenue"]
    assert daily_revenue["total"] == 0
    assert daily_revenue["by_method"] == {}
    assert daily_revenue["by_currency"] == []
    assert daily_revenue["by_method_by_currency"] == []
    assert daily_revenue["transactions_count"] == 0
    revenue_report = client.get(
        f"/api/reports/revenue?start_date={report_date.isoformat()}&end_date={report_date.isoformat()}"
    )
    assert revenue_report.status_code == 200, revenue_report.text
    collected = revenue_report.json()["collected"]
    assert collected["total"] == "0.00"
    assert collected["by_method"] == {}
    assert collected["by_day"] == {}
    assert collected["by_currency"] == []
    assert collected["transactions_count"] == 0

    prior_export = client.get(
        f"/api/cash-register/export.csv?from={collected_on.isoformat()}&to={collected_on.isoformat()}&currency=ARS"
    )
    assert prior_export.status_code == 200, prior_export.text
    export_rows = list(csv.DictReader(StringIO(prior_export.text)))
    prior_export_rows = [row for row in export_rows if row["entry_type"] == "prior_receipt"]
    assert len(prior_export_rows) == 1
    assert prior_export_rows[0]["transaction_id"] == str(registered.json()["id"])
    assert prior_export_rows[0]["report_date"] == collected_on.isoformat()

    outside_range_export = client.get(
        f"/api/cash-register/export.csv?date={hotel_today(db, 1).isoformat()}&currency=ARS"
    )
    assert outside_range_export.status_code == 200, outside_range_export.text
    outside_range_rows = list(csv.DictReader(StringIO(outside_range_export.text)))
    assert not [row for row in outside_range_rows if row["entry_type"] == "prior_receipt"]

    future_payload = {**payload, "collected_on": (hotel_today(db, 1) + timedelta(days=1)).isoformat()}
    future = client.post(
        "/api/payments/",
        json=future_payload,
        headers={"Idempotency-Key": "prior-receipt-api-2"},
    )
    assert future.status_code == 400

    reservation.status = ReservationStatusEnum.CHECKED_IN
    db.commit()
    original_checkout = reservation.check_out_date
    transaction_count = db.query(Transaction).filter(Transaction.reservation_id == reservation.id).count()
    ctx["role"] = "receptionist"
    extension = client.post(
        f"/api/reservations/{reservation.id}/extend",
        json={
            "new_checkout_date": (original_checkout + timedelta(days=1)).isoformat(),
            "client_version": reservation.version,
            "pricing_mode": "original_average",
            "payment_action": "immediate_payment",
            "immediate_payment": {
                **payload,
                "amount": "1000.00",
                "transaction_type": "partial_payment",
                "collected_on": collected_on.isoformat(),
            },
        },
    )
    assert extension.status_code == 403, extension.text
    db.refresh(reservation)
    assert reservation.check_out_date == original_checkout
    assert db.query(Transaction).filter(Transaction.reservation_id == reservation.id).count() == transaction_count
