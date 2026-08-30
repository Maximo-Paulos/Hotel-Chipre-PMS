"""API routes for reservation waitlist operations."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import AuthContext, require_all_permissions, require_permission
from app.models.waitlist import WaitlistStatusEnum
from app.schemas.waitlist import (
    WaitlistEntryCreate,
    WaitlistEntryRead,
    WaitlistEntryUpdate,
    WaitlistPromoteRequest,
    WaitlistPromoteResponse,
)
from app.services.permission_service import PERMISSION_RESERVATION_CREATE, PERMISSION_WAITLIST_VIEW
from app.services.waitlist_service import (
    WaitlistError,
    add_to_waitlist,
    cancel_waitlist_entry,
    expire_waitlist_entry,
    get_waitlist_entry,
    list_waitlist_entries,
    promote_from_waitlist,
    update_waitlist_entry,
)
from app.api.reservations import _to_read as _reservation_to_read


router = APIRouter(prefix="/api/waitlist", tags=["Waitlist"])


@router.post("/", response_model=WaitlistEntryRead, status_code=status.HTTP_201_CREATED)
@router.post("", response_model=WaitlistEntryRead, status_code=status.HTTP_201_CREATED, include_in_schema=False)
def create_waitlist_entry(
    payload: WaitlistEntryCreate,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_RESERVATION_CREATE)),
):
    try:
        entry = add_to_waitlist(db, context.hotel_id, payload)
        db.commit()
        db.refresh(entry)
        return entry
    except WaitlistError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/", response_model=list[WaitlistEntryRead])
@router.get("", response_model=list[WaitlistEntryRead], include_in_schema=False)
def list_waitlist(
    status_filter: WaitlistStatusEnum | None = None,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_all_permissions(PERMISSION_RESERVATION_CREATE, PERMISSION_WAITLIST_VIEW)),
):
    return list_waitlist_entries(db, context.hotel_id, status_filter=status_filter)


@router.get("/{entry_id}", response_model=WaitlistEntryRead)
def read_waitlist_entry(
    entry_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_all_permissions(PERMISSION_RESERVATION_CREATE, PERMISSION_WAITLIST_VIEW)),
):
    try:
        return get_waitlist_entry(db, context.hotel_id, entry_id)
    except WaitlistError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.patch("/{entry_id}", response_model=WaitlistEntryRead)
def patch_waitlist_entry(
    entry_id: int,
    payload: WaitlistEntryUpdate,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_RESERVATION_CREATE)),
):
    try:
        entry = update_waitlist_entry(db, context.hotel_id, entry_id, payload)
        db.commit()
        db.refresh(entry)
        return entry
    except WaitlistError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/{entry_id}/promote", response_model=WaitlistPromoteResponse)
def promote_waitlist_entry(
    entry_id: int,
    payload: WaitlistPromoteRequest,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_RESERVATION_CREATE)),
):
    try:
        entry, reservation = promote_from_waitlist(
            db,
            context.hotel_id,
            entry_id,
            room_id=payload.room_id,
            notes=payload.notes,
        )
        db.commit()
        db.refresh(entry)
        db.refresh(reservation)
        return WaitlistPromoteResponse(waitlist_entry=entry, reservation=_reservation_to_read(reservation))
    except WaitlistError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/{entry_id}/cancel", response_model=WaitlistEntryRead)
def cancel_waitlist(
    entry_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_RESERVATION_CREATE)),
):
    try:
        entry = cancel_waitlist_entry(db, context.hotel_id, entry_id)
        db.commit()
        db.refresh(entry)
        return entry
    except WaitlistError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/{entry_id}/expire", response_model=WaitlistEntryRead)
def expire_waitlist(
    entry_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_RESERVATION_CREATE)),
):
    try:
        entry = expire_waitlist_entry(db, context.hotel_id, entry_id)
        db.commit()
        db.refresh(entry)
        return entry
    except WaitlistError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
