from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import AuthContext, get_auth_context, require_roles
from app.models.operations import RoomMoveEvent, RoomMovementGroup
from app.services.room_movement_group_service import (
    RoomMovementGroupError,
    get_group,
    list_groups,
    revert_group,
)


router = APIRouter(prefix="/api/movement-groups", tags=["Movement Groups"])


class MovementEventRead(BaseModel):
    id: int
    hotel_id: int
    reservation_id: int
    movement_group_id: int | None
    from_room_id: int | None
    to_room_id: int | None
    move_type: str
    reason_code: str | None
    reason_note: str | None
    trigger_event: str | None
    state_before: str | None
    state_after: str | None
    notes: str | None
    occurred_at: datetime
    created_by_user_id: int | None


class MovementGroupRead(BaseModel):
    id: int
    hotel_id: int
    trigger_reason: str
    notes: str | None
    is_reverted: bool
    reverted_by_user_id: int | None
    reverted_at: datetime | None
    created_by_user_id: int | None
    created_at: datetime
    movements: list[MovementEventRead]


def _enum_value(value) -> str | None:
    if value is None:
        return None
    return value.value if hasattr(value, "value") else str(value)


def _event_to_read(event: RoomMoveEvent) -> MovementEventRead:
    return MovementEventRead(
        id=event.id,
        hotel_id=event.hotel_id,
        reservation_id=event.reservation_id,
        movement_group_id=event.movement_group_id,
        from_room_id=event.from_room_id,
        to_room_id=event.to_room_id,
        move_type=_enum_value(event.move_type) or "",
        reason_code=event.reason_code,
        reason_note=event.reason_note,
        trigger_event=event.trigger_event,
        state_before=event.state_before,
        state_after=event.state_after,
        notes=event.notes,
        occurred_at=event.occurred_at,
        created_by_user_id=event.created_by_user_id,
    )


def _group_to_read(group: RoomMovementGroup) -> MovementGroupRead:
    return MovementGroupRead(
        id=group.id,
        hotel_id=group.hotel_id,
        trigger_reason=group.trigger_reason,
        notes=group.notes,
        is_reverted=group.is_reverted,
        reverted_by_user_id=group.reverted_by_user_id,
        reverted_at=group.reverted_at,
        created_by_user_id=group.created_by_user_id,
        created_at=group.created_at,
        movements=[_event_to_read(event) for event in group.move_events],
    )


def _not_found_or_bad_request(exc: RoomMovementGroupError) -> HTTPException:
    status_code = status.HTTP_404_NOT_FOUND if "not found" in str(exc).lower() else status.HTTP_400_BAD_REQUEST
    return HTTPException(status_code=status_code, detail=str(exc))


@router.get("/", response_model=list[MovementGroupRead])
@router.get("", response_model=list[MovementGroupRead], include_in_schema=False)
def list_movement_groups(
    limit: int = 50,
    trigger_reason: str | None = None,
    is_reverted: bool | None = None,
    reservation_id: int | None = None,
    created_by_user_id: int | None = None,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(get_auth_context),
):
    if (
        trigger_reason is None
        and is_reverted is None
        and reservation_id is None
        and created_by_user_id is None
    ):
        return [_group_to_read(group) for group in list_groups(db, hotel_id=context.hotel_id, limit=limit)]

    safe_limit = max(1, min(limit, 200))
    query = db.query(RoomMovementGroup).filter(RoomMovementGroup.hotel_id == context.hotel_id)
    if trigger_reason is not None:
        query = query.filter(RoomMovementGroup.trigger_reason == trigger_reason)
    if is_reverted is not None:
        query = query.filter(RoomMovementGroup.is_reverted == is_reverted)
    if created_by_user_id is not None:
        query = query.filter(RoomMovementGroup.created_by_user_id == created_by_user_id)
    if reservation_id is not None:
        query = query.join(RoomMoveEvent).filter(
            RoomMoveEvent.hotel_id == context.hotel_id,
            RoomMoveEvent.reservation_id == reservation_id,
        )

    groups = (
        query.order_by(RoomMovementGroup.created_at.desc(), RoomMovementGroup.id.desc())
        .distinct()
        .limit(safe_limit)
        .all()
    )
    return [_group_to_read(group) for group in groups]


@router.get("/{group_id}", response_model=MovementGroupRead)
def read_movement_group(
    group_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(get_auth_context),
):
    group = get_group(db, hotel_id=context.hotel_id, group_id=group_id)
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Movement group not found")
    return _group_to_read(group)


@router.post("/{group_id}/revert", response_model=MovementGroupRead)
def revert_movement_group(
    group_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
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
        return _group_to_read(group)
    except RoomMovementGroupError as exc:
        db.rollback()
        raise _not_found_or_bad_request(exc) from exc
