from datetime import date

import pytest

from app.models.hotel_config import HotelConfiguration
from app.models.guest import DocumentTypeEnum, Guest
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.room import Room, RoomCategory, RoomStatusEnum
from app.models.room_block import RoomBlockReasonEnum
from app.models.user import User
from app.services.reservation_service import check_room_availability, find_available_rooms
from app.services.allocation_engine import build_slots_from_db
from app.services.room_block_service import (
    ProtectedReservationConflictError,
    create_block,
    list_active_blocks,
    resolve_block,
)


def _hotel(db, hotel_id: int) -> HotelConfiguration:
    hotel = HotelConfiguration(id=hotel_id, deposit_percentage=30.0, subscription_active=True)
    db.add(hotel)
    db.flush()
    return hotel


def _category(db, hotel_id: int, code: str = "STD") -> RoomCategory:
    category = RoomCategory(
        hotel_id=hotel_id,
        name=f"{code} category",
        code=f"{code}{hotel_id}",
        base_price_per_night=100.0,
        max_occupancy=2,
    )
    db.add(category)
    db.flush()
    return category


def _room(db, hotel_id: int, category_id: int, number: str) -> Room:
    room = Room(
        hotel_id=hotel_id,
        category_id=category_id,
        room_number=number,
        floor=1,
        status=RoomStatusEnum.AVAILABLE,
        is_active=True,
    )
    db.add(room)
    db.flush()
    return room


def _guest(db, hotel_id: int) -> Guest:
    guest = Guest(
        hotel_id=hotel_id,
        first_name="Test",
        last_name="Guest",
        document_type=DocumentTypeEnum.DNI,
        document_number=f"{hotel_id}12345",
        terms_accepted=True,
    )
    db.add(guest)
    db.flush()
    return guest


def _user(db, user_id: int) -> User:
    user = User(
        id=user_id,
        email=f"user{user_id}@example.com",
        password_hash="test",
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    db.flush()
    return user


def _reservation(
    db,
    *,
    hotel_id: int,
    room_id: int,
    category_id: int,
    status: ReservationStatusEnum = ReservationStatusEnum.PENDING,
    allocation_locked: bool = False,
    company_id: int | None = None,
) -> Reservation:
    reservation = Reservation(
        hotel_id=hotel_id,
        confirmation_code=f"RB-{hotel_id}-{room_id}-{status.value}",
        guest_id=_guest(db, hotel_id).id,
        room_id=room_id,
        category_id=category_id,
        check_in_date=date(2026, 7, 10),
        check_out_date=date(2026, 7, 14),
        status=status,
        total_amount=400,
        allocation_locked=allocation_locked,
        company_id=company_id,
    )
    db.add(reservation)
    db.flush()
    return reservation


def test_active_room_block_excludes_room_from_availability(db):
    _hotel(db, 1)
    category = _category(db, 1)
    blocked_room = _room(db, 1, category.id, "101")
    open_room = _room(db, 1, category.id, "102")

    create_block(
        db,
        hotel_id=1,
        room_id=blocked_room.id,
        starts_at=date(2026, 7, 1),
        ends_at=date(2026, 7, 5),
        reason_code=RoomBlockReasonEnum.MAINTENANCE,
    )

    assert check_room_availability(db, blocked_room.id, date(2026, 7, 2), date(2026, 7, 4), hotel_id=1) is False
    assert check_room_availability(db, open_room.id, date(2026, 7, 2), date(2026, 7, 4), hotel_id=1) is True
    assert [room.id for room in find_available_rooms(db, category.id, date(2026, 7, 2), date(2026, 7, 4), hotel_id=1)] == [open_room.id]


def test_indefinite_block_excludes_future_dates_until_resolved(db):
    _hotel(db, 1)
    category = _category(db, 1)
    room = _room(db, 1, category.id, "101")

    block = create_block(
        db,
        hotel_id=1,
        room_id=room.id,
        starts_at=date(2026, 7, 1),
        ends_at=None,
        is_indefinite=True,
        reason_code=RoomBlockReasonEnum.DEEP_CLEANING,
    )

    assert check_room_availability(db, room.id, date(2027, 1, 1), date(2027, 1, 3), hotel_id=1) is False

    _user(db, 42)
    resolve_block(db, hotel_id=1, block_id=block.id, resolved_by_user_id=42)

    assert check_room_availability(db, room.id, date(2027, 1, 1), date(2027, 1, 3), hotel_id=1) is True


def test_block_overlapping_protected_reservation_requires_manual_resolution(db):
    _hotel(db, 1)
    category = _category(db, 1)
    room = _room(db, 1, category.id, "101")
    reservation = _reservation(
        db,
        hotel_id=1,
        room_id=room.id,
        category_id=category.id,
        allocation_locked=True,
    )

    with pytest.raises(ProtectedReservationConflictError) as exc_info:
        create_block(
            db,
            hotel_id=1,
            room_id=room.id,
            starts_at=date(2026, 7, 12),
            ends_at=date(2026, 7, 13),
            reason_code=RoomBlockReasonEnum.MAINTENANCE,
        )

    assert exc_info.value.reservation_ids == [reservation.id]


def test_resolved_block_frees_room(db):
    _hotel(db, 1)
    category = _category(db, 1)
    room = _room(db, 1, category.id, "101")
    block = create_block(
        db,
        hotel_id=1,
        room_id=room.id,
        starts_at=date(2026, 7, 1),
        ends_at=date(2026, 7, 5),
        reason_code=RoomBlockReasonEnum.OTHER,
    )

    assert check_room_availability(db, room.id, date(2026, 7, 2), date(2026, 7, 4), hotel_id=1) is False

    _user(db, 7)
    resolved = resolve_block(db, hotel_id=1, block_id=block.id, resolved_by_user_id=7)

    assert resolved.resolved_by_user_id == 7
    assert check_room_availability(db, room.id, date(2026, 7, 2), date(2026, 7, 4), hotel_id=1) is True


def test_room_blocks_are_hotel_scoped(db):
    _hotel(db, 1)
    _hotel(db, 2)
    category_1 = _category(db, 1)
    category_2 = _category(db, 2)
    room_1 = _room(db, 1, category_1.id, "101")
    room_2 = _room(db, 2, category_2.id, "101")

    create_block(
        db,
        hotel_id=1,
        room_id=room_1.id,
        starts_at=date(2026, 7, 1),
        ends_at=date(2026, 7, 5),
        reason_code=RoomBlockReasonEnum.MAINTENANCE,
    )

    assert check_room_availability(db, room_1.id, date(2026, 7, 2), date(2026, 7, 4), hotel_id=1) is False
    assert check_room_availability(db, room_2.id, date(2026, 7, 2), date(2026, 7, 4), hotel_id=2) is True
    assert list_active_blocks(db, hotel_id=2, start_date=date(2026, 7, 2), end_date=date(2026, 7, 4)) == []


def test_allocation_candidates_exclude_blocked_rooms(db):
    _hotel(db, 1)
    category = _category(db, 1)
    blocked_room = _room(db, 1, category.id, "101")
    open_room = _room(db, 1, category.id, "102")

    create_block(
        db,
        hotel_id=1,
        room_id=blocked_room.id,
        starts_at=date(2026, 7, 1),
        ends_at=date(2026, 7, 5),
        reason_code=RoomBlockReasonEnum.MAINTENANCE,
    )

    _, room_slots = build_slots_from_db(
        db,
        start_date=date(2026, 7, 2),
        end_date=date(2026, 7, 4),
        hotel_id=1,
    )

    assert [slot.room_id for slot in room_slots] == [open_room.id]
