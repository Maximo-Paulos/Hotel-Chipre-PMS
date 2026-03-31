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
from app.models.room import Room, RoomStatusEnum


class CheckInError(Exception):
    """Custom exception for check-in validation errors."""
    pass


def validate_guest_for_checkin(
    db: Session,
    guest: Guest,
    config: HotelConfiguration | None = None,
) -> list[str]:
    """
    Validate that a guest has all required data for check-in.
    Returns a list of missing field descriptions (empty = valid).
    """
    if config is None:
        config = db.query(HotelConfiguration).filter(HotelConfiguration.id == 1).first()

    errors: list[str] = []

    # Always required: name
    if not guest.first_name or not guest.first_name.strip():
        errors.append("First name is required")
    if not guest.last_name or not guest.last_name.strip():
        errors.append("Last name is required")

    # Document requirement (configurable)
    if config and config.require_document_for_checkin:
        if not guest.document_type or not guest.document_type.strip():
            errors.append("Document type (DNI/Passport) is required")
        if not guest.document_number or not guest.document_number.strip():
            errors.append("Document number is required")

    # Terms acceptance (configurable)
    if config and config.require_terms_acceptance:
        if not guest.terms_accepted:
            errors.append("Guest must accept terms and conditions")

    return errors


def perform_checkin(
    db: Session,
    reservation_id: int,
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
    reservation = db.query(Reservation).filter(
        Reservation.id == reservation_id
    ).first()

    if not reservation:
        raise CheckInError(f"Reservation {reservation_id} not found")

    # Must be fully paid to check in
    if reservation.status != ReservationStatusEnum.FULLY_PAID:
        raise CheckInError(
            f"Cannot check in: reservation status is '{reservation.status.value}'. "
            f"Must be 'fully_paid'. Outstanding balance: ${reservation.balance_due:.2f}"
        )

    # Load guest
    guest = db.query(Guest).filter(Guest.id == reservation.guest_id).first()
    if not guest:
        raise CheckInError("Guest record not found for this reservation")

    # Validate guest data
    config = db.query(HotelConfiguration).filter(HotelConfiguration.id == 1).first()
    validation_errors = validate_guest_for_checkin(db, guest, config)

    if validation_errors:
        raise CheckInError(
            f"Check-in blocked — missing required guest data: {'; '.join(validation_errors)}"
        )

    # All validations passed — perform check-in
    try:
        transition_reservation_status(db, reservation, ReservationStatusEnum.CHECKED_IN)
    except ReservationError as e:
        raise CheckInError(str(e))

    reservation.actual_check_in = datetime.now(timezone.utc)
    # Mark room as occupied for housekeeping dashboard
    if reservation.room_id is not None:
        room = db.query(Room).filter(Room.id == reservation.room_id).first()
        if room:
            room.status = RoomStatusEnum.OCCUPIED
    db.flush()

    return reservation


def perform_checkout(
    db: Session,
    reservation_id: int,
) -> Reservation:
    """
    Check-out process:
    1. Verify reservation is in 'checked_in' status
    2. Verify no outstanding balance (optional: allow checkout with balance)
    3. Transition to checked_out
    4. Record actual check-out timestamp
    """
    reservation = db.query(Reservation).filter(
        Reservation.id == reservation_id
    ).first()

    if not reservation:
        raise CheckInError(f"Reservation {reservation_id} not found")

    if reservation.status != ReservationStatusEnum.CHECKED_IN:
        raise CheckInError(
            f"Cannot check out: reservation status is '{reservation.status.value}'. "
            f"Must be 'checked_in'."
        )

    # Transition
    try:
        transition_reservation_status(db, reservation, ReservationStatusEnum.CHECKED_OUT)
    except ReservationError as e:
        raise CheckInError(str(e))

    reservation.actual_check_out = datetime.now(timezone.utc)
    
    # Mark room for cleaning
    if reservation.room_id is not None:
        room = db.query(Room).filter(Room.id == reservation.room_id).first()
        if room:
            room.status = RoomStatusEnum.CLEANING
            
    db.flush()

    return reservation
