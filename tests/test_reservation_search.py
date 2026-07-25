"""Tests for the reservation global search filter (B1 header search).

Search is a thin filter on top of list_reservations: match by confirmation
code or guest last name, always scoped to hotel_id so it can never surface a
match that belongs to a different hotel.
"""
from datetime import date

from app.models.guest import Guest
from app.models.hotel_config import HotelConfiguration
from app.schemas.reservation import ReservationCreate
from app.services.reservation_service import create_reservation, list_reservations


def _reservation(db, guest, category, room, hotel_id):
    reservation = create_reservation(
        db,
        ReservationCreate(
            guest_id=guest.id,
            category_id=category.id,
            room_id=room.id,
            check_in_date=date(2026, 9, 1),
            check_out_date=date(2026, 9, 3),
        ),
        hotel_id=hotel_id,
    )
    db.flush()
    return reservation


def test_search_matches_confirmation_code(db, sample_guest, sample_categories, sample_rooms, hotel_config):
    reservation = _reservation(db, sample_guest, sample_categories[0], sample_rooms[0], hotel_id=1)

    results = list_reservations(db, hotel_id=1, search=reservation.confirmation_code[-6:])

    assert [r.id for r in results] == [reservation.id]


def test_search_matches_guest_last_name_case_insensitive(db, sample_guest, sample_categories, sample_rooms, hotel_config):
    reservation = _reservation(db, sample_guest, sample_categories[0], sample_rooms[0], hotel_id=1)
    assert sample_guest.last_name == "Pérez"

    results = list_reservations(db, hotel_id=1, search="pérez")

    assert [r.id for r in results] == [reservation.id]


def test_search_no_match_returns_empty(db, sample_guest, sample_categories, sample_rooms, hotel_config):
    _reservation(db, sample_guest, sample_categories[0], sample_rooms[0], hotel_id=1)

    results = list_reservations(db, hotel_id=1, search="Nonexistent-Guest-Name")

    assert results == []


def test_search_does_not_leak_across_hotels(
    db,
    sample_guest,
    sample_categories,
    sample_rooms,
    hotel_config,
    sample_categories_hotel2,
    sample_rooms_hotel2,
):
    # Hotel 1 reservation.
    _reservation(db, sample_guest, sample_categories[0], sample_rooms[0], hotel_id=1)

    # Hotel 2 guest that shares the same last name as the hotel-1 guest.
    guest_hotel2 = Guest(
        first_name="Otro",
        last_name=sample_guest.last_name,
        email="otro@email.com",
        terms_accepted=True,
        hotel_id=2,
    )
    db.add(guest_hotel2)
    db.flush()
    reservation_hotel2 = _reservation(db, guest_hotel2, sample_categories_hotel2[0], sample_rooms_hotel2[0], hotel_id=2)

    # Searching from hotel 1 must only ever return hotel 1's reservation.
    results_hotel1 = list_reservations(db, hotel_id=1, search=sample_guest.last_name)
    assert all(r.hotel_id == 1 for r in results_hotel1)
    assert reservation_hotel2.id not in [r.id for r in results_hotel1]

    # Searching from hotel 2 must only ever return hotel 2's reservation.
    results_hotel2 = list_reservations(db, hotel_id=2, search=sample_guest.last_name)
    assert all(r.hotel_id == 2 for r in results_hotel2)
    assert reservation_hotel2.id in [r.id for r in results_hotel2]
