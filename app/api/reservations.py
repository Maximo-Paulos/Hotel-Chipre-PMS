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
from app.schemas.reservation import ReservationCreate, ReservationRead, ReservationUpdate
from app.services.reservation_service import (
    create_reservation,
    transition_reservation_status,
    check_room_availability,
    find_available_rooms,
    ReservationError,
)

router = APIRouter(prefix="/api/reservations", tags=["Reservations"])


def _to_read(r: Reservation) -> ReservationRead:
    result = ReservationRead.model_validate(r)
    result.balance_due = r.balance_due
    result.nights = r.nights
    return result


@router.post("/", response_model=ReservationRead, status_code=status.HTTP_201_CREATED)
def create_new_reservation(data: ReservationCreate, db: Session = Depends(get_db)):
    try:
        reservation = create_reservation(db, data)
        db.commit()
        db.refresh(reservation)
        return _to_read(reservation)
    except ReservationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/", response_model=list[ReservationRead])
def list_reservations(
    status_filter: str = "",
    from_date: date = None,
    to_date: date = None,
    db: Session = Depends(get_db),
):
    query = db.query(Reservation)
    if status_filter:
        query = query.filter(Reservation.status == status_filter)
    if from_date:
        query = query.filter(Reservation.check_in_date >= from_date)
    if to_date:
        query = query.filter(Reservation.check_out_date <= to_date)
    reservations = query.order_by(Reservation.check_in_date).all()
    return [_to_read(r) for r in reservations]


@router.get("/{reservation_id}", response_model=ReservationRead)
def get_reservation(reservation_id: int, db: Session = Depends(get_db)):
    r = db.query(Reservation).filter(Reservation.id == reservation_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Reservation not found")
    return _to_read(r)


@router.post("/{reservation_id}/cancel", response_model=ReservationRead)
def cancel_reservation(reservation_id: int, db: Session = Depends(get_db)):
    """Cancel a reservation. Only allowed for pre-check-in states."""
    r = db.query(Reservation).filter(Reservation.id == reservation_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Reservation not found")
    if r.status in (ReservationStatusEnum.CHECKED_IN, ReservationStatusEnum.CHECKED_OUT):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel: reservation is '{r.status.value}'. Only pre-check-in reservations can be cancelled."
        )
    if r.status == ReservationStatusEnum.CANCELLED:
        raise HTTPException(status_code=400, detail="Reservation is already cancelled")
    try:
        transition_reservation_status(db, r, ReservationStatusEnum.CANCELLED)
        db.commit()
        db.refresh(r)
        return _to_read(r)
    except ReservationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{reservation_id}/noshow", response_model=ReservationRead)
def mark_no_show(reservation_id: int, db: Session = Depends(get_db)):
    """Mark a reservation as no-show (cancels it). Valid when guest doesn't arrive."""
    r = db.query(Reservation).filter(Reservation.id == reservation_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Reservation not found")
    if r.status in (ReservationStatusEnum.CHECKED_IN, ReservationStatusEnum.CHECKED_OUT, ReservationStatusEnum.CANCELLED):
        raise HTTPException(status_code=400, detail=f"Cannot mark no-show: reservation is '{r.status.value}'")
    try:
        r.notes = (r.notes or '') + f'\n[NO-SHOW] Marcado como no-show el {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")}'
        transition_reservation_status(db, r, ReservationStatusEnum.CANCELLED)
        db.commit()
        db.refresh(r)
        return _to_read(r)
    except ReservationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/{reservation_id}", response_model=ReservationRead)
def modify_reservation(reservation_id: int, data: ReservationUpdate, db: Session = Depends(get_db)):
    """Modify a reservation (dates, notes, room). Only allowed for pre-check-in states."""
    r = db.query(Reservation).filter(Reservation.id == reservation_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Reservation not found")
    if r.status in (ReservationStatusEnum.CHECKED_IN, ReservationStatusEnum.CHECKED_OUT, ReservationStatusEnum.CANCELLED):
        raise HTTPException(status_code=400, detail=f"Cannot modify: reservation is '{r.status.value}'")

    update_data = data.model_dump(exclude_unset=True)

    # Handle date changes — recalculate total
    new_ci = update_data.get('check_in_date', r.check_in_date)
    new_co = update_data.get('check_out_date', r.check_out_date)

    if 'check_in_date' in update_data or 'check_out_date' in update_data:
        if new_co <= new_ci:
            raise HTTPException(status_code=400, detail="Check-out must be after check-in")
        nights = (new_co - new_ci).days
        category = db.query(RoomCategory).filter(RoomCategory.id == r.category_id).first()
        if r.room_id and not check_room_availability(db, r.room_id, new_ci, new_co, exclude_reservation_id=r.id):
            raise HTTPException(status_code=400, detail="Room is not available for the new dates")
        r.check_in_date = new_ci
        r.check_out_date = new_co
        r.total_amount = category.base_price_per_night * nights

    # Handle room change
    if 'room_id' in update_data and update_data['room_id'] is not None:
        new_room = db.query(Room).filter(Room.id == update_data['room_id']).first()
        if not new_room:
            raise HTTPException(status_code=400, detail="Room not found")
        if new_room.category_id != r.category_id:
            raise HTTPException(status_code=400, detail="New room must be in the same category")
        if not check_room_availability(db, new_room.id, r.check_in_date, r.check_out_date, exclude_reservation_id=r.id):
            raise HTTPException(status_code=400, detail="New room is not available for these dates")
        r.room_id = update_data['room_id']

    # Simple field updates
    for field in ('num_adults', 'num_children', 'notes'):
        if field in update_data:
            setattr(r, field, update_data[field])

    db.commit()
    db.refresh(r)
    return _to_read(r)


@router.post("/{reservation_id}/extend", response_model=ReservationRead)
def extend_stay(reservation_id: int, new_checkout: date, db: Session = Depends(get_db)):
    """Extend a guest's stay to a new checkout date."""
    r = db.query(Reservation).filter(Reservation.id == reservation_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Reservation not found")
    if r.status not in (ReservationStatusEnum.CHECKED_IN, ReservationStatusEnum.FULLY_PAID):
        raise HTTPException(status_code=400, detail=f"Can only extend stays that are checked-in or fully paid, got '{r.status.value}'")
    if new_checkout <= r.check_out_date:
        raise HTTPException(status_code=400, detail="New checkout must be after current checkout")
    if r.room_id and not check_room_availability(db, r.room_id, r.check_out_date, new_checkout, exclude_reservation_id=r.id):
        raise HTTPException(status_code=400, detail="Room is not available for the extended dates")

    category = db.query(RoomCategory).filter(RoomCategory.id == r.category_id).first()
    extra_nights = (new_checkout - r.check_out_date).days
    r.check_out_date = new_checkout
    r.total_amount = round(r.total_amount + extra_nights * category.base_price_per_night, 2)
    r.notes = (r.notes or '') + f'\n[EXTENSIÓN] +{extra_nights} noches hasta {new_checkout}'

    # If was fully_paid or checked_in and now has balance, transition back appropriately
    if r.balance_due > 0 and r.status == ReservationStatusEnum.FULLY_PAID:
        r.status = ReservationStatusEnum.DEPOSIT_PAID

    db.commit()
    db.refresh(r)
    return _to_read(r)
