from datetime import date

from app.models.allocation import ReservationAllocationLock
from app.models.company import Company
from app.models.guest import DocumentTypeEnum, Guest
from app.models.hotel_config import HotelConfiguration
from app.models.operations import RoomMoveEvent, RoomMovementGroup
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.room import Room, RoomCategory, RoomStatusEnum
from app.services.allocation_engine import ReservationSlot, RoomSlot, build_slots_from_db, run_allocation
from app.services.allocation_runtime_service import run_persisted_allocation


def _slot(reservation_id: int, *, mobility: bool = False, room_id: int | None = None, locked: bool = False):
    return ReservationSlot(
        reservation_id=reservation_id,
        category_id=1,
        check_in=date(2026, 7, 1),
        check_out=date(2026, 7, 4),
        current_room_id=room_id,
        is_locked=locked,
        mobility_restriction=mobility,
    )


def test_mobility_restriction_prefers_lowest_compatible_floor():
    rooms = [
        RoomSlot(room_id=1, room_number="001", category_id=1, floor=0, score=1, is_accessible=True),
        RoomSlot(room_id=2, room_number="201", category_id=1, floor=2, score=10, is_accessible=True),
        RoomSlot(room_id=3, room_number="101", category_id=1, floor=1, score=10, is_accessible=False),
    ]

    result = run_allocation([_slot(1, mobility=True)], rooms)

    assert result.success is True
    assert result.assignments[1] == 1


def test_score_only_breaks_equivalent_room_tie():
    rooms = [
        RoomSlot(room_id=1, room_number="101", category_id=1, floor=1, score=1, is_accessible=True),
        RoomSlot(room_id=2, room_number="102", category_id=1, floor=1, score=10, is_accessible=True),
    ]

    result = run_allocation([_slot(1)], rooms)

    assert result.success is True
    assert result.assignments[1] == 2


def test_solver_does_not_move_corporate_manual_or_pre_checkin_reservations(db):
    hotel, category, rooms, guests = _seed_hotel_rooms_guests(db, room_count=4)
    company = Company(
        hotel_id=hotel.id,
        legal_name="Protected SA",
        display_name="Protected",
        requires_signature=True,
    )
    db.add(company)
    db.flush()
    reservations = [
        _reservation(db, hotel.id, guests[0].id, category.id, rooms[0].id, "CORP", company_id=company.id),
        _reservation(db, hotel.id, guests[1].id, category.id, rooms[1].id, "MANUAL", allocation_locked=True),
        _reservation(db, hotel.id, guests[2].id, category.id, rooms[2].id, "PRE", status=ReservationStatusEnum.PRE_CHECK_IN),
    ]
    db.add(
        ReservationAllocationLock(
            hotel_id=hotel.id,
            reservation_id=reservations[1].id,
            locked_room_id=rooms[1].id,
            lock_reason_code="manual_pin",
            is_active=True,
        )
    )
    db.flush()

    slots, room_slots = build_slots_from_db(
        db,
        hotel_id=hotel.id,
        start_date=date(2026, 7, 1),
        end_date=date(2026, 7, 5),
    )
    locked_by_id = {slot.reservation_id: slot.is_locked for slot in slots}
    result = run_allocation(slots, room_slots, optimization_horizon=(date(2026, 7, 1), date(2026, 7, 5)))

    assert locked_by_id == {reservation.id: True for reservation in reservations}
    assert result.success is True
    assert result.assignments[reservations[0].id] == rooms[0].id
    assert result.assignments[reservations[1].id] == rooms[1].id
    assert result.assignments[reservations[2].id] == rooms[2].id
    assert not set(reservation.id for reservation in reservations) & set(result.moved_reservations)


def test_allocation_run_creates_movement_group_and_events(db):
    hotel, category, rooms, guests = _seed_hotel_rooms_guests(db, room_count=2)
    _reservation(db, hotel.id, guests[0].id, category.id, rooms[0].id, "LOCK1", date(2026, 7, 1), date(2026, 7, 3), allocation_locked=True)
    _reservation(db, hotel.id, guests[1].id, category.id, rooms[0].id, "LOCK2", date(2026, 7, 4), date(2026, 7, 6), allocation_locked=True)
    mover = _reservation(db, hotel.id, guests[2].id, category.id, rooms[1].id, "MOVE", date(2026, 7, 3), date(2026, 7, 4))
    db.flush()

    result = run_persisted_allocation(
        db,
        hotel_id=hotel.id,
        trigger_type="test_gap_fill",
        apply=True,
        horizon_start=date(2026, 7, 1),
        horizon_end=date(2026, 7, 6),
    )

    group = db.query(RoomMovementGroup).filter(RoomMovementGroup.hotel_id == hotel.id).one()
    event = db.query(RoomMoveEvent).filter(RoomMoveEvent.movement_group_id == group.id).one()
    db.refresh(mover)
    assert result.solver_result.success is True
    assert mover.room_id == rooms[0].id
    assert group.trigger_reason == "test_gap_fill"
    assert event.reservation_id == mover.id
    assert event.from_room_id == rooms[1].id
    assert event.to_room_id == rooms[0].id


def _seed_hotel_rooms_guests(db, *, hotel_id: int = 1, room_count: int = 3):
    hotel = HotelConfiguration(id=hotel_id, subscription_active=True)
    db.add(hotel)
    db.flush()
    category = RoomCategory(
        hotel_id=hotel_id,
        name=f"Standard {hotel_id}",
        code=f"STD{hotel_id}",
        base_price_per_night=100,
        max_occupancy=2,
    )
    db.add(category)
    db.flush()
    rooms = [
        Room(
            hotel_id=hotel_id,
            room_number=f"{hotel_id}{idx:02d}",
            floor=idx,
            category_id=category.id,
            status=RoomStatusEnum.AVAILABLE,
            is_active=True,
            is_accessible=True,
            score=idx,
        )
        for idx in range(1, room_count + 1)
    ]
    guests = [
        Guest(
            hotel_id=hotel_id,
            first_name=f"Guest{idx}",
            last_name="Test",
            document_type=DocumentTypeEnum.DNI,
            document_number=f"{hotel_id}{idx:04d}",
            terms_accepted=True,
        )
        for idx in range(1, max(room_count + 2, 5))
    ]
    db.add_all([*rooms, *guests])
    db.flush()
    return hotel, category, rooms, guests


def _reservation(
    db,
    hotel_id: int,
    guest_id: int,
    category_id: int,
    room_id: int,
    code: str,
    check_in: date = date(2026, 7, 1),
    check_out: date = date(2026, 7, 4),
    *,
    status: ReservationStatusEnum = ReservationStatusEnum.PENDING,
    allocation_locked: bool = False,
    company_id: int | None = None,
) -> Reservation:
    reservation = Reservation(
        hotel_id=hotel_id,
        confirmation_code=f"{hotel_id}-{code}",
        guest_id=guest_id,
        room_id=room_id,
        category_id=category_id,
        company_id=company_id,
        check_in_date=check_in,
        check_out_date=check_out,
        status=status,
        total_amount=100,
        amount_paid=0,
        deposit_amount=0,
        allocation_locked=allocation_locked,
    )
    db.add(reservation)
    db.flush()
    return reservation
