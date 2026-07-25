from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.dependencies.auth import AuthContext, get_auth_context
from app.main import app as fastapi_app
from app.models.guest import Guest
from app.models.hotel_config import HotelConfiguration
from app.models.reservation import Reservation, ReservationSourceEnum, ReservationStatusEnum
from app.models.room import Room, RoomCategory, RoomStatusEnum


@pytest.fixture
def reservation_api_client():
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

    def override_auth():
        return AuthContext(
            hotel_id=1,
            user_id=1,
            user_email="owner@test.com",
            user_role="owner",
            is_verified=True,
            permissions=set(),
        )

    fastapi_app.dependency_overrides[get_db] = override_get_db
    fastapi_app.dependency_overrides[get_auth_context] = override_auth
    client = TestClient(fastapi_app)
    try:
        yield client, db
    finally:
        fastapi_app.dependency_overrides.clear()
        db.close()
        engine.dispose()


def _seed_reservation_prerequisites(db):
    hotel = HotelConfiguration(id=1, owner_email="owner@test.com", subscription_active=True)
    guest = Guest(first_name="Mobility", last_name="Guest", hotel_id=1)
    category = RoomCategory(
        hotel_id=1,
        name="Standard Mobility",
        code="STD_MOB",
        base_price_per_night=100.0,
        max_occupancy=2,
    )
    room_a = Room(
        hotel_id=1,
        room_number="M101",
        floor=1,
        category=category,
        status=RoomStatusEnum.AVAILABLE,
    )
    room_b = Room(
        hotel_id=1,
        room_number="M102",
        floor=1,
        category=category,
        status=RoomStatusEnum.AVAILABLE,
    )
    db.add_all([hotel, guest, category, room_a, room_b])
    db.commit()
    return guest, category, room_a, room_b


def test_create_reservation_persists_mobility_restriction(reservation_api_client, monkeypatch):
    client, db = reservation_api_client
    calls = []
    monkeypatch.setattr("app.api.reservations._trigger_reoptimization_bg", lambda **kwargs: calls.append(kwargs))
    guest, category, room, _ = _seed_reservation_prerequisites(db)

    quote_response = client.get(
        "/api/bookings/price-quote",
        params={
            "category_id": category.id,
            "check_in_date": "2027-04-01",
            "check_out_date": "2027-04-03",
            "num_adults": 1,
            "num_children": 0,
        },
    )
    assert quote_response.status_code == 200, quote_response.text

    response = client.post(
        "/api/reservations/",
        json={
            "guest_id": guest.id,
            "category_id": category.id,
            "room_id": room.id,
            "check_in_date": "2027-04-01",
            "check_out_date": "2027-04-03",
            "num_adults": 1,
            "mobility_restriction": True,
            "quote_token": quote_response.json()["quote_token"],
        },
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["mobility_restriction"] is True
    saved = db.get(Reservation, body["id"])
    assert saved.mobility_restriction is True


def test_update_mobility_restriction_triggers_reoptimization(reservation_api_client, monkeypatch):
    client, db = reservation_api_client
    calls = []
    monkeypatch.setattr("app.api.reservations._trigger_reoptimization_bg", lambda **kwargs: calls.append(kwargs))
    guest, category, room, _ = _seed_reservation_prerequisites(db)
    reservation = Reservation(
        confirmation_code="MOB-UPD-1",
        hotel_id=1,
        guest_id=guest.id,
        room_id=room.id,
        category_id=category.id,
        check_in_date=date(2027, 4, 10),
        check_out_date=date(2027, 4, 12),
        total_amount=200.0,
        subtotal_amount=200.0,
        net_amount=200.0,
        amount_paid=0.0,
        deposit_amount=60.0,
        currency_code="ARS",
        status=ReservationStatusEnum.PENDING,
        source=ReservationSourceEnum.DIRECT,
        num_adults=1,
        num_children=0,
        mobility_restriction=True,
    )
    db.add(reservation)
    db.commit()

    response = client.patch(f"/api/reservations/{reservation.id}", json={"mobility_restriction": False})

    assert response.status_code == 200, response.text
    assert response.json()["mobility_restriction"] is False
    db.refresh(reservation)
    assert reservation.mobility_restriction is False
    assert calls == [{"hotel_id": 1, "trigger_type": "reservation_update"}]


def test_patch_reservation_silently_ignores_unsupported_category_and_status_fields(
    reservation_api_client, monkeypatch
):
    """Fase 3 (QA reservas): PATCH /api/reservations/{id} only understands
    room_id/check_in_date/check_out_date/num_adults/num_children/notes/
    mobility_restriction/client_version (see ReservationUpdate). category_id
    and status are NOT part of that schema, so FastAPI/Pydantic drop them
    silently instead of raising a 422 -- the request still returns 200 with
    an unchanged reservation.

    This is the backend contract driving the frontend fix in
    ReservationsPage.tsx: the edit form must not offer an interactive
    "Categoria"/"Estado" control, since submitting a change there produces a
    misleading 200 "Reserva actualizada" without actually changing anything.
    Real status transitions must go through their dedicated, validated
    endpoints/buttons (cancel, check-in, check-out, no-show).
    """
    client, db = reservation_api_client
    monkeypatch.setattr("app.api.reservations._trigger_reoptimization_bg", lambda **kwargs: None)
    guest, category, room, _ = _seed_reservation_prerequisites(db)
    other_category = RoomCategory(
        hotel_id=1,
        name="Deluxe Mobility",
        code="DLX_MOB",
        base_price_per_night=500.0,
        max_occupancy=4,
    )
    db.add(other_category)
    db.commit()

    reservation = Reservation(
        confirmation_code="MOB-IGNORE-1",
        hotel_id=1,
        guest_id=guest.id,
        room_id=room.id,
        category_id=category.id,
        check_in_date=date(2027, 6, 1),
        check_out_date=date(2027, 6, 3),
        total_amount=200.0,
        subtotal_amount=200.0,
        net_amount=200.0,
        amount_paid=0.0,
        deposit_amount=60.0,
        currency_code="ARS",
        status=ReservationStatusEnum.PENDING,
        source=ReservationSourceEnum.DIRECT,
        num_adults=1,
        num_children=0,
    )
    db.add(reservation)
    db.commit()

    response = client.patch(
        f"/api/reservations/{reservation.id}",
        json={"category_id": other_category.id, "status": "cancelled", "notes": "intento de cambio"},
    )

    assert response.status_code == 200, response.text
    db.refresh(reservation)
    assert reservation.category_id == category.id
    assert reservation.status == ReservationStatusEnum.PENDING
    assert reservation.notes == "intento de cambio"


def test_room_move_requires_reason_code_and_accepts_valid_reason(reservation_api_client, monkeypatch):
    client, db = reservation_api_client
    monkeypatch.setattr("app.api.reservations._trigger_reoptimization_bg", lambda **_kwargs: None)
    guest, category, room_a, room_b = _seed_reservation_prerequisites(db)
    reservation = Reservation(
        confirmation_code="MOVE-REASON-API",
        hotel_id=1,
        guest_id=guest.id,
        room_id=room_a.id,
        category_id=category.id,
        check_in_date=date(2027, 5, 1),
        check_out_date=date(2027, 5, 3),
        total_amount=200.0,
        subtotal_amount=200.0,
        net_amount=200.0,
        amount_paid=0.0,
        deposit_amount=60.0,
        currency_code="ARS",
        status=ReservationStatusEnum.PENDING,
        source=ReservationSourceEnum.DIRECT,
        num_adults=1,
        num_children=0,
    )
    db.add(reservation)
    db.commit()

    missing_reason = client.post(f"/api/reservations/{reservation.id}/room-move", json={"to_room_id": room_b.id})
    assert missing_reason.status_code == 422, missing_reason.text

    valid = client.post(
        f"/api/reservations/{reservation.id}/room-move",
        json={"to_room_id": room_b.id, "reason_code": "guest_request"},
    )
    assert valid.status_code == 200, valid.text
    db.refresh(reservation)
    assert reservation.room_id == room_b.id
