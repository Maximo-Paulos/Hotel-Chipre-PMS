"""Regression tests for tenant-scoped, per-role reservation visibility."""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.dependencies.auth import AuthContext, get_auth_context
from app.main import app as fastapi_app
from app.models.hotel_config import HotelConfiguration
from app.models.hotel_role_visibility_window import HotelRoleVisibilityWindow
from app.models.security_audit_log import SecurityAuditLog
from app.models.user import User
from app.schemas.permission import VisibilityWindowUpdate
from app.schemas.reservation import ReservationCreate
from app.services.permission_service import get_visibility_window, set_visibility_window
from app.services.reservation_service import (
    create_reservation,
    get_occupancy_grid,
    list_reservations,
    visible_reservations,
)


def _context(hotel_id: int = 1, role: str = "receptionist", user_id: int | None = None) -> AuthContext:
    return AuthContext(
        hotel_id=hotel_id,
        user_id=user_id,
        user_email=f"{role}@test.com",
        user_role=role,
        is_verified=True,
        permissions=set(),
    )


def _reserve(db, guest, room, check_in: date, check_out: date):
    reservation = create_reservation(
        db,
        ReservationCreate(
            guest_id=guest.id,
            category_id=room.category_id,
            room_id=room.id,
            check_in_date=check_in,
            check_out_date=check_out,
        ),
        hotel_id=1,
    )
    db.flush()
    return reservation


def _hotel_today(hotel_config: HotelConfiguration) -> date:
    return datetime.now(ZoneInfo(hotel_config.hotel_timezone)).date()


def test_visibility_window_filters_far_future_and_null_is_unlimited(
    db, sample_guest, sample_rooms, hotel_config
):
    today = _hotel_today(hotel_config)
    far_future = _reserve(db, sample_guest, sample_rooms[0], today + timedelta(days=10), today + timedelta(days=12))
    context = _context()

    set_visibility_window(db, 1, "receptionist", 24, 24, actor_user_id=None)
    assert far_future.id not in {r.id for r in visible_reservations(db, context).all()}
    assert far_future.id not in {
        r.id
        for r in list_reservations(db, hotel_id=1, context=context)
    }
    grid = get_occupancy_grid(
        db,
        hotel_id=1,
        date_from=today + timedelta(days=9),
        date_to=today + timedelta(days=13),
        context=context,
    )
    assert far_future.id not in {r["id"] for r in [*grid["reservations"], *grid["unassigned"]]}

    set_visibility_window(db, 1, "receptionist", None, None, actor_user_id=None)
    assert far_future.id in {r.id for r in visible_reservations(db, context).all()}


def test_in_house_guest_remains_visible_when_check_in_predates_window(
    db, sample_guest, sample_rooms, hotel_config
):
    today = _hotel_today(hotel_config)
    in_house = _reserve(db, sample_guest, sample_rooms[0], today - timedelta(days=10), today + timedelta(days=2))

    set_visibility_window(db, 1, "receptionist", 24, 24, actor_user_id=None)

    assert in_house.id in {
        r.id for r in visible_reservations(db, _context()).all()
    }


def test_visibility_window_isolated_by_hotel(db, hotel_config):
    db.add(HotelConfiguration(id=2, hotel_timezone="UTC", subscription_active=True))
    db.flush()
    set_visibility_window(db, 1, "receptionist", 24, 24, actor_user_id=None)
    set_visibility_window(db, 2, "receptionist", None, None, actor_user_id=None)

    hotel_one = get_visibility_window(db, 1, "receptionist")
    hotel_two = get_visibility_window(db, 2, "receptionist")

    assert hotel_one is not None and hotel_one.future_hours == 24
    assert hotel_two is not None and hotel_two.future_hours is None
    assert db.query(HotelRoleVisibilityWindow).filter_by(hotel_id=1).count() == 1
    assert db.query(HotelRoleVisibilityWindow).filter_by(hotel_id=2).count() == 1


def test_visibility_window_schema_accepts_only_supported_hours():
    assert VisibilityWindowUpdate(role="receptionist", past_hours=None, future_hours=168)
    with pytest.raises(ValueError):
        VisibilityWindowUpdate(role="receptionist", past_hours=13, future_hours=24)


@pytest.fixture
def visibility_api():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    db.add_all(
        [
            HotelConfiguration(id=1, subscription_active=True),
            HotelConfiguration(id=2, subscription_active=True),
            User(
                id=7,
                email="visibility-owner@test.com",
                password_hash="test-hash",
                is_active=True,
                is_verified=True,
            ),
        ]
    )
    db.commit()

    def override_get_db():
        yield db

    def override_auth():
        return _context(user_id=7, role="owner")

    fastapi_app.dependency_overrides[get_db] = override_get_db
    fastapi_app.dependency_overrides[get_auth_context] = override_auth
    try:
        yield TestClient(fastapi_app), db
    finally:
        fastapi_app.dependency_overrides.clear()
        db.close()
        engine.dispose()


def test_visibility_window_api_lists_all_roles_audits_and_rejects_invalid_value(visibility_api):
    client, db = visibility_api

    initial = client.get("/api/permissions/visibility-windows")
    assert initial.status_code == 200
    assert [row["role"] for row in initial.json()["windows"]] == [
        "owner",
        "co_owner",
        "manager",
        "receptionist",
        "housekeeping",
    ]
    assert all(row["past_hours"] is None for row in initial.json()["windows"])

    invalid = client.put(
        "/api/permissions/visibility-windows",
        json={"role": "receptionist", "past_hours": 13, "future_hours": 24},
    )
    assert invalid.status_code == 422

    updated = client.put(
        "/api/permissions/visibility-windows",
        json={"role": "receptionist", "past_hours": 24, "future_hours": None},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["past_hours"] == 24
    assert updated.json()["future_hours"] is None
    audit = (
        db.query(SecurityAuditLog)
        .filter(SecurityAuditLog.action == "permission.visibility_window.updated")
        .one()
    )
    assert audit.hotel_id == 1
    assert audit.user_id == 7
    assert audit.resource_id == "receptionist"

