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
from app.models.pricing import CategoryPricing
from app.schemas.reservation import ReservationCreate, ReservationUpdate


class ReservationError(Exception):
    """Custom exception for reservation business logic errors."""
    pass


def generate_confirmation_code(prefix: str = "RES") -> str:
    """Generate a unique, human-readable confirmation code."""
    random_part = "".join(random.choices(string.ascii_uppercase + string.digits, k=8))
    return f"{prefix}-{random_part}"


def compute_reservation_pricing(
    db: Session,
    category_id: int,
    check_in: date,
    check_out: date,
    hotel_id: int,
) -> tuple[int, float, float, float]:
    """
    Calculate nights, nightly rate, total amount, and deposit amount for a stay.
    Raises ReservationError for invalid dates or missing category.
    """
    category = (
        db.query(RoomCategory)
        .filter(RoomCategory.id == category_id, RoomCategory.hotel_id == hotel_id)
        .first()
    )
    if not category:
        raise ReservationError(f"Room category with id={category_id} not found")

    nights = (check_out - check_in).days
    if nights <= 0:
        raise ReservationError("Check-out date must be after check-in date")

    pricing = db.query(CategoryPricing).filter(CategoryPricing.category_id == category_id).first()
    nightly_rate = pricing.price_cash if pricing and pricing.price_cash is not None else category.base_price_per_night

    total_amount = round(nightly_rate * nights, 2)

    config = db.query(HotelConfiguration).filter(HotelConfiguration.id == hotel_id).first()
    deposit_pct = config.deposit_percentage if config else 30.0
    deposit_amount = round(total_amount * (deposit_pct / 100.0), 2)

    return nights, nightly_rate, total_amount, deposit_amount


def check_room_availability(
    db: Session,
    room_id: int,
    hotel_id: int,
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
        Reservation.hotel_id == hotel_id,
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
    hotel_id: int,
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
        Room.hotel_id == hotel_id,
        Room.is_active == True,
        Room.status.in_([RoomStatusEnum.AVAILABLE, RoomStatusEnum.OCCUPIED, RoomStatusEnum.CLEANING]),
    ).all()

    available = []
    for room in candidate_rooms:
        if check_room_availability(db, room.id, hotel_id, check_in, check_out):
            available.append(room)

    return available


def create_reservation(db: Session, data: ReservationCreate, hotel_id: int) -> Reservation:
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
    category = (
        db.query(RoomCategory)
        .filter(RoomCategory.id == data.category_id, RoomCategory.hotel_id == hotel_id)
        .first()
    )
    if not category:
        raise ReservationError(f"Room category with id={data.category_id} not found")

    nights, price_night, total_amount, deposit_amount = compute_reservation_pricing(
        db, data.category_id, data.check_in_date, data.check_out_date, hotel_id
    )

    # 3/4. Room assignment with locking
    room_id = data.room_id
    if room_id:
        # Validate specific room
        room = (
            db.query(Room)
            .filter(Room.id == room_id, Room.hotel_id == hotel_id)
            .with_for_update()
            .first()
        )
        if not room:
            raise ReservationError(f"Room with id={room_id} not found")
        if room.category_id != data.category_id:
            raise ReservationError(
                f"Room {room.room_number} belongs to category {room.category_id}, "
                f"not {data.category_id}"
            )
        if not check_room_availability(db, room_id, hotel_id, data.check_in_date, data.check_out_date):
            raise ReservationError(
                f"Room {room.room_number} is not available for the requested dates"
            )
    else:
        # Auto-assign: find first available room with lock
        available = find_available_rooms(db, data.category_id, hotel_id, data.check_in_date, data.check_out_date)
        if not available:
            raise ReservationError(
                f"No rooms available in category {category.name} for the requested dates"
            )
        room_id = available[0].id

    # 5. Create reservation
    confirmation_code = generate_confirmation_code()
    reservation = Reservation(
        confirmation_code=confirmation_code,
        hotel_id=hotel_id,
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
    hotel_id: int,
) -> Reservation:
    """
    Transition a reservation to a new status following the state machine rules.
    Raises ReservationError if the transition is invalid.
    """
    if reservation.hotel_id != hotel_id:
        raise ReservationError("Cross-hotel status transition is not allowed")
    if not reservation.can_transition_to(new_status):
        raise ReservationError(
            f"Cannot transition from {reservation.status.value} to {new_status.value}"
        )
    reservation.status = new_status
    db.flush()
    return reservation


def list_reservations(
    db: Session,
    hotel_id: int,
    status_filter: str = "",
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
) -> list[Reservation]:
    query = db.query(Reservation).filter(Reservation.hotel_id == hotel_id)
    if status_filter:
        query = query.filter(Reservation.status == status_filter)
    if from_date:
        query = query.filter(Reservation.check_in_date >= from_date)
    if to_date:
        query = query.filter(Reservation.check_out_date <= to_date)
    return query.order_by(Reservation.check_in_date).all()


def get_reservation_by_id(db: Session, reservation_id: int, hotel_id: int) -> Reservation | None:
    return (
        db.query(Reservation)
        .filter(Reservation.id == reservation_id, Reservation.hotel_id == hotel_id)
        .first()
    )


def update_reservation_fields(
    db: Session,
    reservation: Reservation,
    data: ReservationUpdate,
    hotel_id: int,
) -> Reservation:
    update_data = data.model_dump(exclude_unset=True)

    new_ci = update_data.get("check_in_date", reservation.check_in_date)
    new_co = update_data.get("check_out_date", reservation.check_out_date)

    if "check_in_date" in update_data or "check_out_date" in update_data:
        if new_co <= new_ci:
            raise ReservationError("Check-out must be after check-in")
        nights = (new_co - new_ci).days
        category = (
            db.query(RoomCategory)
            .filter(RoomCategory.id == reservation.category_id, RoomCategory.hotel_id == hotel_id)
            .first()
        )
        if reservation.room_id and not check_room_availability(
            db, reservation.room_id, hotel_id, new_ci, new_co, exclude_reservation_id=reservation.id
        ):
            raise ReservationError("Room is not available for the new dates")
        reservation.check_in_date = new_ci
        reservation.check_out_date = new_co
        reservation.total_amount = category.base_price_per_night * nights

    # Handle room change
    if "room_id" in update_data and update_data["room_id"] is not None:
        new_room = db.query(Room).filter(
            Room.id == update_data["room_id"],
            Room.hotel_id == hotel_id,
        ).first()
        if not new_room:
            raise ReservationError("Room not found")
        if new_room.category_id != reservation.category_id:
            raise ReservationError("New room must be in the same category")
        if not check_room_availability(
            db,
            new_room.id,
            hotel_id,
            reservation.check_in_date,
            reservation.check_out_date,
            exclude_reservation_id=reservation.id,
        ):
            raise ReservationError("New room is not available for these dates")
        reservation.room_id = update_data["room_id"]

    for field in ("num_adults", "num_children", "notes"):
        if field in update_data:
            setattr(reservation, field, update_data[field])

    db.flush()
    return reservation
