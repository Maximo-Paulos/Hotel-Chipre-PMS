"""
Check-in Service.
Manages the deep guest check-in flow:
  1. Validates all required guest data (document, terms acceptance, etc.)
  2. Ensures reservation is fully_paid before check-in
  3. Records actual check-in time
  4. Transitions status to checked_in
  5. Also handles check-out flow
"""
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.guest import Guest
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.hotel_config import HotelConfiguration
from app.services.reservation_service import transition_reservation_status, ReservationError
from app.services.jurisdiction_profile import compute_missing_guest_fields
from app.models.room import Room, RoomStatusEnum
from app.services.guest_profile import get_guest_profile, validate_primary_guest_record


class CheckInError(Exception):
    """Custom exception for check-in validation errors."""
    pass


def _resolve_jurisdiction_code(config: HotelConfiguration | None) -> str:
    if not config:
        return "AR"
    extra_policies = config.get_extra_policies()
    return str(extra_policies.get("jurisdiction_code") or "AR").strip().upper()


def validate_guest_for_checkin(
    db: Session,
    guest: Guest,
    config_or_hotel: HotelConfiguration | int | None = None,
    reservation: Reservation | None = None,
) -> list[str]:
    """
    Validate that a guest has all required data for check-in.
    Returns a list of missing field descriptions (empty = valid).
    """
    config: HotelConfiguration | None
    if isinstance(config_or_hotel, HotelConfiguration):
        config = config_or_hotel
        hotel_id = config.id
    else:
        if config_or_hotel is None:
            raise CheckInError("hotel_id is required for check-in validation")
        hotel_id = config_or_hotel
        config = db.query(HotelConfiguration).filter(HotelConfiguration.id == hotel_id).first()

    return compute_missing_guest_fields(
        guest,
        jurisdiction_code=_resolve_jurisdiction_code(config),
        require_document=bool(config.require_document_for_checkin) if config else False,
        require_terms=bool(config.require_terms_acceptance) if config else False,
    )


def perform_checkin(
    db: Session,
    reservation_id: int,
    hotel_id: int | None = None,
) -> Reservation:
    """
    Full check-in process:
    1. Load reservation with guest data
    2. Verify reservation is in 'fully_paid' status
    3. Validate guest identity documents
    4. Transition to checked_in
    5. Record actual check-in timestamp
    
    Raises CheckInError with descriptive messages on failure.
    """
    reservation_q = db.query(Reservation).filter(Reservation.id == reservation_id)
    if hotel_id is not None:
        reservation_q = reservation_q.filter(Reservation.hotel_id == hotel_id)
    reservation = reservation_q.first()

    if not reservation:
        raise CheckInError(f"Reservation {reservation_id} not found")

    hotel_id = reservation.hotel_id or hotel_id
    if hotel_id is None:
        raise CheckInError("hotel_id is required for check-in")
    reservation.hotel_id = hotel_id

    # Must be fully paid to check in
    if reservation.status != ReservationStatusEnum.FULLY_PAID:
        raise CheckInError(
            f"Cannot check in: reservation status is '{reservation.status.value}'. "
            f"Must be 'fully_paid'. Outstanding balance: ${reservation.balance_due:.2f}"
        )

    # Load guest
    guest = db.query(Guest).filter(Guest.id == reservation.guest_id, Guest.hotel_id == hotel_id).first()
    if not guest:
        raise CheckInError("Guest record not found for this reservation")

    # Validate guest data
    config = db.query(HotelConfiguration).filter(HotelConfiguration.id == hotel_id).first()
    validation_errors = validate_guest_for_checkin(db, guest, config or hotel_id, reservation=reservation)

    if validation_errors:
        raise CheckInError(
            f"Check-in blocked — missing required guest data: {'; '.join(validation_errors)}"
        )

    # All validations passed — perform check-in
    try:
        transition_reservation_status(db, reservation, ReservationStatusEnum.CHECKED_IN, hotel_id)
    except ReservationError as e:
        raise CheckInError(str(e))

    reservation.actual_check_in = datetime.now(timezone.utc)
    # Mark room as occupied for housekeeping dashboard
    if reservation.room_id is not None:
        room = db.query(Room).filter(Room.id == reservation.room_id, Room.hotel_id == hotel_id).first()
        if room:
            room.status = RoomStatusEnum.OCCUPIED
    db.flush()

    return reservation


def perform_checkout(
    db: Session,
    reservation_id: int,
    hotel_id: int | None = None,
) -> Reservation:
    """
    Check-out process:
    1. Verify reservation is in 'checked_in' status
    2. Verify no outstanding balance (optional: allow checkout with balance)
    3. Transition to checked_out
    4. Record actual check-out timestamp
    """
    reservation_q = db.query(Reservation).filter(Reservation.id == reservation_id)
    if hotel_id is not None:
        reservation_q = reservation_q.filter(Reservation.hotel_id == hotel_id)
    reservation = reservation_q.first()

    if not reservation:
        raise CheckInError(f"Reservation {reservation_id} not found")

    hotel_id = reservation.hotel_id or hotel_id
    if hotel_id is None:
        raise CheckInError("hotel_id is required for check-out")
    reservation.hotel_id = hotel_id

    if reservation.status != ReservationStatusEnum.CHECKED_IN:
        raise CheckInError(
            f"Cannot check out: reservation status is '{reservation.status.value}'. "
            f"Must be 'checked_in'."
        )

    # Transition
    try:
        transition_reservation_status(db, reservation, ReservationStatusEnum.CHECKED_OUT, hotel_id)
    except ReservationError as e:
        raise CheckInError(str(e))

    reservation.actual_check_out = datetime.now(timezone.utc)
    
    # Mark room for cleaning
    if reservation.room_id is not None:
        room = db.query(Room).filter(Room.id == reservation.room_id, Room.hotel_id == hotel_id).first()
        if room:
            room.status = RoomStatusEnum.CLEANING
            
    db.flush()

    return reservation
