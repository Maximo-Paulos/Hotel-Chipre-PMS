from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import AuthContext, require_any_permission, require_permission
from app.models.room_block import RoomBlockReasonEnum
from app.services.permission_service import (
    PERMISSION_ROOM_READ,
    PERMISSION_ROOM_BLOCK_CREATE,
    PERMISSION_ROOM_BLOCK_RELEASE,
)
from app.services.room_block_service import (
    ProtectedReservationConflictError,
    RoomBlockExtensionConflictError,
    RoomBlockReleaseConflictError,
    RoomBlockError,
    create_block,
    extend_block,
    get_block,
    list_active_blocks,
    preview_block_extension,
    preview_block_conflicts,
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


class RoomBlockConflictPreview(BaseModel):
    reservation_count: int
    protected_reservation_count: int


class RoomBlockExtensionConflictPreview(BaseModel):
    reservation_count: int
    protected_reservation_count: int
    overlapping_block_count: int


class RoomBlockExtensionInput(BaseModel):
    ends_at: date


@router.post("/", response_model=RoomBlockRead, status_code=status.HTTP_201_CREATED)
def create_room_block(
    data: RoomBlockCreate,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_ROOM_BLOCK_CREATE)),
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
    context: AuthContext = Depends(
        require_any_permission(PERMISSION_ROOM_READ, PERMISSION_ROOM_BLOCK_CREATE, PERMISSION_ROOM_BLOCK_RELEASE)
    ),
):
    try:
        blocks = list_active_blocks(db, hotel_id=context.hotel_id, start_date=start_date, end_date=end_date)
        if context.operational_role == "housekeeping":
            visible_reasons = {RoomBlockReasonEnum.MAINTENANCE, RoomBlockReasonEnum.DEEP_CLEANING}
            blocks = [block for block in blocks if block.reason_code in visible_reasons]
        return blocks
    except RoomBlockError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/conflicts/preview", response_model=RoomBlockConflictPreview)
def preview_room_block_conflicts_endpoint(
    room_id: int,
    starts_at: date,
    ends_at: date | None = None,
    is_indefinite: bool = False,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_ROOM_BLOCK_CREATE)),
):
    """Return counts only; guest identity and reservation IDs are not needed for this warning."""
    try:
        return preview_block_conflicts(
            db,
            hotel_id=context.hotel_id,
            room_id=room_id,
            starts_at=starts_at,
            ends_at=ends_at,
            is_indefinite=is_indefinite,
        )
    except RoomBlockError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/{block_id}", response_model=RoomBlockRead)
def get_room_block(
    block_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(
        require_any_permission(PERMISSION_ROOM_READ, PERMISSION_ROOM_BLOCK_CREATE, PERMISSION_ROOM_BLOCK_RELEASE)
    ),
):
    try:
        return get_block(db, hotel_id=context.hotel_id, block_id=block_id)
    except RoomBlockError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/{block_id}/extend-preview", response_model=RoomBlockExtensionConflictPreview)
def preview_room_block_extension_endpoint(
    block_id: int,
    ends_at: date,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_ROOM_BLOCK_CREATE)),
):
    try:
        return preview_block_extension(db, hotel_id=context.hotel_id, block_id=block_id, ends_at=ends_at)
    except RoomBlockError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/{block_id}/extend", response_model=RoomBlockRead)
def extend_room_block(
    block_id: int,
    data: RoomBlockExtensionInput,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_ROOM_BLOCK_CREATE)),
):
    try:
        block = extend_block(db, hotel_id=context.hotel_id, block_id=block_id, ends_at=data.ends_at)
    except RoomBlockExtensionConflictError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": str(exc),
                "protected_reservation_count": exc.protected_reservation_count,
                "overlapping_block_count": exc.overlapping_block_count,
            },
        ) from exc
    except RoomBlockError as exc:
        db.rollback()
        code = status.HTTP_404_NOT_FOUND if str(exc) == "Room block not found" else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=code, detail=str(exc)) from exc
    db.commit()
    db.refresh(block)
    return block


@router.post("/{block_id}/resolve", response_model=RoomBlockRead)
def resolve_room_block(
    block_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_ROOM_BLOCK_RELEASE)),
):
    try:
        block = resolve_block(
            db,
            hotel_id=context.hotel_id,
            block_id=block_id,
            resolved_by_user_id=context.user_id,
        )
    except RoomBlockReleaseConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": str(exc),
                "reservation_ids": exc.reservation_ids,
                "other_block_ids": exc.other_block_ids,
            },
        ) from exc
    except RoomBlockError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    db.commit()
    db.refresh(block)
    return block
