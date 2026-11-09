"""PostgreSQL regressions for room moves that do not need a new price quote."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.database import get_db
from app.dependencies.auth import AuthContext, get_auth_context
from app.main import app as fastapi_app
from app.models.guest import Guest
from app.models.hotel_config import HotelConfiguration
from app.models.reservation import (
    Reservation,
    ReservationSourceEnum,
    ReservationStatusEnum,
)
from app.models.room import Room, RoomCategory, RoomStatusEnum
from app.models.user import User
from app.services import reservation_operations_service as operations
from app.services.reservation_operations_service import (
    ReservationOperationsError,
    move_reservation_room,
)
from app.services.reservation_service import ReservationError
from app.services.tenant_context import set_tenant_context, set_tenant_hotel_context


def _seed_room_move_case(pg_engine, *, different_destination_category: bool = False):
    session_factory = sessionmaker(bind=pg_engine, expire_on_commit=False)
    db = session_factory()
    suffix = uuid4().hex[:10].upper()
    hotel_id = 150_000_000 + uuid4().int % 20_000_000
    set_tenant_hotel_context(db, hotel_id)

    hotel = HotelConfiguration(
        id=hotel_id,
        hotel_name=f"Synthetic room move pricing {suffix}",
        deposit_policy_configured=False,
    )
    user = User(
        email=f"room-move-{suffix.lower()}@example.test",
        password_hash="synthetic-test-hash",
        role="manager",
        is_active=True,
        is_verified=True,
    )
    source_category = RoomCategory(
        hotel_id=hotel_id,
        name=f"Synthetic Doble {suffix}",
        code=f"D{suffix}",
        base_price_per_night=Decimal("60000.00"),
        max_occupancy=2,
    )
    destination_category = source_category
    db.add_all([hotel, source_category, user])
    db.flush()
    if different_destination_category:
        destination_category = RoomCategory(
            hotel_id=hotel_id,
            name=f"Synthetic Superior {suffix}",
            code=f"S{suffix}",
            base_price_per_night=Decimal("75000.00"),
            max_occupancy=2,
        )
        db.add(destination_category)
        db.flush()

    guest = Guest(hotel_id=hotel_id, first_name="Synthetic", last_name="Move")
    source_room = Room(
        hotel_id=hotel_id,
        room_number=f"A{suffix[:8]}",
        floor=1,
        category_id=source_category.id,
        status=RoomStatusEnum.AVAILABLE,
    )
    destination_room = Room(
        hotel_id=hotel_id,
        room_number=f"B{suffix[:8]}",
        floor=1,
        category_id=destination_category.id,
        status=RoomStatusEnum.AVAILABLE,
    )
    db.add_all([guest, source_room, destination_room])
    db.flush()

    reservation = Reservation(
        hotel_id=hotel_id,
        confirmation_code=f"MOVE-{suffix}",
        guest_id=guest.id,
        room_id=source_room.id,
        category_id=source_category.id,
        check_in_date=date(2026, 12, 30),
        check_out_date=date(2027, 1, 2),
        total_amount=Decimal("180000.00"),
        subtotal_amount=Decimal("180000.00"),
        net_amount=Decimal("180000.00"),
        amount_paid=Decimal("0.00"),
        currency_code="ARS",
        status=ReservationStatusEnum.PENDING,
        source=ReservationSourceEnum.DIRECT,
        num_adults=2,
        num_children=0,
    )
    db.add(reservation)
    db.commit()
    return db, hotel_id, reservation, source_room, destination_room, user.id


def test_postgres_room_move_api_same_category_keep_succeeds_without_deposit_policy(
    pg_engine,
    monkeypatch,
):
    db, hotel_id, reservation, source_room, destination_room, user_id = _seed_room_move_case(pg_engine)
    reservation_id = reservation.id
    source_category_id = source_room.category_id
    destination_room_id = destination_room.id
    session_factory = sessionmaker(bind=pg_engine, expire_on_commit=False)
    db.close()

    monkeypatch.setattr(operations, "_invalidate_availability_cache", lambda _hotel_id: None)
    monkeypatch.setattr(operations, "_touch_facts", lambda *_args, **_kwargs: None)
    from app.api import reservations as reservations_api

    monkeypatch.setattr(reservations_api, "_project_reservation_graph", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(reservations_api, "project_room_movement", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(reservations_api, "reservation_overlaps_default_horizon", lambda *_args, **_kwargs: False)

    other_hotel_id = hotel_id + 1
    foreign_seed = session_factory()
    try:
        set_tenant_hotel_context(foreign_seed, hotel_id)
        foreign_hotel = HotelConfiguration(id=other_hotel_id, hotel_name="Synthetic foreign hotel")
        foreign_category = RoomCategory(
            hotel_id=other_hotel_id,
            name="Synthetic foreign room",
            code="FOREIGN",
            base_price_per_night=Decimal("60000.00"),
            max_occupancy=2,
        )
        foreign_seed.add_all([foreign_hotel, foreign_category])
        foreign_seed.flush()
        foreign_room = Room(
            hotel_id=other_hotel_id,
            room_number="FOREIGN-1",
            floor=1,
            category_id=foreign_category.id,
            status=RoomStatusEnum.AVAILABLE,
        )
        foreign_seed.add(foreign_room)
        foreign_seed.commit()
        foreign_room_id = foreign_room.id
    finally:
        foreign_seed.close()

    def override_get_db():
        session = session_factory()
        set_tenant_context(session, user_id=user_id, hotel_id=hotel_id)
        try:
            yield session
        finally:
            session.close()

    def override_auth_context():
        return AuthContext(
            hotel_id=hotel_id,
            user_id=user_id,
            user_email=f"manager-{user_id}@example.test",
            user_role="manager",
            is_verified=True,
            permissions=set(),
        )

    previous_overrides = dict(fastapi_app.dependency_overrides)
    fastapi_app.dependency_overrides[get_db] = override_get_db
    fastapi_app.dependency_overrides[get_auth_context] = override_auth_context
    try:
        with TestClient(fastapi_app) as client:
            move_response = client.post(
                f"/api/reservations/{reservation_id}/room-move",
                json={
                    "to_room_id": destination_room_id,
                    "reason_code": "operational",
                    "notes": "Synthetic same-category move",
                    "client_version": 0,
                    "price_action": "keep",
                    "origin_room_disposition": None,
                    "origin_room_disposition_note": None,
                },
            )
            assert move_response.status_code == 200, move_response.text
            moved = move_response.json()["reservation"]
            assert moved["room_id"] == destination_room_id
            assert moved["total_amount"] == 180000.0

            foreign_move = client.post(
                f"/api/reservations/{reservation_id}/room-move",
                json={
                    "to_room_id": foreign_room_id,
                    "reason_code": "operational",
                    "client_version": moved["version"],
                    "price_action": "keep",
                },
            )
            assert foreign_move.status_code == 400, foreign_move.text
            assert "FOREIGN-1" not in foreign_move.text

        verify = session_factory()
        try:
            set_tenant_context(verify, user_id=user_id, hotel_id=hotel_id)
            stored_reservation = verify.get(Reservation, reservation_id)
            assert stored_reservation is not None
            assert stored_reservation.room_id == destination_room_id
            assert stored_reservation.category_id == source_category_id
            assert stored_reservation.total_amount == Decimal("180000.00")
        finally:
            verify.close()
    finally:
        fastapi_app.dependency_overrides.clear()
        fastapi_app.dependency_overrides.update(previous_overrides)


def test_postgres_required_room_move_quote_errors_become_domain_errors(pg_engine, monkeypatch):
    db, hotel_id, reservation, _source_room, destination_room, _user_id = _seed_room_move_case(
        pg_engine,
        different_destination_category=True,
    )
    monkeypatch.setattr(operations, "_invalidate_availability_cache", lambda _hotel_id: None)
    monkeypatch.setattr(operations, "_touch_facts", lambda *_args, **_kwargs: None)

    def unavailable_quote(*_args, **_kwargs):
        raise ReservationError("El hotel debe confirmar sus reglas de depósito y cancelación.")

    monkeypatch.setattr(operations, "calculate_reservation_pricing", unavailable_quote)
    source_room_id = reservation.room_id
    try:
        with pytest.raises(ReservationOperationsError, match="confirmar sus reglas de depósito"):
            move_reservation_room(
                db,
                reservation=reservation,
                to_room_id=destination_room.id,
                hotel_id=hotel_id,
                client_version=reservation.version,
                actor_role="owner",
                reason_code="operational",
                price_action="reprice",
            )

        db.refresh(reservation)
        assert reservation.room_id == source_room_id
        assert reservation.total_amount == Decimal("180000.00")
    finally:
        db.close()
