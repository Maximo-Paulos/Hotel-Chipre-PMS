"""
FastAPI routes for Check-in / Check-out.
"""
from fastapi import APIRouter, Body, Depends, HTTPException, status
from pydantic import BaseModel
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
from app.dependencies.auth import get_auth_context, AuthContext, require_permission
from app.services.permission_service import (
    PERMISSION_CHECKIN_OVERRIDE_PROHIBIDO,
    PERMISSION_CHECKIN_PERFORM,
    audit_permission_denied,
    resolve,
)

router = APIRouter(prefix="/api/checkin", tags=["Check-in"])


class CheckInRequest(BaseModel):
    override_prohibido: bool = False


@router.post("/{reservation_id}", response_model=ReservationRead)
def checkin(
    reservation_id: int,
    request: CheckInRequest | None = Body(default=None),
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_CHECKIN_PERFORM)),
):
    override_prohibido = bool(request.override_prohibido) if request else False
    if override_prohibido and not resolve(
        db,
        context.hotel_id,
        context.user_role,
        PERMISSION_CHECKIN_OVERRIDE_PROHIBIDO,
    ):
        audit_permission_denied(
            db,
            hotel_id=context.hotel_id,
            user_id=context.user_id,
            role=context.user_role,
            permission_code=PERMISSION_CHECKIN_OVERRIDE_PROHIBIDO,
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tenes permisos para esta accion")

    try:
        reservation = perform_checkin(
            db,
            reservation_id,
            hotel_id=context.hotel_id,
            override_prohibido=override_prohibido,
            override_user_id=context.user_id if override_prohibido else None,
        )
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
    force: bool = False,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_CHECKIN_PERFORM)),
):
    try:
        reservation = perform_checkout(db, reservation_id, hotel_id=context.hotel_id, force=force)
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
    guest = (
        db.query(Guest)
        .filter(Guest.id == guest_id, Guest.hotel_id == context.hotel_id)
        .first()
    )
    if not guest:
        raise HTTPException(status_code=404, detail="Guest not found")
    errors = validate_guest_for_checkin(db, guest, context.hotel_id)
    return {
        "guest_id": guest_id,
        "valid": len(errors) == 0,
        "errors": errors,
    }
