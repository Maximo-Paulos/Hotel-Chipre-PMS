"""
FastAPI routes for Reservations.
Complete CRUD + cancel, modify, no-show, extend stay.
"""
from datetime import date, datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.room import Room, RoomCategory
from app.models.hotel_config import HotelConfiguration
from app.schemas.reservation import ReservationCreate, ReservationRead, ReservationUpdate
from app.services.reservation_service import (
    create_reservation,
    transition_reservation_status,
    check_room_availability,
    find_available_rooms,
    ReservationError,
    list_reservations as list_reservations_service,
    get_reservation_by_id,
    update_reservation_fields,
)
from app.dependencies.auth import get_auth_context, AuthContext, require_roles

router = APIRouter(prefix="/api/reservations", tags=["Reservations"])


def _to_read(r: Reservation) -> ReservationRead:
    result = ReservationRead.model_validate(r)
    result.balance_due = r.balance_due
    result.nights = r.nights
    result.additional_guests = [
        {"id": g.id, "first_name": g.first_name, "last_name": g.last_name, "document_type": g.document_type, "document_number": g.document_number}
        for g in r.additional_guests
    ]
    return result


# Accept with and without trailing slash to avoid 405 when the FE omits it.
@router.post("/", response_model=ReservationRead, status_code=status.HTTP_201_CREATED)
@router.post("", response_model=ReservationRead, status_code=status.HTTP_201_CREATED, include_in_schema=False)
def create_new_reservation(
    data: ReservationCreate,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager", "housekeeping")),
):
    config = db.get(HotelConfiguration, context.hotel_id)
    if config and not config.subscription_active:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Suscripción inactiva. Reactivá el plan para crear nuevas reservas.",
        )
    try:
        reservation = create_reservation(db, data, hotel_id=context.hotel_id)
        db.commit()
        db.refresh(reservation)
        return _to_read(reservation)
    except ReservationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/", response_model=list[ReservationRead])
@router.get("", response_model=list[ReservationRead], include_in_schema=False)
def list_reservations(
    status_filter: str = "",
    from_date: date = None,
    to_date: date = None,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(get_auth_context),
):
    reservations = list_reservations_service(
        db, hotel_id=context.hotel_id, status_filter=status_filter, from_date=from_date, to_date=to_date
    )
    return [_to_read(r) for r in reservations]


@router.get("/{reservation_id}", response_model=ReservationRead)
def get_reservation(
    reservation_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(get_auth_context),
):
    reservation = get_reservation_by_id(db, reservation_id, context.hotel_id)
    if not reservation:
        raise HTTPException(status_code=404, detail="Reservation not found")
    return _to_read(reservation)


from app.schemas.guest import GuestCreate
from app.models.guest import Guest

@router.post("/{reservation_id}/guests", response_model=ReservationRead)
def add_reservation_guests(
    reservation_id: int,
    guests: list[GuestCreate],
    db: Session = Depends(get_db),
    context: AuthContext = Depends(get_auth_context),
):
    reservation = get_reservation_by_id(db, reservation_id, context.hotel_id)
    if not reservation:
        raise HTTPException(status_code=404, detail="Reservation not found")
        
    for guest_data in guests:
        # Check if guest already exists by DocNum
        guest = None
        if guest_data.document_number:
            guest = db.query(Guest).filter(
                Guest.document_number == guest_data.document_number,
                Guest.hotel_id == context.hotel_id,
            ).first()
        
        if not guest:
            guest = Guest(**guest_data.model_dump(exclude={"companions"}), hotel_id=context.hotel_id)
            db.add(guest)
            db.flush()
        
        # Link if not linked
        if guest not in reservation.additional_guests:
            reservation.additional_guests.append(guest)
            
    db.commit()
    db.refresh(reservation)
    return _to_read(reservation)


@router.post("/{reservation_id}/cancel", response_model=ReservationRead)
def cancel_reservation(
    reservation_id: int,
    manager_pin: str | None = None,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
):
    """Cancel a reservation. Post check-in cancellations are not allowed."""
    config = db.get(HotelConfiguration, context.hotel_id)
    if config and not config.subscription_active:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Suscripción inactiva. Reactivá el plan para gestionar reservas.",
        )
    r = get_reservation_by_id(db, reservation_id, context.hotel_id)
    if not r:
        raise HTTPException(status_code=404, detail="Reservation not found")

    if r.status in (ReservationStatusEnum.CHECKED_IN, ReservationStatusEnum.CHECKED_OUT):
        raise HTTPException(
            status_code=400,
            detail="Cannot cancel a reservation that is already checked-in or checked-out",
        )

    if r.status == ReservationStatusEnum.CANCELLED:
        raise HTTPException(status_code=400, detail="Reservation is already cancelled")
    try:
        transition_reservation_status(db, r, ReservationStatusEnum.CANCELLED, context.hotel_id)
        db.commit()
        db.refresh(r)
        return _to_read(r)
    except ReservationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{reservation_id}/noshow", response_model=ReservationRead)
def mark_no_show(
    reservation_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
):
    """Mark a reservation as no-show (cancels it). Valid when guest doesn't arrive."""
    r = get_reservation_by_id(db, reservation_id, context.hotel_id)
    if not r:
        raise HTTPException(status_code=404, detail="Reservation not found")
    if r.status in (ReservationStatusEnum.CHECKED_IN, ReservationStatusEnum.CHECKED_OUT, ReservationStatusEnum.CANCELLED):
        raise HTTPException(status_code=400, detail=f"Cannot mark no-show: reservation is '{r.status.value}'")
    try:
        r.notes = (r.notes or '') + f'\n[NO-SHOW] Marcado como no-show el {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")}'
        transition_reservation_status(db, r, ReservationStatusEnum.CANCELLED, context.hotel_id)
        db.commit()
        db.refresh(r)
        return _to_read(r)
    except ReservationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/{reservation_id}", response_model=ReservationRead)
def modify_reservation(
    reservation_id: int,
    data: ReservationUpdate,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
):
    """Modify a reservation (dates, notes, room). Only allowed for pre-check-in states."""
    config = db.get(HotelConfiguration, context.hotel_id)
    if config and not config.subscription_active:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Suscripción inactiva. Reactivá el plan para gestionar reservas.",
        )
    r = get_reservation_by_id(db, reservation_id, context.hotel_id)
    if not r:
        raise HTTPException(status_code=404, detail="Reservation not found")
    if r.status in (ReservationStatusEnum.CHECKED_IN, ReservationStatusEnum.CHECKED_OUT, ReservationStatusEnum.CANCELLED):
        raise HTTPException(status_code=400, detail=("Cannot modify: reservation is " + r.status.value))
    try:
        update_reservation_fields(db, r, data, context.hotel_id)
        db.commit()
        db.refresh(r)
        return _to_read(r)
    except ReservationError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{reservation_id}/extend", response_model=ReservationRead)
def extend_stay(
    reservation_id: int,
    new_checkout: date,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
):
    """Extend a guest's stay to a new checkout date."""
    r = get_reservation_by_id(db, reservation_id, context.hotel_id)
    if not r:
        raise HTTPException(status_code=404, detail="Reservation not found")
    if r.status not in (ReservationStatusEnum.CHECKED_IN, ReservationStatusEnum.FULLY_PAID):
        raise HTTPException(status_code=400, detail=f"Can only extend stays that are checked-in or fully paid, got '{r.status.value}'")
    if new_checkout <= r.check_out_date:
        raise HTTPException(status_code=400, detail="New checkout must be after current checkout")
    if r.room_id and not check_room_availability(
        db,
        r.room_id,
        r.check_out_date,
        new_checkout,
        hotel_id=context.hotel_id,
        exclude_reservation_id=r.id,
    ):
        raise HTTPException(status_code=400, detail="Room is not available for the extended dates")

    category = db.query(RoomCategory).filter(RoomCategory.id == r.category_id).first()
    extra_nights = (new_checkout - r.check_out_date).days
    r.check_out_date = new_checkout
    r.total_amount = round(r.total_amount + extra_nights * category.base_price_per_night, 2)
    r.notes = (r.notes or '') + f"\n[EXTENSION] +{extra_nights} noches hasta {new_checkout}"

    if r.balance_due > 0 and r.status == ReservationStatusEnum.FULLY_PAID:
        r.status = ReservationStatusEnum.DEPOSIT_PAID

    db.commit()
    db.refresh(r)
    return _to_read(r)
