# -*- coding: utf-8 -*-
"""
Multi-hotel isolation contracts.

These tests separate the parts that are already isolated from the parts that
still need backend hardening. The passing tests lock the current hotel scoping
for lists and details; the xfail tests document the security gaps we still need
to close in auth and legacy endpoints.
"""
from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app as fastapi_app
from app.database import Base, get_db
from app.dependencies.auth import AuthContext, get_auth_context
from app.models.guest import Guest
from app.models.hotel_config import HotelConfiguration
from app.models.hotel_membership import HotelMembership
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.room import Room, RoomCategory, RoomStatusEnum
from app.models.user import User
from app.services.security import create_access_token, hash_password


def _get_db_override_target():
    return get_db


@pytest.fixture
def isolated_client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    def override_get_db():
        try:
            yield db
        finally:
            pass

    fastapi_app.dependency_overrides[_get_db_override_target()] = override_get_db
    client = TestClient(fastapi_app)
    try:
        yield client, db
    finally:
        fastapi_app.dependency_overrides.clear()
        db.close()
        engine.dispose()


def _seed_hotel(db, hotel_id: int, owner_email: str) -> HotelConfiguration:
    hotel = HotelConfiguration(id=hotel_id, owner_email=owner_email, subscription_active=True)
    db.add(hotel)
    db.flush()
    return hotel


def _seed_membership(db, hotel_id: int, user_id: int, role: str = "owner") -> HotelMembership:
    membership = HotelMembership(hotel_id=hotel_id, user_id=user_id, role=role, status="active")
    db.add(membership)
    db.flush()
    return membership


def _seed_hotel_payload(db, hotel_id: int, code_suffix: str, room_number: str, confirmation_code: str):
    hotel_email = f"owner{hotel_id}@test.com"
    hotel = _seed_hotel(db, hotel_id, hotel_email)
    category = RoomCategory(
        hotel_id=hotel.id,
        name=f"Category {code_suffix}",
        code=f"CAT_{code_suffix}",
        base_price_per_night=100.0 + hotel_id,
        max_occupancy=2,
    )
    db.add(category)
    db.flush()
    room = Room(
        hotel_id=hotel.id,
        room_number=room_number,
        floor=1,
        category_id=category.id,
        status=RoomStatusEnum.AVAILABLE,
    )
    guest = Guest(
        hotel_id=hotel.id,
        first_name=f"Guest{code_suffix}",
        last_name="PMS",
        email=f"guest{hotel_id}@test.com",
        terms_accepted=True,
    )
    db.add_all([room, guest])
    db.flush()
    reservation = Reservation(
        confirmation_code=confirmation_code,
        hotel_id=hotel.id,
        guest_id=guest.id,
        room_id=room.id,
        category_id=category.id,
        check_in_date=date(2026, 1, 1),
        check_out_date=date(2026, 1, 2),
        total_amount=100.0,
        amount_paid=0.0,
        deposit_amount=30.0,
        status=ReservationStatusEnum.PENDING,
    )
    db.add(reservation)
    db.flush()
    return {
        "hotel": hotel,
        "category": category,
        "room": room,
        "guest": guest,
        "reservation": reservation,
    }


def _set_auth_context_override(hotel_id: int, user_id: int, user_email: str, role: str = "owner"):
    def override_get_auth_context():
        return AuthContext(
            hotel_id=hotel_id,
            user_id=user_id,
            user_email=user_email,
            user_role=role,
            is_verified=True,
            permissions=set(),
        )

    fastapi_app.dependency_overrides[get_auth_context] = override_get_auth_context


def test_rooms_and_reservations_are_scoped_to_active_hotel(isolated_client):
    client, db = isolated_client

    user = User(email="owner@test.com", password_hash=hash_password("pass"), role="owner", is_verified=True)
    db.add(user)
    db.flush()

    hotel1 = _seed_hotel_payload(db, 1, "H1", "101", "RES-H1")
    hotel2 = _seed_hotel_payload(db, 2, "H2", "201", "RES-H2")
    _seed_membership(db, hotel1["hotel"].id, user.id, "owner")
    _seed_membership(db, hotel2["hotel"].id, user.id, "owner")
    db.commit()

    _set_auth_context_override(hotel1["hotel"].id, user.id, user.email, "owner")
    resp_rooms_h1 = client.get("/api/rooms/")
    assert resp_rooms_h1.status_code == 200, resp_rooms_h1.text
    assert [room["room_number"] for room in resp_rooms_h1.json()] == ["101"]

    resp_res_h1 = client.get("/api/reservations/")
    assert resp_res_h1.status_code == 200, resp_res_h1.text
    assert [res["confirmation_code"] for res in resp_res_h1.json()] == ["RES-H1"]

    _set_auth_context_override(hotel2["hotel"].id, user.id, user.email, "owner")
    resp_rooms_h2 = client.get("/api/rooms/")
    assert resp_rooms_h2.status_code == 200, resp_rooms_h2.text
    assert [room["room_number"] for room in resp_rooms_h2.json()] == ["201"]

    resp_res_h2 = client.get("/api/reservations/")
    assert resp_res_h2.status_code == 200, resp_res_h2.text
    assert [res["confirmation_code"] for res in resp_res_h2.json()] == ["RES-H2"]


def test_foreign_room_and_reservation_details_are_hidden(isolated_client):
    client, db = isolated_client

    user = User(email="owner@test.com", password_hash=hash_password("pass"), role="owner", is_verified=True)
    db.add(user)
    db.flush()

    hotel1 = _seed_hotel_payload(db, 1, "H1", "101", "RES-H1")
    hotel2 = _seed_hotel_payload(db, 2, "H2", "201", "RES-H2")
    _seed_membership(db, hotel1["hotel"].id, user.id, "owner")
    _seed_membership(db, hotel2["hotel"].id, user.id, "owner")
    db.commit()

    _set_auth_context_override(hotel1["hotel"].id, user.id, user.email, "owner")

    room_resp = client.get(f"/api/rooms/{hotel2['room'].id}")
    assert room_resp.status_code == 404, room_resp.text

    reservation_resp = client.get(f"/api/reservations/{hotel2['reservation'].id}")
    assert reservation_resp.status_code == 404, reservation_resp.text


def test_x_hotel_id_spoofing_should_not_switch_hotel(isolated_client):
    client, db = isolated_client

    user = User(email="owner@test.com", password_hash=hash_password("pass"), role="owner", is_verified=True)
    db.add(user)
    db.flush()

    hotel1 = _seed_hotel_payload(db, 1, "H1", "101", "RES-H1")
    hotel2 = _seed_hotel_payload(db, 2, "H2", "201", "RES-H2")
    _seed_membership(db, hotel1["hotel"].id, user.id, "owner")
    db.commit()

    token = create_access_token(
        user.id,
        extra={
            "email": user.email,
            "role": "owner",
            "hotel_id": hotel1["hotel"].id,
            "hotel_ids": [hotel1["hotel"].id],
        },
    )

    resp = client.get(
        "/api/rooms/",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Hotel-Id": str(hotel2["hotel"].id),
            "X-User-Id": str(user.id),
        },
    )

    assert resp.status_code in {401, 403, 404}


def test_legacy_connections_endpoint_should_not_be_exposed(isolated_client):
    client, db = isolated_client

    payload = {"credentials": {"token": "abc"}, "settings": {"hotel_id": 1}}
    resp = client.post("/api/connections/mercadopago/connect", json=payload)
    assert resp.status_code in {404, 410}


def test_housekeeping_summary_should_be_hotel_scoped(isolated_client):
    client, db = isolated_client

    user = User(email="owner@test.com", password_hash=hash_password("pass"), role="owner", is_verified=True)
    db.add(user)
    db.flush()

    hotel1 = _seed_hotel_payload(db, 1, "H1", "101", "RES-H1")
    hotel2 = _seed_hotel_payload(db, 2, "H2", "201", "RES-H2")
    _seed_membership(db, hotel1["hotel"].id, user.id, "owner")
    _seed_membership(db, hotel2["hotel"].id, user.id, "owner")
    db.commit()

    _set_auth_context_override(hotel1["hotel"].id, user.id, user.email, "owner")
    resp = client.get("/api/rooms/housekeeping/summary")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == 1
    assert [room["room_number"] for room in body["rooms"]] == ["101"]


def test_checkin_guest_validation_should_not_leak_foreign_guest(isolated_client):
    client, db = isolated_client

    user = User(email="owner@test.com", password_hash=hash_password("pass"), role="owner", is_verified=True)
    db.add(user)
    db.flush()

    hotel1 = _seed_hotel_payload(db, 1, "H1", "101", "RES-H1")
    hotel2 = _seed_hotel_payload(db, 2, "H2", "201", "RES-H2")
    _seed_membership(db, hotel1["hotel"].id, user.id, "owner")
    _seed_membership(db, hotel2["hotel"].id, user.id, "owner")
    db.commit()

    _set_auth_context_override(hotel1["hotel"].id, user.id, user.email, "owner")
    resp = client.get(f"/api/checkin/validate/{hotel2['guest'].id}")
    assert resp.status_code == 404, resp.text
