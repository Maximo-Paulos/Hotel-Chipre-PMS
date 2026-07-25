"""
Tests for check-in security enforcement:
  - prohibido_alojar tag blocks check-in (v72 §2.7)
  - optimistic locking on reservation updates
  - PRE_CHECK_IN status is a valid pre-check-in state
"""
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.models.guest import Guest, GuestTag, GuestTagTypeEnum
from app.models.hotel_config import HotelConfiguration
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.room import Room, RoomCategory, RoomStatusEnum
from app.services.checkin_service import perform_checkin, CheckInError
from app.services.reservation_service import (
    ReservationError,
    update_reservation_fields,
)
from app.schemas.reservation import ReservationUpdate


# ── helpers ──────────────────────────────────────────────────────────────────

def _make_hotel(db: Session, hotel_id: int) -> HotelConfiguration:
    hotel = HotelConfiguration(id=hotel_id, hotel_name=f"Hotel {hotel_id}", subscription_active=True)
    db.add(hotel)
    db.flush()
    return hotel


def _make_guest(db: Session, hotel_id: int, doc: str = "11111111") -> Guest:
    guest = Guest(
        hotel_id=hotel_id,
        first_name="Ana",
        last_name="Gomez",
        document_type="DNI",
        document_number=doc,
        birth_place="Mendoza",
        birth_country="Argentina",
        marital_status="single",
        occupation="Enfermera",
        terms_accepted=True,
    )
    db.add(guest)
    db.flush()
    return guest


def _make_room(db: Session, hotel_id: int) -> tuple[RoomCategory, Room]:
    cat = RoomCategory(
        hotel_id=hotel_id, name="Standard", code="STD",
        base_price_per_night=Decimal("100.00"), max_occupancy=2,
    )
    db.add(cat)
    db.flush()
    room = Room(
        hotel_id=hotel_id, category_id=cat.id, room_number="101",
        status=RoomStatusEnum.AVAILABLE,
    )
    db.add(room)
    db.flush()
    return cat, room


_res_counter = 0


def _make_paid_reservation(
    db: Session, hotel_id: int, guest: Guest, cat: RoomCategory, room: Room,
    status: ReservationStatusEnum = ReservationStatusEnum.FULLY_PAID,
) -> Reservation:
    global _res_counter
    _res_counter += 1
    res = Reservation(
        hotel_id=hotel_id,
        guest_id=guest.id,
        category_id=cat.id,
        room_id=room.id,
        check_in_date=date(2026, 7, 1),
        check_out_date=date(2026, 7, 3),
        num_adults=1,
        total_amount=Decimal("200.00"),
        amount_paid=Decimal("200.00"),
        status=status,
        confirmation_code=f"TEST{_res_counter:06d}",
    )
    db.add(res)
    db.flush()
    return res


# ── prohibido_alojar tests ────────────────────────────────────────────────────

def test_prohibido_alojar_blocks_checkin(db: Session):
    """Guest with active prohibido_alojar tag cannot check in."""
    hotel = _make_hotel(db, 5001)
    guest = _make_guest(db, 5001)
    cat, room = _make_room(db, 5001)
    res = _make_paid_reservation(db, 5001, guest, cat, room)

    tag = GuestTag(
        hotel_id=5001,
        guest_id=guest.id,
        tag_type=GuestTagTypeEnum.PROHIBIDO_ALOJAR,
        note="No payment history",
    )
    db.add(tag)
    db.flush()

    with pytest.raises(CheckInError) as exc_info:
        perform_checkin(db, res.id, hotel_id=5001)

    assert "prohibido_alojar" in str(exc_info.value)
    assert "No payment history" in str(exc_info.value)


def test_other_tags_do_not_block_checkin(db: Session):
    """VIP and other non-blocking tags must not prevent check-in."""
    hotel = _make_hotel(db, 5002)
    guest = _make_guest(db, 5002)
    cat, room = _make_room(db, 5002)
    res = _make_paid_reservation(db, 5002, guest, cat, room)

    tag = GuestTag(
        hotel_id=5002,
        guest_id=guest.id,
        tag_type=GuestTagTypeEnum.VIP,
    )
    db.add(tag)
    db.flush()

    # Should not raise
    checked_in = perform_checkin(db, res.id, hotel_id=5002)
    assert checked_in.status == ReservationStatusEnum.CHECKED_IN


def test_no_prohibido_tag_allows_checkin(db: Session):
    """Guest without prohibido_alojar tag can check in normally."""
    hotel = _make_hotel(db, 5003)
    guest = _make_guest(db, 5003)
    cat, room = _make_room(db, 5003)
    res = _make_paid_reservation(db, 5003, guest, cat, room)

    checked_in = perform_checkin(db, res.id, hotel_id=5003)
    assert checked_in.status == ReservationStatusEnum.CHECKED_IN
    assert checked_in.actual_check_in is not None


def test_prohibido_tag_from_different_hotel_does_not_block(db: Session):
    """prohibido_alojar tag from a different hotel must not affect check-in."""
    hotel_a = _make_hotel(db, 5004)
    hotel_b = _make_hotel(db, 5005)

    guest_a = _make_guest(db, 5004, doc="22222222")
    guest_b = _make_guest(db, 5005, doc="22222222")

    cat_a, room_a = _make_room(db, 5004)
    res_a = _make_paid_reservation(db, 5004, guest_a, cat_a, room_a)

    # Tag on hotel_b guest — must not leak into hotel_a check-in
    tag = GuestTag(
        hotel_id=5005,
        guest_id=guest_b.id,
        tag_type=GuestTagTypeEnum.PROHIBIDO_ALOJAR,
    )
    db.add(tag)
    db.flush()

    # hotel_a check-in should succeed
    checked_in = perform_checkin(db, res_a.id, hotel_id=5004)
    assert checked_in.status == ReservationStatusEnum.CHECKED_IN


# ── PRE_CHECK_IN status allows check-in ───────────────────────────────────────

def test_pre_check_in_status_allows_checkin(db: Session):
    """A reservation in PRE_CHECK_IN state can transition to CHECKED_IN."""
    hotel = _make_hotel(db, 5006)
    guest = _make_guest(db, 5006)
    cat, room = _make_room(db, 5006)
    res = _make_paid_reservation(db, 5006, guest, cat, room, status=ReservationStatusEnum.PRE_CHECK_IN)

    checked_in = perform_checkin(db, res.id, hotel_id=5006)
    assert checked_in.status == ReservationStatusEnum.CHECKED_IN


# ── Optimistic locking ────────────────────────────────────────────────────────

def test_reservation_has_version_column(db: Session):
    """Reservations have a version column defaulting to 0."""
    hotel = _make_hotel(db, 5010)
    guest = _make_guest(db, 5010)
    cat, room = _make_room(db, 5010)
    res = _make_paid_reservation(db, 5010, guest, cat, room)

    assert res.version == 0


def test_update_increments_version(db: Session):
    """Updating a reservation increments its version."""
    hotel = _make_hotel(db, 5011)
    guest = _make_guest(db, 5011)
    cat, room = _make_room(db, 5011)
    res = _make_paid_reservation(db, 5011, guest, cat, room)

    assert res.version == 0
    update_reservation_fields(
        db, res,
        ReservationUpdate(notes="Updated note"),
        hotel_id=5011,
    )
    assert res.version == 1


def test_correct_version_passes_optimistic_lock(db: Session):
    """Providing the correct client_version passes the optimistic lock check."""
    hotel = _make_hotel(db, 5012)
    guest = _make_guest(db, 5012)
    cat, room = _make_room(db, 5012)
    res = _make_paid_reservation(db, 5012, guest, cat, room)

    # version == 0, passing client_version=0 is correct
    update_reservation_fields(
        db, res,
        ReservationUpdate(notes="First edit"),
        hotel_id=5012,
        client_version=0,
    )
    assert res.version == 1


def test_stale_version_raises_reservation_error(db: Session):
    """Providing a stale client_version raises ReservationError."""
    hotel = _make_hotel(db, 5013)
    guest = _make_guest(db, 5013)
    cat, room = _make_room(db, 5013)
    res = _make_paid_reservation(db, 5013, guest, cat, room)

    # Simulate a concurrent update bumping version to 1
    res.version = 1
    db.flush()

    with pytest.raises(ReservationError) as exc_info:
        update_reservation_fields(
            db, res,
            ReservationUpdate(notes="Stale edit"),
            hotel_id=5013,
            client_version=0,  # stale — expects 0, actual is 1
        )
    assert "concurrently" in str(exc_info.value).lower()


def test_omitting_client_version_skips_check(db: Session):
    """Omitting client_version bypasses the optimistic lock check (backward compat)."""
    hotel = _make_hotel(db, 5014)
    guest = _make_guest(db, 5014)
    cat, room = _make_room(db, 5014)
    res = _make_paid_reservation(db, 5014, guest, cat, room)
    res.version = 5
    db.flush()

    # No client_version — should succeed regardless of server version
    update_reservation_fields(
        db, res,
        ReservationUpdate(notes="No version check"),
        hotel_id=5014,
    )
    assert res.version == 6
