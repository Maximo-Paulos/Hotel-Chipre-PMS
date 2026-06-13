from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from app.models.guest import Guest, GuestRatingEnum, GuestTag, GuestTagTypeEnum
from app.models.hotel_config import HotelConfiguration
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.room import Room, RoomCategory, RoomStatusEnum
from app.models.security_audit_log import SecurityAuditLog
from app.models.user import User
from app.services.checkin_service import CheckInError, perform_checkin
from app.services.guest_service import add_tag, quick_profile, search_guests, set_rating


def _hotel(db, hotel_id: int) -> HotelConfiguration:
    hotel = HotelConfiguration(id=hotel_id, hotel_name=f"Hotel {hotel_id}", subscription_active=True)
    db.add(hotel)
    db.flush()
    return hotel


def _user(db, user_id: int) -> User:
    user = User(
        id=user_id,
        email=f"user{user_id}@example.com",
        password_hash="test",
        is_active=True,
        is_verified=True,
        role="manager",
    )
    db.add(user)
    db.flush()
    return user


def _guest(
    db,
    hotel_id: int,
    *,
    first_name: str = "Ana",
    last_name: str = "Gomez",
    document_number: str = "30000000",
    email: str = "ana@example.com",
    phone: str = "+541100000000",
) -> Guest:
    guest = Guest(
        hotel_id=hotel_id,
        first_name=first_name,
        last_name=last_name,
        document_type="DNI",
        document_number=document_number,
        email=email,
        phone=phone,
        terms_accepted=True,
    )
    db.add(guest)
    db.flush()
    return guest


def _room(db, hotel_id: int, room_number: str = "101") -> tuple[RoomCategory, Room]:
    category = RoomCategory(
        hotel_id=hotel_id,
        name=f"Standard {hotel_id}",
        code=f"STD{hotel_id}",
        base_price_per_night=Decimal("100.00"),
        max_occupancy=2,
    )
    db.add(category)
    db.flush()
    room = Room(
        hotel_id=hotel_id,
        category_id=category.id,
        room_number=room_number,
        status=RoomStatusEnum.AVAILABLE,
    )
    db.add(room)
    db.flush()
    return category, room


def _reservation(
    db,
    hotel_id: int,
    guest: Guest,
    category: RoomCategory,
    room: Room,
    *,
    day: int,
    status: ReservationStatusEnum = ReservationStatusEnum.CHECKED_OUT,
) -> Reservation:
    reservation = Reservation(
        hotel_id=hotel_id,
        guest_id=guest.id,
        category_id=category.id,
        room_id=room.id,
        check_in_date=date(2026, 1, day),
        check_out_date=date(2026, 1, day + 1),
        num_adults=1,
        total_amount=Decimal("100.00"),
        amount_paid=Decimal("100.00"),
        status=status,
        confirmation_code=f"GS{hotel_id}{guest.id}{day:02d}",
    )
    db.add(reservation)
    db.flush()
    return reservation


def test_guest_search_matches_document_phone_email_name(db):
    _hotel(db, 6101)
    _hotel(db, 6102)
    guest = _guest(
        db,
        6101,
        first_name="Ana",
        last_name="Pereira",
        document_number="33123456",
        email="ana.pereira@example.com",
        phone="+5492615551111",
    )
    _guest(db, 6102, last_name="Pereira", document_number="33123456", email="other@example.com")

    assert search_guests(db, 6101, "33123456") == [guest]
    assert search_guests(db, 6101, "261555") == [guest]
    assert search_guests(db, 6101, "pereira@example") == [guest]
    assert search_guests(db, 6101, "Pere") == [guest]


def test_guest_quick_profile_returns_recent_stays_and_tags(db):
    _hotel(db, 6103)
    _user(db, 77)
    guest = _guest(db, 6103)
    category, room = _room(db, 6103)
    for day in range(1, 7):
        _reservation(db, 6103, guest, category, room, day=day)
    active_tag = add_tag(
        db,
        hotel_id=6103,
        guest_id=guest.id,
        tag_type=GuestTagTypeEnum.CONFLICTIVO,
        note="Late checkout disputes",
        user_id=77,
    )
    expired_tag = GuestTag(
        hotel_id=6103,
        guest_id=guest.id,
        tag_type=GuestTagTypeEnum.NO_PAGO,
        expires_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
    )
    db.add(expired_tag)
    db.flush()

    profile = quick_profile(db, hotel_id=6103, guest_id=guest.id)

    assert profile["guest"].id == guest.id
    assert [stay["check_in_date"].day for stay in profile["last_stays"]] == [6, 5, 4, 3, 2]
    assert profile["active_tags"] == [active_tag]


def test_set_rating_audits_change(db):
    _hotel(db, 6104)
    _user(db, 88)
    guest = _guest(db, 6104)

    set_rating(db, hotel_id=6104, guest_id=guest.id, rating=GuestRatingEnum.COMPLICADO, user_id=88)

    assert guest.rating == GuestRatingEnum.COMPLICADO
    audit = db.query(SecurityAuditLog).filter(SecurityAuditLog.action == "guest.rating.updated").one()
    assert audit.hotel_id == 6104
    assert audit.user_id == 88
    assert "complicado" in (audit.details or "")


def test_prohibido_alojar_blocks_checkin_without_override(db):
    _hotel(db, 6105)
    _user(db, 99)
    guest = _guest(db, 6105)
    category, room = _room(db, 6105)
    reservation = _reservation(db, 6105, guest, category, room, day=1, status=ReservationStatusEnum.FULLY_PAID)
    add_tag(
        db,
        hotel_id=6105,
        guest_id=guest.id,
        tag_type=GuestTagTypeEnum.PROHIBIDO_ALOJAR,
        note="Manager review required",
        user_id=99,
    )

    with pytest.raises(CheckInError, match="prohibido_alojar"):
        perform_checkin(db, reservation.id, hotel_id=6105)


def test_authorized_override_allows_checkin_and_audits(db):
    _hotel(db, 6106)
    _user(db, 42)
    _user(db, 99)
    guest = _guest(db, 6106)
    category, room = _room(db, 6106)
    reservation = _reservation(db, 6106, guest, category, room, day=1, status=ReservationStatusEnum.FULLY_PAID)
    add_tag(
        db,
        hotel_id=6106,
        guest_id=guest.id,
        tag_type=GuestTagTypeEnum.PROHIBIDO_ALOJAR,
        note="Owner approved at desk",
        user_id=99,
    )

    checked_in = perform_checkin(
        db,
        reservation.id,
        hotel_id=6106,
        override_prohibido=True,
        override_user_id=42,
    )

    assert checked_in.status == ReservationStatusEnum.CHECKED_IN
    audit = db.query(SecurityAuditLog).filter(SecurityAuditLog.action == "checkin.prohibido_override").one()
    assert audit.hotel_id == 6106
    assert audit.user_id == 42
    assert "Owner approved at desk" in (audit.details or "")
