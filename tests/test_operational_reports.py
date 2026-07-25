from datetime import date
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
from app.models.cash_register import CashSession, CashSessionStatusEnum
from app.models.guest import Guest
from app.models.hotel_config import HotelConfiguration
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.room import Room, RoomCategory, RoomStatusEnum
from app.models.room_block import RoomBlock, RoomBlockReasonEnum
from app.models.user import User


@pytest.fixture
def reports_client():
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

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    db.add_all(
        [
            HotelConfiguration(id=1, hotel_name="Hotel Uno", subscription_active=True),
            HotelConfiguration(id=2, hotel_name="Hotel Dos", subscription_active=True),
            User(
                id=1100,
                email="reports@test.com",
                password_hash="test-hash",
                is_active=True,
                is_verified=True,
            ),
        ]
    )
    db.flush()

    ctx = {"hotel_id": 1, "role": "manager", "user_id": 1100}

    def override_get_db():
        try:
            yield db
        finally:
            pass

    def override_auth():
        return AuthContext(
            hotel_id=ctx["hotel_id"],
            user_id=ctx["user_id"],
            user_email="reports@test.com",
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


def _make_room_set(db, hotel_id: int, prefix: str = "") -> tuple[RoomCategory, list[Room]]:
    category = RoomCategory(
        hotel_id=hotel_id,
        name=f"{prefix}Standard",
        code=f"{prefix}STD",
        base_price_per_night=Decimal("100.00"),
        max_occupancy=2,
    )
    db.add(category)
    db.flush()
    rooms = [
        Room(
            hotel_id=hotel_id,
            category_id=category.id,
            room_number=f"{prefix}{number}",
            floor=1,
            status=RoomStatusEnum.AVAILABLE,
        )
        for number in ("101", "102", "103")
    ]
    db.add_all(rooms)
    db.flush()
    return category, rooms


def _make_guest(db, hotel_id: int, suffix: str) -> Guest:
    guest = Guest(
        hotel_id=hotel_id,
        first_name=f"Guest{suffix}",
        last_name="Report",
        document_number=f"DOC{hotel_id}{suffix}",
        terms_accepted=True,
    )
    db.add(guest)
    db.flush()
    return guest


def _make_reservation(
    db,
    *,
    hotel_id: int,
    guest: Guest,
    category: RoomCategory,
    room: Room | None,
    code: str,
    check_in: date,
    check_out: date,
    total: str = "200.00",
    paid: str = "0.00",
    status: ReservationStatusEnum = ReservationStatusEnum.PENDING,
    requires_manual_review: bool = False,
    allocation_status: str = "assigned",
) -> Reservation:
    reservation = Reservation(
        hotel_id=hotel_id,
        guest_id=guest.id,
        category_id=category.id,
        room_id=room.id if room else None,
        confirmation_code=code,
        check_in_date=check_in,
        check_out_date=check_out,
        total_amount=Decimal(total),
        amount_paid=Decimal(paid),
        status=status,
        num_adults=1,
        requires_manual_review=requires_manual_review,
        allocation_status=allocation_status,
    )
    db.add(reservation)
    db.flush()
    return reservation


def test_daily_report_includes_pending_payment_late_arrivals_and_room_blocks(reports_client):
    client, db, _ctx = reports_client
    report_date = date(2026, 6, 13)
    category, rooms = _make_room_set(db, 1, "A")
    pending_guest = _make_guest(db, 1, "pending")
    late_guest = _make_guest(db, 1, "late")
    departing_guest = _make_guest(db, 1, "departing")

    pending = _make_reservation(
        db,
        hotel_id=1,
        guest=pending_guest,
        category=category,
        room=rooms[0],
        code="RPT-PENDING",
        check_in=report_date,
        check_out=date(2026, 6, 15),
        total="300.00",
        paid="100.00",
    )
    late = _make_reservation(
        db,
        hotel_id=1,
        guest=late_guest,
        category=category,
        room=rooms[1],
        code="RPT-LATE",
        check_in=date(2026, 6, 12),
        check_out=date(2026, 6, 14),
        total="150.00",
        paid="150.00",
    )
    _make_reservation(
        db,
        hotel_id=1,
        guest=departing_guest,
        category=category,
        room=rooms[2],
        code="RPT-DEPART",
        check_in=date(2026, 6, 11),
        check_out=report_date,
        total="100.00",
        paid="100.00",
        status=ReservationStatusEnum.CHECKED_IN,
    )
    block = RoomBlock(
        hotel_id=1,
        room_id=rooms[2].id,
        reason_code=RoomBlockReasonEnum.MAINTENANCE,
        starts_at=date(2026, 6, 12),
        ends_at=date(2026, 6, 14),
        reason_note="AC repair",
    )
    db.add(block)
    db.add(CashSession(hotel_id=1, status=CashSessionStatusEnum.OPEN, opening_balance=Decimal("500.00")))
    db.flush()

    response = client.get("/api/reports/operational/daily", params={"report_date": report_date.isoformat()})

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["hotel_id"] == 1
    assert payload["arrivals"]["count"] == 1
    assert payload["departures"]["count"] == 1
    assert [item["reservation_id"] for item in payload["pending_payments"]["reservations"]] == [pending.id]
    assert [item["reservation_id"] for item in payload["late_arrivals"]] == [late.id]
    assert [item["room_block_id"] for item in payload["active_room_blocks"]] == [block.id]
    assert payload["cash_session"]["status"] == "open"


def test_daily_report_is_hotel_scoped(reports_client):
    client, db, _ctx = reports_client
    report_date = date(2026, 6, 13)
    category_1, rooms_1 = _make_room_set(db, 1, "H1")
    category_2, rooms_2 = _make_room_set(db, 2, "H2")
    _make_reservation(
        db,
        hotel_id=1,
        guest=_make_guest(db, 1, "h1"),
        category=category_1,
        room=rooms_1[0],
        code="RPT-H1",
        check_in=report_date,
        check_out=date(2026, 6, 14),
        total="120.00",
        paid="0.00",
    )
    _make_reservation(
        db,
        hotel_id=2,
        guest=_make_guest(db, 2, "h2"),
        category=category_2,
        room=rooms_2[0],
        code="RPT-H2",
        check_in=report_date,
        check_out=date(2026, 6, 14),
        total="999.00",
        paid="0.00",
    )

    response = client.get("/api/reports/operational/daily", params={"report_date": report_date.isoformat()})

    assert response.status_code == 200, response.text
    codes = {item["confirmation_code"] for item in response.json()["arrivals"]["reservations"]}
    assert codes == {"RPT-H1"}


def test_available_with_review_surfaces_in_report(reports_client):
    client, db, _ctx = reports_client
    report_date = date(2026, 6, 13)
    category, rooms = _make_room_set(db, 1, "REV")
    review_reservation = _make_reservation(
        db,
        hotel_id=1,
        guest=_make_guest(db, 1, "review"),
        category=category,
        room=rooms[0],
        code="RPT-REVIEW",
        check_in=date(2026, 6, 14),
        check_out=date(2026, 6, 15),
        total="100.00",
        paid="100.00",
        status=ReservationStatusEnum.FULLY_PAID,
        requires_manual_review=True,
        allocation_status="manual_review",
    )

    response = client.get("/api/reports/operational/daily", params={"report_date": report_date.isoformat()})

    assert response.status_code == 200, response.text
    assert response.json()["available_with_review"] == [
        {
            "reservation_id": review_reservation.id,
            "confirmation_code": "RPT-REVIEW",
            "room_id": rooms[0].id,
            "room_number": "REV101",
            "check_in_date": "2026-06-14",
            "check_out_date": "2026-06-15",
            "allocation_status": "manual_review",
        }
    ]


def test_reports_permission_denied_for_housekeeping(reports_client):
    client, _db, ctx = reports_client
    ctx["role"] = "housekeeping"

    response = client.get("/api/reports/operational/daily", params={"report_date": "2026-06-13"})

    assert response.status_code == 403


def test_daily_report_pending_payments_reflect_consumption_charges(reports_client):
    """A fully-paid stay that later gets a consumption charge (BillingAdjustment)
    must show up as a pending payment with the real balance due, matching the
    canonical operational_balance_due helper used elsewhere in the app."""
    client, db, _ctx = reports_client
    report_date = date(2026, 6, 13)
    category, rooms = _make_room_set(db, 1, "C")
    guest = _make_guest(db, 1, "consumption")
    reservation = _make_reservation(
        db,
        hotel_id=1,
        guest=guest,
        category=category,
        room=rooms[0],
        code="RPT-CONSUME",
        check_in=date(2026, 6, 12),
        check_out=date(2026, 6, 15),
        total="200.00",
        paid="200.00",
        status=ReservationStatusEnum.CHECKED_IN,
    )
    db.commit()

    # Real journey: charge a consumption via the normal API, not a DB write.
    charge_response = client.post(
        f"/api/reservations/{reservation.id}/charges",
        json={"amount": "50.00", "currency_code": "ARS", "description": "Minibar QA"},
    )
    assert charge_response.status_code == 201, charge_response.text

    response = client.get("/api/reports/operational/daily", params={"report_date": report_date.isoformat()})

    assert response.status_code == 200, response.text
    payload = response.json()
    pending_ids = [item["reservation_id"] for item in payload["pending_payments"]["reservations"]]
    assert reservation.id in pending_ids, (
        "A stay with an unpaid consumption charge must appear in pending_payments"
    )
    pending_item = next(
        item for item in payload["pending_payments"]["reservations"] if item["reservation_id"] == reservation.id
    )
    assert Decimal(pending_item["balance_due"]) == Decimal("50.00")
    alert_reservation_ids = {
        alert["reservation_id"] for alert in payload["alerts"] if alert["code"] == "pending_payment"
    }
    assert reservation.id in alert_reservation_ids
