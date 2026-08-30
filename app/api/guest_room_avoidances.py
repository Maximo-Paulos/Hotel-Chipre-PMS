"""Read and resolve the guest room-rejection lifecycle."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import AuthContext, require_permission
from app.schemas.guest_room_avoidance import (
    GuestRoomAvoidanceRead,
    GuestRoomAvoidanceResolveRequest,
)
from app.services.guest_room_avoidance_service import (
    GuestRoomAvoidanceConflictError,
    GuestRoomAvoidanceNotFoundError,
    get_active_guest_room_avoidances,
    resolve_guest_room_avoidance,
)
from app.services.permission_service import (
    PERMISSION_GUEST_READ,
    PERMISSION_GUEST_ROOM_AVOIDANCE_RESOLVE,
)


router = APIRouter(prefix="/api/guests", tags=["Guest Room Avoidances"])


@router.get("/{guest_id}/room-avoidances", response_model=list[GuestRoomAvoidanceRead])
def list_active_room_avoidances(
    guest_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_GUEST_READ)),
):
    try:
        return get_active_guest_room_avoidances(db, hotel_id=context.hotel_id, guest_id=guest_id)
    except GuestRoomAvoidanceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(
    "/{guest_id}/room-avoidances/{avoidance_id}/resolve",
    response_model=GuestRoomAvoidanceRead,
)
def resolve_room_avoidance(
    guest_id: int,
    avoidance_id: int,
    data: GuestRoomAvoidanceResolveRequest,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_GUEST_ROOM_AVOIDANCE_RESOLVE)),
):
    try:
        avoidance = resolve_guest_room_avoidance(
            db,
            hotel_id=context.hotel_id,
            guest_id=guest_id,
            avoidance_id=avoidance_id,
            resolved_by_user_id=context.user_id,
            resolution_note=data.resolution_note,
        )
    except GuestRoomAvoidanceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except GuestRoomAvoidanceConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    db.commit()
    db.refresh(avoidance)
    return avoidance
