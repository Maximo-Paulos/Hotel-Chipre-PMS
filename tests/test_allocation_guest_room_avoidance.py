from __future__ import annotations

from datetime import date

from sqlalchemy import event

from app.models.guest import Guest
from app.models.guest_room_avoidance import GuestRoomAvoidance, GuestRoomAvoidanceStatusEnum
from app.models.hotel_config import HotelConfiguration
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.room import Room, RoomCategory, RoomStatusEnum
from app.services.allocation_engine import (
    ReservationSlot,
    RoomSlot,
    _run_allocation_greedy,
    build_slots_from_db,
    run_allocation,
)


HORIZON_START = date(2027, 5, 10)
HORIZON_END = date(2027, 5, 15)


def _seed_hotel(db, *, room_count: int = 2):
    hotel = HotelConfiguration(id=9701, hotel_name="Avoidance Allocation", subscription_active=True)
    standard = RoomCategory(
        hotel_id=hotel.id,
        name="Standard",
        code="AVOID-STD",
        base_price_per_night=100,
        max_occupancy=2,
    )
    db.add_all([hotel, standard])
    db.flush()
    rooms = [
        Room(
            hotel_id=hotel.id,
            category_id=standard.id,
            room_number=f"A-{index}",
            status=RoomStatusEnum.AVAILABLE,
            is_active=True,
            score=index,
        )
        for index in range(1, room_count + 1)
    ]
    db.add_all(rooms)
    db.flush()
    return hotel, standard, rooms


def _guest(db, hotel_id: int, suffix: str = "guest"):
    guest = Guest(hotel_id=hotel_id, first_name="Returning", last_name=suffix)
    db.add(guest)
    db.flush()
    return guest


def _reservation(
    db,
    *,
    hotel_id: int,
    guest_id: int,
    category_id: int,
    room_id: int | None,
    check_in: date,
    check_out: date,
    status: ReservationStatusEnum,
    confirmation_code: str,
):
    reservation = Reservation(
        hotel_id=hotel_id,
        guest_id=guest_id,
        category_id=category_id,
        room_id=room_id,
        check_in_date=check_in,
        check_out_date=check_out,
        status=status,
        confirmation_code=confirmation_code,
        total_amount=100,
        amount_paid=0,
        num_adults=1,
    )
    db.add(reservation)
    db.flush()
    return reservation


def _slots(db, hotel_id: int):
    return build_slots_from_db(
        db,
        hotel_id=hotel_id,
        start_date=HORIZON_START,
        end_date=HORIZON_END,
    )


def test_active_rejection_never_leaves_guest_unassigned_when_it_is_the_only_room(db):
    hotel, category, rooms = _seed_hotel(db, room_count=1)
    guest = _guest(db, hotel.id)
    upcoming = _reservation(
        db,
        hotel_id=hotel.id,
        guest_id=guest.id,
        category_id=category.id,
        room_id=None,
        check_in=HORIZON_START,
        check_out=date(2027, 5, 12),
        status=ReservationStatusEnum.PENDING,
        confirmation_code="AVOID-ONLY-ROOM",
    )
    db.add(
        GuestRoomAvoidance(
            hotel_id=hotel.id,
            guest_id=guest.id,
            room_id=rooms[0].id,
            status=GuestRoomAvoidanceStatusEnum.ACTIVE,
            reason="Noise complaint",
        )
    )
    db.flush()

    slots, room_slots = _slots(db, hotel.id)
    cp_sat = run_allocation(slots, room_slots, optimization_horizon=(HORIZON_START, HORIZON_END))
    greedy = _run_allocation_greedy(slots, room_slots, optimization_horizon=(HORIZON_START, HORIZON_END))

    assert cp_sat.success is True
    assert cp_sat.unassigned_reservations == []
    assert cp_sat.assignments[upcoming.id] == rooms[0].id
    assert greedy.success is True
    assert greedy.assignments[upcoming.id] == rooms[0].id


def test_previous_completed_room_signal_requires_the_new_reservation_category(db):
    hotel, standard, rooms = _seed_hotel(db)
    superior = RoomCategory(
        hotel_id=hotel.id,
        name="Superior",
        code="AVOID-SUP",
        base_price_per_night=150,
        max_occupancy=2,
    )
    db.add(superior)
    db.flush()
    superior_room = Room(
        hotel_id=hotel.id,
        category_id=superior.id,
        room_number="S-1",
        status=RoomStatusEnum.AVAILABLE,
    )
    db.add(superior_room)
    db.flush()
    guest = _guest(db, hotel.id)
    _reservation(
        db,
        hotel_id=hotel.id,
        guest_id=guest.id,
        category_id=standard.id,
        room_id=rooms[0].id,
        check_in=date(2026, 12, 20),
        check_out=date(2026, 12, 22),
        status=ReservationStatusEnum.CHECKED_OUT,
        confirmation_code="AVOID-OLDER-STD",
    )
    _reservation(
        db,
        hotel_id=hotel.id,
        guest_id=guest.id,
        category_id=superior.id,
        room_id=superior_room.id,
        check_in=date(2027, 1, 1),
        check_out=date(2027, 1, 3),
        status=ReservationStatusEnum.CHECKED_OUT,
        confirmation_code="AVOID-PAST-SUP",
    )
    upcoming = _reservation(
        db,
        hotel_id=hotel.id,
        guest_id=guest.id,
        category_id=standard.id,
        room_id=None,
        check_in=HORIZON_START,
        check_out=date(2027, 5, 12),
        status=ReservationStatusEnum.PENDING,
        confirmation_code="AVOID-UPCOMING-STD",
    )

    slots, _ = _slots(db, hotel.id)
    slot = next(item for item in slots if item.reservation_id == upcoming.id)
    assert slot.guest_id == guest.id
    assert slot.prior_stay_room_id is None
    assert rooms[0].category_id == standard.id


def test_last_completed_room_signal_is_applied_by_cp_sat_and_greedy(db):
    hotel, category, rooms = _seed_hotel(db)
    guest = _guest(db, hotel.id)
    _reservation(
        db,
        hotel_id=hotel.id,
        guest_id=guest.id,
        category_id=category.id,
        room_id=rooms[0].id,
        check_in=date(2027, 1, 1),
        check_out=date(2027, 1, 3),
        status=ReservationStatusEnum.CHECKED_OUT,
        confirmation_code="AVOID-PAST-ROOM",
    )
    upcoming = _reservation(
        db,
        hotel_id=hotel.id,
        guest_id=guest.id,
        category_id=category.id,
        room_id=None,
        check_in=HORIZON_START,
        check_out=date(2027, 5, 12),
        status=ReservationStatusEnum.PENDING,
        confirmation_code="AVOID-RETURNING",
    )

    slots, room_slots = _slots(db, hotel.id)
    cp_sat = run_allocation(slots, room_slots, optimization_horizon=(HORIZON_START, HORIZON_END))
    greedy = _run_allocation_greedy(slots, room_slots, optimization_horizon=(HORIZON_START, HORIZON_END))

    assert next(slot for slot in slots if slot.reservation_id == upcoming.id).prior_stay_room_id == rooms[0].id
    assert cp_sat.assignments[upcoming.id] == rooms[0].id
    assert greedy.assignments[upcoming.id] == rooms[0].id


def test_soft_signals_do_not_move_an_already_compatible_assignment():
    slot = ReservationSlot(
        reservation_id=1,
        guest_id=10,
        category_id=1,
        check_in=HORIZON_START,
        check_out=date(2027, 5, 12),
        current_room_id=1,
        is_locked=False,
        prior_stay_room_id=2,
        avoided_room_ids=[1],
    )
    rooms = [
        RoomSlot(room_id=1, room_number="101", category_id=1),
        RoomSlot(room_id=2, room_number="102", category_id=1),
    ]

    cp_sat = run_allocation([slot], rooms, optimization_horizon=(HORIZON_START, HORIZON_END))
    greedy = _run_allocation_greedy([slot], rooms, optimization_horizon=(HORIZON_START, HORIZON_END))

    assert cp_sat.assignments == {1: 1}
    assert greedy.assignments == {1: 1}


def test_last_completed_room_and_active_rejections_are_loaded_in_one_batch_query(db):
    hotel, category, rooms = _seed_hotel(db)
    guest = _guest(db, hotel.id)
    _reservation(
        db,
        hotel_id=hotel.id,
        guest_id=guest.id,
        category_id=category.id,
        room_id=rooms[0].id,
        check_in=date(2027, 1, 1),
        check_out=date(2027, 1, 3),
        status=ReservationStatusEnum.CHECKED_OUT,
        confirmation_code="AVOID-PAST-FINAL",
    )
    upcoming = _reservation(
        db,
        hotel_id=hotel.id,
        guest_id=guest.id,
        category_id=category.id,
        room_id=None,
        check_in=HORIZON_START,
        check_out=date(2027, 5, 12),
        status=ReservationStatusEnum.PENDING,
        confirmation_code="AVOID-UPCOMING",
    )
    db.add(
        GuestRoomAvoidance(
            hotel_id=hotel.id,
            guest_id=guest.id,
            room_id=rooms[1].id,
            status=GuestRoomAvoidanceStatusEnum.ACTIVE,
        )
    )
    db.flush()

    statements: list[str] = []

    def capture_sql(_connection, _cursor, statement, _parameters, _context, _executemany):
        statements.append(statement.lower())

    event.listen(db.bind, "before_cursor_execute", capture_sql)
    try:
        slots, _ = _slots(db, hotel.id)
    finally:
        event.remove(db.bind, "before_cursor_execute", capture_sql)

    slot = next(item for item in slots if item.reservation_id == upcoming.id)
    assert slot.prior_stay_room_id == rooms[0].id
    assert slot.avoided_room_ids == [rooms[1].id]
    signal_queries = [
        statement
        for statement in statements
        if "from guest_room_avoidance" in statement
        and "from reservations" in statement
        and "reservations.room_id is not null" in statement
    ]
    assert len(signal_queries) == 1
