from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import AuthContext, get_auth_context, require_permission
from app.models.room_block import RoomBlockReasonEnum
from app.services.permission_service import PERMISSION_ROOM_BLOCK
from app.services.room_block_service import (
    ProtectedReservationConflictError,
    RoomBlockError,
    create_block,
    get_block,
    list_active_blocks,
    resolve_block,
)

router = APIRouter(prefix="/api/room-blocks", tags=["Room Blocks"])


class RoomBlockCreate(BaseModel):
    room_id: int
    starts_at: date
    ends_at: date | None = None
    is_indefinite: bool = False
    reason_code: RoomBlockReasonEnum = RoomBlockReasonEnum.OTHER
    reason_note: str | None = Field(default=None, max_length=500)


class RoomBlockRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    hotel_id: int
    room_id: int
    reason_code: RoomBlockReasonEnum
    reason_note: str | None = None
    starts_at: date
    ends_at: date | None = None
    is_indefinite: bool
    created_by_user_id: int | None = None
    resolved_by_user_id: int | None = None
    resolved_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


@router.post("/", response_model=RoomBlockRead, status_code=status.HTTP_201_CREATED)
def create_room_block(
    data: RoomBlockCreate,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_ROOM_BLOCK)),
):
    try:
        block = create_block(
            db,
            hotel_id=context.hotel_id,
            room_id=data.room_id,
            starts_at=data.starts_at,
            ends_at=data.ends_at,
            is_indefinite=data.is_indefinite,
            reason_code=data.reason_code,
            reason_note=data.reason_note,
            created_by_user_id=context.user_id,
        )
    except ProtectedReservationConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": str(exc), "reservation_ids": exc.reservation_ids},
        ) from exc
    except RoomBlockError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    db.commit()
    db.refresh(block)
    return block


@router.get("/", response_model=list[RoomBlockRead])
def list_room_blocks(
    start_date: date | None = None,
    end_date: date | None = None,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(get_auth_context),
):
    try:
        return list_active_blocks(db, hotel_id=context.hotel_id, start_date=start_date, end_date=end_date)
    except RoomBlockError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/{block_id}", response_model=RoomBlockRead)
def get_room_block(
    block_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(get_auth_context),
):
    try:
        return get_block(db, hotel_id=context.hotel_id, block_id=block_id)
    except RoomBlockError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/{block_id}/resolve", response_model=RoomBlockRead)
def resolve_room_block(
    block_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_ROOM_BLOCK)),
):
    try:
        block = resolve_block(
            db,
            hotel_id=context.hotel_id,
            block_id=block_id,
            resolved_by_user_id=context.user_id,
        )
    except RoomBlockError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    db.commit()
    db.refresh(block)
    return block
