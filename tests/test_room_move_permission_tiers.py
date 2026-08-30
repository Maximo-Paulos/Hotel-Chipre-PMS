from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.dependencies.auth import AuthContext, get_auth_context
from app.main import app as fastapi_app
from app.models.guest import Guest
from app.models.hotel_config import HotelConfiguration
from app.models.permission import HotelPermissionOverride
from app.models.reservation import Reservation, ReservationSourceEnum, ReservationStatusEnum
from app.models.room import Room, RoomCategory, RoomStatusEnum
from app.models.user import User
from app.services.permission_service import (
    DEFAULT_MATRIX,
    PERMISSION_RESERVATION_MOVE,
    PERMISSION_RESERVATION_MOVE_CAPACITY,
    PERMISSION_RESERVATION_MOVE_CATEGORY,
    seed_default_permissions,
)
from app.services.reservation_operations_service import required_room_move_permission


@pytest.fixture
def room_move_api_client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    role_state = {"role": "manager"}

    db.add_all(
        [
            HotelConfiguration(id=1, subscription_active=True),
            User(id=10, email="room-move-tiers@test.com", password_hash="test", is_active=True, is_verified=True),
        ]
    )
    db.commit()

    def override_get_db():
        try:
            yield db
        finally:
            pass

    def override_auth():
        return AuthContext(
            hotel_id=1,
            user_id=10,
            user_email=f"{role_state['role']}@test.com",
            user_role=role_state["role"],
            is_verified=True,
            permissions=set(),
        )

    fastapi_app.dependency_overrides[get_db] = override_get_db
    fastapi_app.dependency_overrides[get_auth_context] = override_auth
    try:
        yield TestClient(fastapi_app), db, role_state
    finally:
        fastapi_app.dependency_overrides.clear()
        db.close()
        engine.dispose()


def _seed_move_shapes(db: Session, *, guests: int = 1):
    current_category = RoomCategory(
        hotel_id=1,
        name="Tier Standard",
        code="TIER_STD",
        base_price_per_night=100,
        max_occupancy=2,
    )
    same_capacity_category = RoomCategory(
        hotel_id=1,
        name="Tier Superior",
        code="TIER_SUP",
        base_price_per_night=120,
        max_occupancy=2,
    )
    different_capacity_category = RoomCategory(
        hotel_id=1,
        name="Tier Family",
        code="TIER_FAM",
        base_price_per_night=180,
        max_occupancy=4,
    )
    db.add_all([current_category, same_capacity_category, different_capacity_category])
    db.flush()

    rooms = {
        "same": Room(hotel_id=1, room_number="T101", floor=1, category=current_category, status=RoomStatusEnum.AVAILABLE),
        "same_category": Room(hotel_id=1, room_number="T102", floor=1, category=current_category, status=RoomStatusEnum.AVAILABLE),
        "same_capacity": Room(hotel_id=1, room_number="T201", floor=2, category=same_capacity_category, status=RoomStatusEnum.AVAILABLE),
        "different_capacity": Room(hotel_id=1, room_number="T301", floor=3, category=different_capacity_category, status=RoomStatusEnum.AVAILABLE),
    }
    guest = Guest(hotel_id=1, first_name="Tier", last_name="Guest")
    db.add_all([*rooms.values(), guest])
    db.flush()
    reservation = Reservation(
        hotel_id=1,
        confirmation_code="TIER-MOVE-1",
        guest_id=guest.id,
        room_id=rooms["same"].id,
        category_id=current_category.id,
        check_in_date=date(2027, 8, 1),
        check_out_date=date(2027, 8, 3),
        total_amount=200,
        subtotal_amount=200,
        net_amount=200,
        amount_paid=0,
        deposit_amount=0,
        currency_code="ARS",
        status=ReservationStatusEnum.PENDING,
        source=ReservationSourceEnum.DIRECT,
        num_adults=guests,
        num_children=0,
    )
    db.add(reservation)
    db.commit()
    return reservation, rooms, current_category, same_capacity_category, different_capacity_category


def _move(client: TestClient, reservation: Reservation, destination: Room):
    return client.post(
        f"/api/reservations/{reservation.id}/room-move",
        json={"to_room_id": destination.id, "reason_code": "guest_request"},
    )


def test_room_move_tier_classifier_uses_category_identity_then_capacity():
    current = RoomCategory(id=1, hotel_id=1, name="Current", code="CUR", base_price_per_night=100, max_occupancy=2)
    same_category = RoomCategory(id=1, hotel_id=1, name="Same", code="SAME", base_price_per_night=100, max_occupancy=2)
    same_capacity = RoomCategory(id=2, hotel_id=1, name="Equivalent", code="EQ", base_price_per_night=120, max_occupancy=2)
    different_capacity = RoomCategory(id=3, hotel_id=1, name="Family", code="FAM", base_price_per_night=180, max_occupancy=4)

    assert required_room_move_permission(current, same_category) == PERMISSION_RESERVATION_MOVE
    assert required_room_move_permission(current, same_capacity) == PERMISSION_RESERVATION_MOVE_CATEGORY
    assert required_room_move_permission(current, different_capacity) == PERMISSION_RESERVATION_MOVE_CAPACITY


@pytest.mark.parametrize(
    ("destination_key", "expected_status", "required_text"),
    [
        ("same_category", 200, None),
        ("same_capacity", 403, "Cambiar de categoría"),
        ("different_capacity", 403, "Cambiar de capacidad"),
    ],
)
def test_receptionist_is_limited_to_same_category_moves(
    room_move_api_client, destination_key, expected_status, required_text, monkeypatch
):
    client, db, role_state = room_move_api_client
    role_state["role"] = "receptionist"
    monkeypatch.setattr("app.api.reservations._trigger_reoptimization_bg", lambda **_kwargs: None)
    reservation, rooms, *_ = _seed_move_shapes(db)

    response = _move(client, reservation, rooms[destination_key])

    assert response.status_code == expected_status, response.text
    if required_text is not None:
        assert required_text in response.json()["detail"]
        db.refresh(reservation)
        assert reservation.room_id == rooms["same"].id


@pytest.mark.parametrize("destination_key", ("same_category", "same_capacity", "different_capacity"))
def test_manager_can_move_each_shape(room_move_api_client, destination_key, monkeypatch):
    client, db, role_state = room_move_api_client
    role_state["role"] = "manager"
    monkeypatch.setattr("app.api.reservations._trigger_reoptimization_bg", lambda **_kwargs: None)
    reservation, rooms, *_ = _seed_move_shapes(db)

    response = _move(client, reservation, rooms[destination_key])

    assert response.status_code == 200, response.text
    db.refresh(reservation)
    assert reservation.room_id == rooms[destination_key].id


@pytest.mark.parametrize("role", ("owner", "co_owner", "manager"))
@pytest.mark.parametrize("destination_key", ("same_category", "same_capacity", "different_capacity"))
def test_existing_wide_roles_still_move_anywhere(room_move_api_client, role, destination_key, monkeypatch):
    client, db, role_state = room_move_api_client
    role_state["role"] = role
    monkeypatch.setattr("app.api.reservations._trigger_reoptimization_bg", lambda **_kwargs: None)
    reservation, rooms, *_ = _seed_move_shapes(db)

    response = _move(client, reservation, rooms[destination_key])

    assert response.status_code == 200, response.text


@pytest.mark.parametrize("destination_key", ("same_category", "same_capacity", "different_capacity"))
def test_capacity_tier_alone_includes_each_narrower_tier(room_move_api_client, destination_key, monkeypatch):
    client, db, role_state = room_move_api_client
    role_state["role"] = "manager"
    monkeypatch.setattr("app.api.reservations._trigger_reoptimization_bg", lambda **_kwargs: None)
    reservation, rooms, *_ = _seed_move_shapes(db)

    seed_default_permissions(db)
    db.add_all(
        [
            HotelPermissionOverride(hotel_id=1, role="manager", permission_code=PERMISSION_RESERVATION_MOVE, allowed=False),
            HotelPermissionOverride(hotel_id=1, role="manager", permission_code=PERMISSION_RESERVATION_MOVE_CATEGORY, allowed=False),
        ]
    )
    db.commit()

    response = _move(client, reservation, rooms[destination_key])

    assert response.status_code == 200, response.text


def test_manager_capacity_permission_does_not_bypass_occupancy_validation(room_move_api_client, monkeypatch):
    client, db, role_state = room_move_api_client
    role_state["role"] = "manager"
    monkeypatch.setattr("app.api.reservations._trigger_reoptimization_bg", lambda **_kwargs: None)
    reservation, rooms, _current, _same_capacity, different_capacity = _seed_move_shapes(db, guests=4)
    too_small_category = RoomCategory(
        hotel_id=1,
        name="Tier Small",
        code="TIER_SMALL",
        base_price_per_night=80,
        max_occupancy=2,
    )
    db.add(too_small_category)
    db.flush()
    too_small_room = Room(
        hotel_id=1,
        room_number="T401",
        floor=4,
        category=too_small_category,
        status=RoomStatusEnum.AVAILABLE,
    )
    db.add(too_small_room)
    db.commit()

    # Move the reservation to the capacity-four category first, then attempt
    # the capacity-two destination. The manager holds move_capacity by default.
    first_move = _move(client, reservation, rooms["different_capacity"])
    assert first_move.status_code == 200, first_move.text

    response = _move(client, reservation, too_small_room)

    assert response.status_code == 400, response.text
    assert "hasta 2" in response.json()["detail"]
    db.refresh(reservation)
    assert reservation.category_id == different_capacity.id


def test_room_move_default_matrix_matches_the_three_tier_contract():
    expected = {
        "owner": (True, True, True),
        "co_owner": (True, True, True),
        "manager": (True, True, True),
        "receptionist": (True, False, False),
        "housekeeping": (False, False, False),
    }

    for role, tiers in expected.items():
        assert (
            DEFAULT_MATRIX[role][PERMISSION_RESERVATION_MOVE],
            DEFAULT_MATRIX[role][PERMISSION_RESERVATION_MOVE_CATEGORY],
            DEFAULT_MATRIX[role][PERMISSION_RESERVATION_MOVE_CAPACITY],
        ) == tiers
