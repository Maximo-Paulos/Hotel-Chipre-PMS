"""
FastAPI routes for Check-in / Check-out.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.reservation import ReservationRead
from app.services.checkin_service import (
    perform_checkin,
    perform_checkout,
    validate_guest_for_checkin,
    CheckInError,
)
from app.models.guest import Guest
from app.dependencies.auth import get_auth_context, AuthContext

router = APIRouter(prefix="/api/checkin", tags=["Check-in"])


@router.post("/{reservation_id}", response_model=ReservationRead)
def checkin(
    reservation_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(get_auth_context),
):
    try:
        reservation = perform_checkin(db, reservation_id, hotel_id=context.hotel_id)
        db.commit()
        db.refresh(reservation)
        result = ReservationRead.model_validate(reservation)
        result.balance_due = reservation.balance_due
        result.nights = reservation.nights
        return result
    except CheckInError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/checkout/{reservation_id}", response_model=ReservationRead)
def checkout(
    reservation_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(get_auth_context),
):
    try:
        reservation = perform_checkout(db, reservation_id, hotel_id=context.hotel_id)
        db.commit()
        db.refresh(reservation)
        result = ReservationRead.model_validate(reservation)
        result.balance_due = reservation.balance_due
        result.nights = reservation.nights
        return result
    except CheckInError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/validate/{guest_id}")
def validate_guest(
    guest_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(get_auth_context),
):
    guest = db.query(Guest).filter(Guest.id == guest_id).first()
    if not guest:
        raise HTTPException(status_code=404, detail="Guest not found")
    errors = validate_guest_for_checkin(db, guest, hotel_id=context.hotel_id)
    return {
        "guest_id": guest_id,
        "valid": len(errors) == 0,
        "errors": errors,
    }
