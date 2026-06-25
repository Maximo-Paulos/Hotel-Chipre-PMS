from __future__ import annotations

from datetime import date
import sys
from pathlib import Path

import pytest

from app.models.room import Room, RoomCategory
from app.services.reservation_service import (
    ReservationError,
    calculate_reservation_pricing,
    check_room_availability,
)

sys.path.append(str(Path(__file__).resolve().parent))
from test_multi_hotel_isolation_contracts import (
    _seed_hotel_payload,
    _set_auth_context_override,
    isolated_client,
)


def test_pricing_foreign_category_is_not_returned_by_query(db, hotel_config, sample_categories_hotel2):
    foreign_category = sample_categories_hotel2[0]

    assert (
        db.query(RoomCategory)
        .filter(RoomCategory.id == foreign_category.id, RoomCategory.hotel_id == hotel_config.id)
        .first()
        is None
    )

    with pytest.raises(ReservationError, match=f"Room category with id={foreign_category.id} not found"):
        calculate_reservation_pricing(
            db,
            category_id=foreign_category.id,
            check_in=date(2026, 1, 1),
            check_out=date(2026, 1, 2),
            hotel_id=hotel_config.id,
        )


def test_room_availability_foreign_room_is_not_returned_by_query(db, hotel_config, sample_rooms_hotel2):
    foreign_room = sample_rooms_hotel2[0]

    assert (
        db.query(Room)
        .filter(Room.id == foreign_room.id, Room.hotel_id == hotel_config.id)
        .first()
        is None
    )

    with pytest.raises(ReservationError, match=f"Room with id={foreign_room.id} not found"):
        check_room_availability(
            db,
            foreign_room.id,
            date(2026, 1, 1),
            date(2026, 1, 2),
            hotel_id=hotel_config.id,
        )


def test_update_booking_foreign_room_is_not_returned_by_query(isolated_client):
    client, db = isolated_client
    hotel1 = _seed_hotel_payload(db, 1, "H1", "101", "RES-H1")
    hotel2 = _seed_hotel_payload(db, 2, "H2", "201", "RES-H2")
    db.commit()

    assert (
        db.query(Room)
        .filter(Room.id == hotel2["room"].id, Room.hotel_id == hotel1["hotel"].id)
        .first()
        is None
    )

    _set_auth_context_override(hotel1["hotel"].id, user_id=1, user_email="owner1@test.com", role="owner")
    response = client.patch(
        f"/api/bookings/{hotel1['reservation'].id}",
        json={"room_id": hotel2["room"].id},
    )

    assert response.status_code in {400, 404}, response.text
    assert response.json()["detail"] in {"Room not found", "Booking not found"}
