from __future__ import annotations

from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import AuthContext, require_roles
from app.models.room import Room
from app.models.room_block import RoomBlock, RoomBlockReasonEnum
from app.models.user import User
from app.services.room_block_service import (
    ProtectedReservationConflictError,
    RoomBlockError,
    create_block,
    resolve_block,
)


router = APIRouter(prefix="/api", tags=["Room Blocks"])


class RoomBlockCreate(BaseModel):
    start_date: date
    end_date: date | None = None
    reason: str = Field(..., min_length=1, max_length=200)


class RoomBlockRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    hotel_id: int
    room_id: int
    start_date: date
    end_date: date | None = None
    reason: str
    is_active: bool
    created_by_user_id: int | None = None
    created_at: datetime
    released_at: datetime | None = None
    released_by_user_id: int | None = None


def _validate_block_dates(start: date, end: date | None) -> None:
    if end is not None and end < start:
        raise HTTPException(status_code=422, detail="end_date must be greater than or equal to start_date")


def _exclusive_end(end: date | None) -> date | None:
    return end + timedelta(days=1) if end is not None else None


def _inclusive_end(ends_at: date | None) -> date | None:
    return ends_at - timedelta(days=1) if ends_at is not None else None


def _existing_user_id(db: Session, user_id: int | None) -> int | None:
    if user_id is None:
        return None
    return user_id if db.get(User, user_id) is not None else None


def _read_block(block: RoomBlock) -> RoomBlockRead:
    return RoomBlockRead(
        id=block.id,
        hotel_id=block.hotel_id,
        room_id=block.room_id,
        start_date=block.starts_at,
        end_date=_inclusive_end(block.ends_at),
        reason=block.reason_note or block.reason_code.value,
        is_active=block.resolved_at is None,
        created_by_user_id=block.created_by_user_id,
        created_at=block.created_at,
        released_at=block.resolved_at,
        released_by_user_id=block.resolved_by_user_id,
    )


@router.post("/rooms/{room_id}/blocks", status_code=status.HTTP_201_CREATED)
def create_room_block(
    room_id: int,
    payload: RoomBlockCreate,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("receptionist", "manager", "owner", "co_owner")),
):
    _validate_block_dates(payload.start_date, payload.end_date)
    room = db.query(Room).filter(Room.id == room_id, Room.hotel_id == context.hotel_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    try:
        create_block(
            db,
            hotel_id=context.hotel_id,
            room_id=room_id,
            starts_at=payload.start_date,
            ends_at=_exclusive_end(payload.end_date),
            is_indefinite=payload.end_date is None,
            reason_code=RoomBlockReasonEnum.OTHER,
            reason_note=payload.reason,
            created_by_user_id=_existing_user_id(db, context.user_id),
        )
    except ProtectedReservationConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "blocked": False,
                "moved_reservations": [],
                "conflicts": [
                    {"reservation_id": reservation_id, "reason": "protected"}
                    for reservation_id in exc.reservation_ids
                ],
            },
        ) from exc
    except RoomBlockError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    db.commit()
    return {"blocked": True, "moved_reservations": [], "conflicts": []}


@router.get("/rooms/{room_id}/blocks", response_model=list[RoomBlockRead])
def list_room_blocks(
    room_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("receptionist", "manager", "owner", "co_owner")),
):
    room = db.query(Room).filter(Room.id == room_id, Room.hotel_id == context.hotel_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    blocks = (
        db.query(RoomBlock)
        .filter(
            RoomBlock.hotel_id == context.hotel_id,
            RoomBlock.room_id == room_id,
            RoomBlock.resolved_at.is_(None),
        )
        .order_by(RoomBlock.starts_at.asc(), RoomBlock.id.asc())
        .all()
    )
    return [_read_block(block) for block in blocks]


@router.delete("/blocks/{block_id}")
def release_room_block(
    block_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("manager", "owner", "co_owner")),
):
    block = db.query(RoomBlock).filter(RoomBlock.id == block_id, RoomBlock.hotel_id == context.hotel_id).first()
    if not block:
        raise HTTPException(status_code=404, detail="Block not found")
    if block.resolved_at is None:
        resolve_block(
            db,
            hotel_id=context.hotel_id,
            block_id=block_id,
            resolved_by_user_id=_existing_user_id(db, context.user_id),
        )
        db.commit()
    return {"released": True, "moved_reservations": []}
