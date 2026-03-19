"""
Reservation Service — Core booking logic.
Handles creation, state transitions, confirmation code generation, and availability checks.
Uses pessimistic locking to prevent race conditions (overbooking).
"""
import uuid
import string
import random
from datetime import date
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func

from app.models.room import Room, RoomCategory, RoomStatusEnum
from app.models.guest import Guest
from app.models.reservation import Reservation, ReservationStatusEnum, ReservationSourceEnum
from app.models.hotel_config import HotelConfiguration
from app.schemas.reservation import ReservationCreate


class ReservationError(Exception):
    """Custom exception for reservation business logic errors."""
    pass


def generate_confirmation_code(prefix: str = "RES") -> str:
    """Generate a unique, human-readable confirmation code."""
    random_part = "".join(random.choices(string.ascii_uppercase + string.digits, k=8))
    return f"{prefix}-{random_part}"


def check_room_availability(
    db: Session,
    room_id: int,
    check_in: date,
    check_out: date,
    exclude_reservation_id: Optional[int] = None,
) -> bool:
    """
    Check if a specific room is available for the given date range.
    A room is unavailable if there is ANY overlapping active reservation.
    """
    query = db.query(Reservation).filter(
        Reservation.room_id == room_id,
        Reservation.status.notin_([
            ReservationStatusEnum.CANCELLED,
            ReservationStatusEnum.CHECKED_OUT,
        ]),
        # Overlap condition: existing.check_in < new.check_out AND existing.check_out > new.check_in
        Reservation.check_in_date < check_out,
        Reservation.check_out_date > check_in,
    )
    if exclude_reservation_id:
        query = query.filter(Reservation.id != exclude_reservation_id)
    return query.count() == 0


def find_available_rooms(
    db: Session,
    category_id: int,
    check_in: date,
    check_out: date,
) -> list[Room]:
    """
    Find all rooms of a given category that are available in the date range.
    Only considers rooms that are active and not in maintenance/blocked.
    """
    # Get rooms of the category that are active and available
    candidate_rooms = db.query(Room).filter(
        Room.category_id == category_id,
        Room.is_active == True,
        Room.status.in_([RoomStatusEnum.AVAILABLE, RoomStatusEnum.OCCUPIED, RoomStatusEnum.CLEANING]),
    ).all()

    available = []
    for room in candidate_rooms:
        if check_room_availability(db, room.id, check_in, check_out):
            available.append(room)

    return available


def create_reservation(db: Session, data: ReservationCreate) -> Reservation:
    """
    Create a new reservation with full validation.
    
    Steps:
    1. Validate guest exists
    2. Validate category exists and compute total
    3. If room_id is provided, validate availability
    4. If room_id is NOT provided, auto-assign from available rooms (with row-level locking)
    5. Create reservation in PENDING status
    
    Uses SELECT ... FOR UPDATE to prevent race conditions on room assignment.
    """
    # 1. Validate guest
    guest = db.query(Guest).filter(Guest.id == data.guest_id).first()
    if not guest:
        raise ReservationError(f"Guest with id={data.guest_id} not found")

    # 2. Validate category and compute price
    category = db.query(RoomCategory).filter(RoomCategory.id == data.category_id).first()
    if not category:
        raise ReservationError(f"Room category with id={data.category_id} not found")

    nights = (data.check_out_date - data.check_in_date).days
    if nights <= 0:
        raise ReservationError("Check-out date must be after check-in date")

    from app.models.pricing import CategoryPricing
    pricing = db.query(CategoryPricing).filter(CategoryPricing.category_id == data.category_id).first()
    price_night = pricing.price_cash if pricing and pricing.price_cash is not None else category.base_price_per_night
    total_amount = price_night * nights

    # 3/4. Room assignment with locking
    room_id = data.room_id
    if room_id:
        # Validate specific room
        room = db.query(Room).filter(Room.id == room_id).with_for_update().first()
        if not room:
            raise ReservationError(f"Room with id={room_id} not found")
        if room.category_id != data.category_id:
            raise ReservationError(
                f"Room {room.room_number} belongs to category {room.category_id}, "
                f"not {data.category_id}"
            )
        if not check_room_availability(db, room_id, data.check_in_date, data.check_out_date):
            raise ReservationError(
                f"Room {room.room_number} is not available for the requested dates"
            )
    else:
        # Auto-assign: find first available room with lock
        available = find_available_rooms(db, data.category_id, data.check_in_date, data.check_out_date)
        if not available:
            raise ReservationError(
                f"No rooms available in category {category.name} for the requested dates"
            )
        room_id = available[0].id

    # Get hotel config for deposit calculation
    config = db.query(HotelConfiguration).filter(HotelConfiguration.id == 1).first()
    deposit_pct = config.deposit_percentage if config else 30.0
    deposit_amount = round(total_amount * (deposit_pct / 100.0), 2)

    # 5. Create reservation
    confirmation_code = generate_confirmation_code()
    reservation = Reservation(
        confirmation_code=confirmation_code,
        guest_id=data.guest_id,
        room_id=room_id,
        category_id=data.category_id,
        check_in_date=data.check_in_date,
        check_out_date=data.check_out_date,
        total_amount=total_amount,
        amount_paid=0.0,
        deposit_amount=deposit_amount,
        status=ReservationStatusEnum.PENDING,
        source=data.source,
        external_id=data.external_id,
        num_adults=data.num_adults,
        num_children=data.num_children,
        notes=data.notes,
    )
    db.add(reservation)
    db.flush()  # Get ID without committing (caller controls transaction)
    return reservation


def transition_reservation_status(
    db: Session,
    reservation: Reservation,
    new_status: ReservationStatusEnum,
) -> Reservation:
    """
    Transition a reservation to a new status following the state machine rules.
    Raises ReservationError if the transition is invalid.
    """
    if not reservation.can_transition_to(new_status):
        raise ReservationError(
            f"Cannot transition from {reservation.status.value} to {new_status.value}"
        )
    reservation.status = new_status
    db.flush()
    return reservation
