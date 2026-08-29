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
from app.database import Base, get_db
from app.dependencies.auth import AuthContext, get_auth_context
from app.models.guest import Guest
from app.models.hotel_config import HotelConfiguration
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.room import Room, RoomCategory, RoomStatusEnum
from app.services.permission_service import (
    DEFAULT_MATRIX,
    PERMISSION_CASH_APPROVE_DIFFERENCE,
    PERMISSION_CASH_OPERATE,
    PERMISSION_GUEST_CREATE,
    PERMISSION_GUEST_EDIT,
    PERMISSION_GUEST_TAGS,
    PERMISSION_GUEST_VIEW,
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


def test_housekeeping_cannot_access_guest_or_reservation_pii(role_client):
    client, _db, auth, _room, guest, _category = role_client
    auth["role"] = "housekeeping"

    assert client.get("/api/guests/").status_code == 403
    assert client.get(f"/api/guests/{guest.id}").status_code == 403
    assert client.get("/api/reservations/").status_code == 403
    assert client.get("/api/reservations/actions/pending").status_code == 403
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
    assert PERMISSION_CASH_OPERATE not in manager_permissions
    assert PERMISSION_CASH_APPROVE_DIFFERENCE not in manager_permissions
    assert client.get("/api/reports/occupancy").status_code == 200
    assert client.get("/api/reports/daily").status_code == 403
    assert client.get("/api/reports/revenue").status_code == 403

    auth["role"] = "owner"
    assert client.get("/api/reports/daily").status_code == 200
    assert client.get("/api/reports/revenue").status_code == 200


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
        json={"status": "cleaning"},
    )
    assert cleaning.status_code == 200, cleaning.text
    assert cleaning.json()["room"]["status"] == "cleaning"
    assert cleaning.json()["reallocation"] is None
    assert allocation_called is False

    db.refresh(room)
    available = client.patch(
        f"/api/rooms/{room.id}/cleaning-status",
        json={"status": "available"},
    )
    assert available.status_code == 200, available.text
    assert available.json()["room"]["status"] == "available"

    invalid = client.patch(
        f"/api/rooms/{room.id}/cleaning-status",
        json={"status": "maintenance"},
    )
    assert invalid.status_code == 422


def test_housekeeping_cleaning_transition_rejects_active_reservation(role_client):
    client, db, auth, room, guest, category = role_client
    auth["role"] = "housekeeping"
    today = date.today()
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
    db.commit()

    response = client.patch(
        f"/api/rooms/{room.id}/cleaning-status",
        json={"status": "cleaning"},
    )

    assert response.status_code == 409
    db.refresh(room)
    assert room.status == RoomStatusEnum.AVAILABLE


SECTION_VIEW_PERMISSION_ROLE_CONTRACTS = (
    ("analytics:view", {"owner", "co_owner"}),
    ("analytics:advanced:view", {"owner", "co_owner"}),
    ("analytics:ai:view", {"owner", "co_owner"}),
    ("dashboard:view", {"owner", "co_owner", "manager", "receptionist"}),
    ("occupancy:view", {"owner", "co_owner", "manager", "receptionist"}),
    ("waitlist:view", {"owner", "co_owner", "manager", "receptionist"}),
    ("waitlist:manage", {"owner", "co_owner", "manager", "receptionist"}),
    ("cash:view", {"owner", "co_owner", "receptionist"}),
    ("company:view", {"owner", "co_owner"}),
    ("settings:users:view", {"owner", "co_owner"}),
    ("settings:users:manage", {"owner", "co_owner"}),
    ("settings:integrations:view", {"owner", "co_owner"}),
    ("settings:integrations:manage", {"owner", "co_owner"}),
    ("settings:subscription:view", {"owner", "co_owner"}),
    ("settings:security:view", {"owner", "co_owner"}),
    ("settings:sessions:view", {"owner", "co_owner"}),
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
