"""PostgreSQL regression coverage for the global reservation search."""
from datetime import date, timedelta
from uuid import uuid4

from app.models.guest import Guest
from app.models.hotel_config import HotelConfiguration
from app.models.reservation import Reservation
from app.models.room import RoomCategory
from app.services.reservation_service import list_reservations


def _create_hotel_reservation(db, *, hotel_id: int, suffix: str, confirmation_code: str):
    hotel = HotelConfiguration(
        id=hotel_id,
        hotel_name=f"Synthetic global search {suffix}",
        subscription_active=True,
    )
    db.add(hotel)
    db.flush()
    category = RoomCategory(
        hotel_id=hotel_id,
        name=f"Synthetic search category {suffix}",
        code=f"S{suffix}",
        base_price_per_night=100,
        max_occupancy=2,
    )
    guest = Guest(
        hotel_id=hotel_id,
        first_name="QA Extension Tester",
        last_name="1109",
    )
    db.add_all([category, guest])
    db.flush()

    check_in = date.today() + timedelta(days=30)
    reservation = Reservation(
        hotel_id=hotel_id,
        confirmation_code=confirmation_code,
        guest_id=guest.id,
        category_id=category.id,
        check_in_date=check_in,
        check_out_date=check_in + timedelta(days=2),
    )
    db.add(reservation)
    db.flush()
    return reservation


def test_global_reservation_search_matches_guest_name_and_keeps_hotel_scope(pg_session):
    suffix = uuid4().hex[:8].upper()
    hotel_a_id = 300_000_000 + uuid4().int % 50_000_000
    hotel_b_id = hotel_a_id + 1
    reservation_a = _create_hotel_reservation(
        pg_session,
        hotel_id=hotel_a_id,
        suffix=f"{suffix}A",
        confirmation_code="RES-MLXZMJRI",
    )
    reservation_b = _create_hotel_reservation(
        pg_session,
        hotel_id=hotel_b_id,
        suffix=f"{suffix}B",
        confirmation_code="RES-Y9XUPLO1",
    )

    code_results = list_reservations(
        pg_session,
        hotel_id=hotel_a_id,
        search="RES-MLXZMJRI",
    )
    full_name_results = list_reservations(
        pg_session,
        hotel_id=hotel_a_id,
        search="QA Extension Tester 1109",
    )
    partial_name_results = list_reservations(
        pg_session,
        hotel_id=hotel_a_id,
        search="QA Extension",
    )
    other_hotel_code_results = list_reservations(
        pg_session,
        hotel_id=hotel_a_id,
        search="RES-Y9XUPLO1",
    )

    assert [row.id for row in code_results] == [reservation_a.id]
    assert [row.id for row in full_name_results] == [reservation_a.id]
    assert [row.id for row in partial_name_results] == [reservation_a.id]
    assert reservation_b.id not in [row.id for row in full_name_results]
    assert other_hotel_code_results == []
