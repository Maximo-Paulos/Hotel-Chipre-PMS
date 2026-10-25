"""
FastAPI routes for Check-in / Check-out.
"""
from fastapi import APIRouter, Body, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import AuthContext, require_permission
from app.models.guest import Guest
from app.models.reservation import Reservation
from app.schemas.checkin import (
    ReservationGuestArrivalListRead,
    ReservationGuestArrivalMutationRead,
)
from app.schemas.guest import GuestUpdate
from app.schemas.guest_restriction import GuestRestrictionOverrideRequest
from app.schemas.reservation import ReservationRead
from app.services.checkin_service import (
    CheckInConflictError,
    CheckInError,
    CheckOutConflictError,
    list_guest_arrivals,
    perform_checkin,
    perform_checkout,
    perform_guest_checkin,
    perform_partial_checkin,
    validate_guest_for_checkin,
)
from app.services.guest_restriction_service import (
    GuestProhibitedError,
    RestrictionOverridePermissionError,
)
from app.services.permission_service import (
    PERMISSION_CHECKIN_OVERRIDE_PROHIBIDO,
    PERMISSION_CHECKIN_PERFORM,
    PERMISSION_CHECKOUT_FORCE,
    PERMISSION_CHECKOUT_PERFORM,
    PERMISSION_GUEST_READ,
    PERMISSION_RESERVATION_PROHIBITION_OVERRIDE,
    PERMISSION_RESERVATION_READ,
    audit_permission_denied,
    resolve,
)

router = APIRouter(prefix="/api/checkin", tags=["Check-in"])


class CheckInRequest(BaseModel):
    override_prohibido: bool = False
    # B3.4: lets the receptionist complete the guest's missing check-in data
    # (birth place/country, marital status, occupation, etc.) in the same
    # request that performs the check-in, instead of a bare 400 with no way
    # to fix it. Applied before validation, same transaction.
    guest: GuestUpdate | None = None
    restriction_override: GuestRestrictionOverrideRequest | None = None


def _reservation_read(reservation: Reservation) -> ReservationRead:
    response = ReservationRead.model_validate(reservation)
    response.balance_due = reservation.balance_due
    response.nights = reservation.nights
    return response


def _authorize_override(db: Session, context: AuthContext, override_prohibido: bool) -> None:
    if override_prohibido and not resolve(
        db,
        context.hotel_id,
        context.user_role,
        PERMISSION_RESERVATION_PROHIBITION_OVERRIDE,
        user_id=context.user_id,
    ):
        audit_permission_denied(
            db,
            hotel_id=context.hotel_id,
            user_id=context.user_id,
            role=context.user_role,
            # Keep the legacy requested key in the audit during the expand
            # window; audit_permission_denied also records its canonical key.
            permission_code=PERMISSION_CHECKIN_OVERRIDE_PROHIBIDO,
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tenes permisos para esta accion")


@router.post("/{reservation_id}", response_model=ReservationRead)
def checkin(
    reservation_id: int,
    request: CheckInRequest | None = Body(default=None),
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_CHECKIN_PERFORM)),
):
    override_prohibido = bool(request.override_prohibido) if request else False
    _authorize_override(db, context, override_prohibido)
    restriction_override = request.restriction_override if request else None

    try:
        reservation = perform_checkin(
            db,
            reservation_id,
            hotel_id=context.hotel_id,
            override_prohibido=override_prohibido,
            override_user_id=context.user_id if override_prohibido else None,
            guest_patch=request.guest.model_dump(exclude_unset=True) if request and request.guest else None,
            restriction_override=restriction_override,
            actor_user_id=context.user_id,
            actor_role=context.user_role,
        )
        db.commit()
        db.refresh(reservation)
        return _reservation_read(reservation)
    except CheckInConflictError as e:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(e)) from e
    except CheckInError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except GuestProhibitedError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": e.code, "message": str(e), "restriction_id": e.restriction_id},
        )
    except RestrictionOverridePermissionError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tenes permisos para esta accion")


@router.get("/{reservation_id}/guest-arrivals", response_model=ReservationGuestArrivalListRead)
def get_guest_arrivals(
    reservation_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_RESERVATION_READ)),
):
    try:
        return list_guest_arrivals(db, reservation_id, hotel_id=context.hotel_id)
    except CheckInError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/{reservation_id}/guests/{guest_id}",
    response_model=ReservationGuestArrivalMutationRead,
)
def checkin_guest(
    reservation_id: int,
    guest_id: int,
    request: CheckInRequest | None = Body(default=None),
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_CHECKIN_PERFORM)),
):
    override_prohibido = bool(request.override_prohibido) if request else False
    _authorize_override(db, context, override_prohibido)
    try:
        reservation, snapshot, already_recorded = perform_guest_checkin(
            db,
            reservation_id,
            guest_id,
            hotel_id=context.hotel_id,
            override_prohibido=override_prohibido,
            override_user_id=context.user_id if override_prohibido else None,
            guest_patch=request.guest.model_dump(exclude_unset=True) if request and request.guest else None,
            restriction_override=request.restriction_override if request else None,
            actor_user_id=context.user_id,
            actor_role=context.user_role,
        )
        guest_arrival = next(
            item for item in snapshot["arrivals"] if item["guest_id"] == guest_id
        )
        result = {
            key: value
            for key, value in snapshot.items()
            if key != "arrivals"
        }
        result["already_recorded"] = already_recorded
        result["arrival"] = guest_arrival
        db.commit()
        db.refresh(reservation)
        return result
    except CheckInConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except CheckInError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except GuestProhibitedError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": exc.code, "message": str(exc), "restriction_id": exc.restriction_id},
        ) from exc
    except RestrictionOverridePermissionError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tenes permisos para esta accion") from exc


@router.post("/{reservation_id}/partial", response_model=ReservationRead)
def checkin_partial(
    reservation_id: int,
    request: CheckInRequest | None = Body(default=None),
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_CHECKIN_PERFORM)),
):
    """B3.1: writes PRE_CHECK_IN — the 'huésped ingresó al cuarto, faltan
    acompañantes/confirmación final' step of the canonical flow."""
    override_prohibido = bool(request.override_prohibido) if request else False
    _authorize_override(db, context, override_prohibido)

    try:
        reservation = perform_partial_checkin(
            db,
            reservation_id,
            hotel_id=context.hotel_id,
            override_prohibido=override_prohibido,
            override_user_id=context.user_id if override_prohibido else None,
            guest_patch=request.guest.model_dump(exclude_unset=True) if request and request.guest else None,
        )
        db.commit()
        db.refresh(reservation)
        return _reservation_read(reservation)
    except CheckInError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/checkout/{reservation_id}", response_model=ReservationRead)
def checkout(
    reservation_id: int,
    force: bool = False,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_CHECKOUT_PERFORM)),
):
    if force and not resolve(
        db,
        context.hotel_id,
        context.user_role,
        PERMISSION_CHECKOUT_FORCE,
        user_id=context.user_id,
    ):
        audit_permission_denied(
            db,
            hotel_id=context.hotel_id,
            user_id=context.user_id,
            role=context.user_role,
            permission_code=PERMISSION_CHECKOUT_FORCE,
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tenes permisos para forzar el checkout")
    try:
        reservation = perform_checkout(
            db,
            reservation_id,
            hotel_id=context.hotel_id,
            force=force,
            actor_user_id=context.user_id,
        )
        db.commit()
        db.refresh(reservation)
        return _reservation_read(reservation)
    except CheckOutConflictError as e:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(e)) from e
    except CheckInError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/validate/{guest_id}")
def validate_guest(
    guest_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_GUEST_READ)),
):
    guest = (
        db.query(Guest)
        .filter(Guest.id == guest_id, Guest.hotel_id == context.hotel_id)
        .first()
    )
    if not guest:
        raise HTTPException(status_code=404, detail="No se encontró el huésped.")
    errors = validate_guest_for_checkin(db, guest, context.hotel_id)
    return {
        "guest_id": guest_id,
        "valid": len(errors) == 0,
        "errors": errors,
    }
