"""Focused regression coverage for staff permission boundaries."""

from datetime import date, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.api import bookings, guests, reports, reservations, rooms
from app.config import get_settings
from app.database import Base, get_db
from app.dependencies.auth import AuthContext, get_auth_context
from app.models.guest import Guest
from app.models.hotel_config import HotelConfiguration
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.room_block import RoomBlock, RoomBlockReasonEnum
from app.models.room import Room, RoomCategory, RoomHousekeepingStatusEnum, RoomStatusEnum
from app.services.permission_service import (
    DEFAULT_MATRIX,
    PERMISSION_CASH_APPROVE_DIFFERENCE,
    PERMISSION_CASH_CUSTODY_RECEIVE,
    PERMISSION_CASH_OPERATE,
    PERMISSION_CASH_RECORD_PRIOR_RECEIPT,
    PERMISSION_GUEST_CREATE,
    PERMISSION_GUEST_EDIT,
    PERMISSION_GUEST_TAGS,
    PERMISSION_GUEST_VIEW,
    PERMISSION_HOUSEKEEPING_BOARD_VIEW,
    PERMISSION_OCCUPANCY_VIEW,
    PERMISSION_OPERATIONS_AUDIT_VIEW,
    PERMISSION_PAYMENT_PROOF_REVIEW,
    PERMISSION_PAYMENT_PROOF_VIEW,
    PERMISSION_REPORTS_FINANCIAL_VIEW,
    PERMISSION_REPORTS_OPERATIONAL_VIEW,
    PERMISSION_ROOM_CLEANING_STATUS,
    ROLE_CODES,
    get_effective_permissions,
)


@pytest.fixture
def role_client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = session_factory()
    app = FastAPI()
    for router in (guests.router, reports.router, rooms.router, reservations.router, bookings.router):
        app.include_router(router)

    auth = {"role": "owner", "hotel_id": 1, "user_id": 501}

    def override_db():
        yield db

    def override_auth():
        return AuthContext(
            hotel_id=auth["hotel_id"],
            user_id=auth["user_id"],
            user_email=f"{auth['role']}@example.test",
            user_role=auth["role"],
            is_verified=True,
            permissions=set(),
        )

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_auth_context] = override_auth

    db.add(HotelConfiguration(id=1, hotel_name="Role Hotel", subscription_active=True))
    db.flush()
    category = RoomCategory(
        hotel_id=1,
        name="Standard",
        code="STD",
        base_price_per_night=100,
        max_occupancy=2,
    )
    db.add(category)
    db.flush()
    room = Room(
        hotel_id=1,
        category_id=category.id,
        room_number="101",
        floor=1,
        status=RoomStatusEnum.AVAILABLE,
    )
    guest = Guest(hotel_id=1, first_name="Ana", last_name="Prueba")
    db.add_all([room, guest])
    db.commit()

    with TestClient(app) as client:
        yield client, db, auth, room, guest, category

    db.close()
    engine.dispose()


def test_receptionist_guest_permissions_are_effective(role_client):
    _client, db, _auth, _room, _guest, _category = role_client

    permissions = set(get_effective_permissions(db, 1, "receptionist"))

    assert {
        PERMISSION_GUEST_VIEW,
        PERMISSION_GUEST_CREATE,
        PERMISSION_GUEST_EDIT,
        PERMISSION_GUEST_TAGS,
    }.issubset(permissions)
    assert "guest:export" not in permissions


def test_booking_demo_seed_endpoint_fails_closed_in_live_with_flags(role_client, monkeypatch):
    client, db, _auth, _room, _guest, _category = role_client
    monkeypatch.setenv("APP_ENV", "live")
    monkeypatch.setenv("ENVIRONMENT", "live")
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("TESTING", "true")
    get_settings.cache_clear()

    before = (
        db.query(Reservation).count(),
        db.query(RoomCategory).count(),
        db.query(Room).count(),
        db.query(Guest).count(),
    )

    def unexpected_seed_work(*_args, **_kwargs):
        pytest.fail("A denied booking demo-seed request reached its side effects.")

    monkeypatch.setattr(bookings, "hotel_today", unexpected_seed_work)
    try:
        response = client.post("/api/bookings/demo-seed")
    finally:
        get_settings.cache_clear()

    assert response.status_code == 404, response.text
    after = (
        db.query(Reservation).count(),
        db.query(RoomCategory).count(),
        db.query(Room).count(),
        db.query(Guest).count(),
    )
    assert after == before


def test_housekeeping_cannot_access_guest_or_reservation_pii(role_client):
    client, _db, auth, _room, guest, _category = role_client
    auth["role"] = "housekeeping"

    assert client.get("/api/guests/").status_code == 403
    assert client.get(f"/api/guests/{guest.id}").status_code == 403
    assert client.get("/api/reservations/").status_code == 403
    assert client.get("/api/reservations/actions/pending").status_code == 403
    assert (
        client.get(
            "/api/reservations/occupancy-grid",
            params={"date_from": date.today().isoformat(), "date_to": (date.today() + timedelta(days=1)).isoformat()},
        ).status_code
        == 403
    )
    assert client.get("/api/bookings/").status_code == 403


def test_manager_can_read_reservations_operationally(role_client):
    client, _db, auth, _room, _guest, _category = role_client
    auth["role"] = "manager"

    assert client.get("/api/reservations/").status_code == 200
    assert client.get("/api/reservations/actions/pending").status_code == 200
    today = date.today()
    assert (
        client.get(
            "/api/reservations/occupancy-grid",
            params={"date_from": today.isoformat(), "date_to": (today + timedelta(days=1)).isoformat()},
        ).status_code
        == 200
    )


def test_report_permissions_split_operational_from_financial(role_client):
    client, db, auth, _room, _guest, _category = role_client
    auth["role"] = "manager"

    manager_permissions = set(get_effective_permissions(db, 1, "manager"))
    assert PERMISSION_REPORTS_OPERATIONAL_VIEW in manager_permissions
    assert PERMISSION_REPORTS_FINANCIAL_VIEW not in manager_permissions
    assert PERMISSION_CASH_OPERATE in manager_permissions
    assert PERMISSION_CASH_APPROVE_DIFFERENCE not in manager_permissions
    assert PERMISSION_CASH_CUSTODY_RECEIVE not in manager_permissions
    assert client.get("/api/reports/occupancy").status_code == 200
    assert client.get("/api/reports/daily").status_code == 403
    assert client.get("/api/reports/revenue").status_code == 403

    auth["role"] = "owner"
    assert client.get("/api/reports/daily").status_code == 200
    assert client.get("/api/reports/revenue").status_code == 200

    co_owner_permissions = set(get_effective_permissions(db, 1, "co_owner"))
    assert PERMISSION_CASH_APPROVE_DIFFERENCE in co_owner_permissions
    assert PERMISSION_CASH_CUSTODY_RECEIVE in co_owner_permissions


def test_housekeeping_cleaning_transition_never_reallocates(role_client, monkeypatch):
    client, db, auth, room, _guest, _category = role_client
    auth["role"] = "housekeeping"
    allocation_called = False

    def fail_if_called(*_args, **_kwargs):
        nonlocal allocation_called
        allocation_called = True
        raise AssertionError("housekeeping cleaning status must not invoke allocation")

    monkeypatch.setattr(rooms, "run_persisted_allocation", fail_if_called)
    permissions = set(get_effective_permissions(db, 1, "housekeeping"))
    assert PERMISSION_ROOM_CLEANING_STATUS in permissions

    cleaning = client.patch(
        f"/api/rooms/{room.id}/cleaning-status",
        json={"status": "in_progress"},
    )
    assert cleaning.status_code == 200, cleaning.text
    assert cleaning.json()["room"]["status"] == "available"
    assert cleaning.json()["room"]["housekeeping_status"] == "in_progress"
    assert cleaning.json()["reallocation"] is None
    assert allocation_called is False

    db.refresh(room)
    clean = client.patch(
        f"/api/rooms/{room.id}/cleaning-status",
        json={"status": "clean"},
    )
    assert clean.status_code == 200, clean.text
    assert clean.json()["room"]["status"] == "available"
    assert clean.json()["room"]["housekeeping_status"] == "clean"

    invalid = client.patch(
        f"/api/rooms/{room.id}/cleaning-status",
        json={"status": "maintenance"},
    )
    assert invalid.status_code == 422


def test_housekeeping_status_can_change_without_changing_active_room_availability(role_client):
    client, db, auth, room, guest, category = role_client
    auth["role"] = "housekeeping"
    today = date.today()
    room.status = RoomStatusEnum.CLEANING
    room.housekeeping_status = RoomHousekeepingStatusEnum.IN_PROGRESS
    db.add(
        Reservation(
            hotel_id=1,
            guest_id=guest.id,
            category_id=category.id,
            room_id=room.id,
            confirmation_code="HK-ACTIVE",
            check_in_date=today,
            check_out_date=today + timedelta(days=1),
            status=ReservationStatusEnum.PENDING,
            total_amount=100,
            num_adults=1,
        )
    )
    db.add(
        Reservation(
            hotel_id=1,
            guest_id=guest.id,
            category_id=category.id,
            room_id=room.id,
            confirmation_code="HK-FUTURE",
            check_in_date=today + timedelta(days=3),
            check_out_date=today + timedelta(days=5),
            status=ReservationStatusEnum.PENDING,
            total_amount=100,
            num_adults=1,
        )
    )
    db.commit()

    response = client.patch(
        f"/api/rooms/{room.id}/cleaning-status",
        json={"status": "clean"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["room"]["housekeeping_status"] == "clean"
    assert "HK-ACTIVE" not in response.text
    assert "HK-FUTURE" not in response.text
    db.refresh(room)
    assert room.status == RoomStatusEnum.CLEANING
    assert room.housekeeping_status == RoomHousekeepingStatusEnum.CLEAN

    # A housekeeper may record cleaning progress, but must not block or otherwise
    # change the operational room state: that path can reallocate active and
    # future reservations. Keep both the dedicated status endpoint and the
    # generic room update endpoint behind the manager lane.
    for path in (f"/api/rooms/{room.id}/status", f"/api/rooms/{room.id}"):
        denied = client.patch(path, json={"status": "maintenance"})
        assert denied.status_code == 403, denied.text

    db.refresh(room)
    assert room.status == RoomStatusEnum.CLEANING
    reservations = (
        db.query(Reservation)
        .filter(Reservation.confirmation_code.in_(["HK-ACTIVE", "HK-FUTURE"]))
        .order_by(Reservation.confirmation_code)
        .all()
    )
    assert [reservation.confirmation_code for reservation in reservations] == ["HK-ACTIVE", "HK-FUTURE"]
    assert all(reservation.room_id == room.id for reservation in reservations)
    assert all(reservation.status == ReservationStatusEnum.PENDING for reservation in reservations)


def test_housekeeping_today_board_is_hotel_scoped_and_has_no_guest_or_free_text_data(role_client):
    client, db, auth, room, guest, category = role_client
    from app.services.timezones import local_today

    today = local_today(db.get(HotelConfiguration, 1).hotel_timezone)
    room.status = RoomStatusEnum.OCCUPIED
    db.add_all(
        [
            Reservation(
                hotel_id=1,
                guest_id=guest.id,
                category_id=category.id,
                room_id=room.id,
                confirmation_code="PRIVATE-ARRIVAL-CODE",
                check_in_date=today,
                check_out_date=today + timedelta(days=1),
                status=ReservationStatusEnum.PENDING,
                total_amount=100,
                num_adults=1,
            ),
            Reservation(
                hotel_id=1,
                guest_id=guest.id,
                category_id=category.id,
                room_id=room.id,
                confirmation_code="PRIVATE-DEPARTURE-CODE",
                check_in_date=today - timedelta(days=1),
                check_out_date=today,
                status=ReservationStatusEnum.CHECKED_IN,
                total_amount=100,
                num_adults=1,
            ),
            RoomBlock(
                hotel_id=1,
                room_id=room.id,
                reason_code=RoomBlockReasonEnum.MAINTENANCE,
                reason_note="PRIVATE maintenance note",
                starts_at=today,
                ends_at=today + timedelta(days=1),
            ),
        ]
    )
    db.commit()

    auth["role"] = "housekeeping"
    permissions = set(get_effective_permissions(db, 1, "housekeeping"))
    assert PERMISSION_HOUSEKEEPING_BOARD_VIEW in permissions
    response = client.get("/api/rooms/housekeeping-board")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["date"] == today.isoformat()
    assert set(payload) == {"date", "rooms"}
    room_item = next(item for item in payload["rooms"] if item["room_id"] == room.id)
    assert set(room_item) == {
        "room_id",
        "room_number",
        "floor",
        "category_name",
        "operational_status",
        "housekeeping_status",
        "has_arrival_today",
        "has_departure_today",
        "maintenance_blocked",
    }
    assert room_item["operational_status"] == "occupied"
    assert room_item["has_arrival_today"] is True
    assert room_item["has_departure_today"] is True
    assert room_item["maintenance_blocked"] is True
    assert "PRIVATE-ARRIVAL-CODE" not in response.text
    assert "PRIVATE-DEPARTURE-CODE" not in response.text
    assert "PRIVATE maintenance note" not in response.text
    assert guest.first_name not in response.text

    auth["role"] = "receptionist"
    denied = client.get("/api/rooms/housekeeping-board")
    assert denied.status_code == 403


SECTION_VIEW_PERMISSION_ROLE_CONTRACTS = (
    (PERMISSION_HOUSEKEEPING_BOARD_VIEW, {"owner", "co_owner", "manager", "housekeeping"}),
    ("analytics:view", {"owner", "co_owner"}),
    ("analytics:advanced:view", {"owner", "co_owner"}),
    ("analytics:ai:view", {"owner", "co_owner"}),
    ("dashboard:view", {"owner", "co_owner", "manager", "receptionist"}),
    # Product decision: cleaning staff get no guest or reservation data by
    # default. This is intentionally not derived from frontend routes; an
    # owner may explicitly grant occupancy:view for a particular hotel.
    (PERMISSION_OCCUPANCY_VIEW, {"owner", "co_owner", "manager", "receptionist"}),
    ("waitlist:view", {"owner", "co_owner", "manager", "receptionist"}),
    ("waitlist:manage", {"owner", "co_owner", "manager", "receptionist"}),
    ("cash:view", {"owner", "co_owner", "manager", "receptionist"}),
    (PERMISSION_OPERATIONS_AUDIT_VIEW, {"owner", "co_owner"}),
    ("company:view", {"owner", "co_owner", "manager"}),
    ("settings:users:view", {"owner", "co_owner"}),
    ("settings:users:manage", {"owner", "co_owner"}),
    ("settings:integrations:view", {"owner", "co_owner"}),
    ("settings:integrations:manage", {"owner", "co_owner"}),
    ("settings:subscription:view", {"owner", "co_owner"}),
    ("settings:security:view", {"owner", "co_owner"}),
    ("settings:notifications:view", {"owner", "co_owner", "manager", "receptionist"}),
    ("settings:assistant:view", {"owner", "co_owner", "manager"}),
    ("settings:tests:view", {"owner", "co_owner"}),
)


def test_new_section_permissions_match_current_frontend_role_gates_exactly():
    for permission_code, expected_roles in SECTION_VIEW_PERMISSION_ROLE_CONTRACTS:
        default_roles = {
            role for role in ROLE_CODES if DEFAULT_MATRIX[role].get(permission_code, False)
        }
        assert default_roles == expected_roles, permission_code


def test_payment_proof_permissions_keep_read_and_review_separate():
    assert DEFAULT_MATRIX["owner"][PERMISSION_PAYMENT_PROOF_VIEW] is True
    assert DEFAULT_MATRIX["owner"][PERMISSION_PAYMENT_PROOF_REVIEW] is True
    assert DEFAULT_MATRIX["co_owner"][PERMISSION_PAYMENT_PROOF_VIEW] is True
    assert DEFAULT_MATRIX["co_owner"][PERMISSION_PAYMENT_PROOF_REVIEW] is True
    assert DEFAULT_MATRIX["manager"][PERMISSION_PAYMENT_PROOF_VIEW] is True
    assert DEFAULT_MATRIX["manager"][PERMISSION_PAYMENT_PROOF_REVIEW] is True
    assert DEFAULT_MATRIX["manager"][PERMISSION_REPORTS_FINANCIAL_VIEW] is False
    assert DEFAULT_MATRIX["receptionist"][PERMISSION_PAYMENT_PROOF_VIEW] is False
    assert DEFAULT_MATRIX["receptionist"][PERMISSION_PAYMENT_PROOF_REVIEW] is False


def test_prior_cash_receipt_permission_is_limited_to_management_by_default():
    assert DEFAULT_MATRIX["owner"][PERMISSION_CASH_RECORD_PRIOR_RECEIPT] is True
    assert DEFAULT_MATRIX["co_owner"][PERMISSION_CASH_RECORD_PRIOR_RECEIPT] is True
    assert DEFAULT_MATRIX["manager"][PERMISSION_CASH_RECORD_PRIOR_RECEIPT] is True
    assert DEFAULT_MATRIX["receptionist"][PERMISSION_CASH_RECORD_PRIOR_RECEIPT] is False
    assert DEFAULT_MATRIX["housekeeping"][PERMISSION_CASH_RECORD_PRIOR_RECEIPT] is False
