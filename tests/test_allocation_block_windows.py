from datetime import date

from app.models.guest import DocumentTypeEnum, Guest
from app.models.hotel_config import HotelConfiguration
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.room import Room, RoomCategory, RoomStatusEnum
from app.models.room_block import RoomBlock, RoomBlockReasonEnum
from app.services.allocation_engine import build_slots_from_db, run_allocation


def test_room_block_excludes_only_stays_that_overlap_its_date_window(db):
    hotel = HotelConfiguration(id=901, hotel_name="Block window test")
    db.add(hotel)
    db.flush()
    category = RoomCategory(
        hotel_id=hotel.id,
        name="Standard",
        code="STD",
        base_price_per_night=100,
        max_occupancy=2,
    )
    db.add(category)
    db.flush()
    room = Room(
        hotel_id=hotel.id,
        room_number="101",
        category_id=category.id,
        status=RoomStatusEnum.AVAILABLE,
        is_active=True,
        is_accessible=True,
    )
    guest = Guest(
        hotel_id=hotel.id,
        first_name="Synthetic",
        last_name="Guest",
        document_type=DocumentTypeEnum.DNI,
        document_number="9010001",
        terms_accepted=True,
    )
    db.add_all([room, guest])
    db.flush()
    block = RoomBlock(
        hotel_id=hotel.id,
        room_id=room.id,
        reason_code=RoomBlockReasonEnum.MAINTENANCE,
        starts_at=date(2026, 4, 10),
        ends_at=date(2026, 4, 12),
        is_indefinite=False,
    )
    blocked_stay = Reservation(
        hotel_id=hotel.id,
        confirmation_code="BLOCK-OVERLAP",
        guest_id=guest.id,
        room_id=None,
        category_id=category.id,
        check_in_date=date(2026, 4, 9),
        check_out_date=date(2026, 4, 11),
        status=ReservationStatusEnum.PENDING,
        total_amount=100,
        amount_paid=0,
        deposit_amount=0,
    )
    available_stay = Reservation(
        hotel_id=hotel.id,
        confirmation_code="BLOCK-AFTER",
        guest_id=guest.id,
        room_id=None,
        category_id=category.id,
        check_in_date=date(2026, 4, 12),
        check_out_date=date(2026, 4, 14),
        status=ReservationStatusEnum.PENDING,
        total_amount=100,
        amount_paid=0,
        deposit_amount=0,
    )
    db.add_all([block, blocked_stay, available_stay])
    db.flush()

    reservations, rooms = build_slots_from_db(
        db,
        start_date=date(2026, 4, 1),
        end_date=date(2026, 4, 20),
        hotel_id=hotel.id,
    )

    slots_by_id = {slot.reservation_id: slot for slot in reservations}
    assert [slot.room_id for slot in rooms] == [room.id]
    assert slots_by_id[blocked_stay.id].blocked_room_ids == [room.id]
    assert slots_by_id[available_stay.id].blocked_room_ids == []

    result = run_allocation(reservations, rooms, optimization_horizon=(date(2026, 4, 1), date(2026, 4, 20)))

    assert result.assignments[available_stay.id] == room.id
    assert blocked_stay.id in result.unassigned_reservations
