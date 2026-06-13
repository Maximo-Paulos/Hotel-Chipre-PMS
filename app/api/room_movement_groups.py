from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import AuthContext, require_permission
from app.schemas.room_movement_group import RoomMovementGroupRead
from app.services.permission_service import PERMISSION_RESERVATION_ROOM_MOVE
from app.services.room_movement_group_service import (
    RoomMovementGroupError,
    get_group,
    list_groups,
    revert_group,
)


router = APIRouter(prefix="/api/room-movement-groups", tags=["Room Movement Groups"])


@router.get("/", response_model=list[RoomMovementGroupRead])
@router.get("", response_model=list[RoomMovementGroupRead], include_in_schema=False)
def list_room_movement_groups(
    limit: int = 50,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_RESERVATION_ROOM_MOVE)),
):
    return list_groups(db, hotel_id=context.hotel_id, limit=limit)


@router.get("/{group_id}", response_model=RoomMovementGroupRead)
def read_room_movement_group(
    group_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_RESERVATION_ROOM_MOVE)),
):
    group = get_group(db, hotel_id=context.hotel_id, group_id=group_id)
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Movement group not found")
    return group


@router.post("/{group_id}/revert", response_model=RoomMovementGroupRead)
def revert_room_movement_group(
    group_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_RESERVATION_ROOM_MOVE)),
):
    try:
        group = revert_group(
            db,
            hotel_id=context.hotel_id,
            group_id=group_id,
            reverted_by_user_id=context.user_id,
        )
        db.commit()
        db.refresh(group)
        return group
    except RoomMovementGroupError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
