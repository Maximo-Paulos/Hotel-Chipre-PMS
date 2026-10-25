import json
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import (
    AuthContext,
    require_all_permissions,
    require_any_permission,
    require_permission,
)
from app.models.room_block import RoomBlockReasonEnum
from app.schemas.allocation_policy import (
    AllocationAssignmentRead,
    AllocationExplanationRead,
    AllocationRunDetailRead,
    SolverMetricRead,
)
from app.services.permission_service import (
    PERMISSION_RESERVATION_MOVE,
    PERMISSION_ROOM_BLOCK_CREATE,
    PERMISSION_ROOM_BLOCK_RELEASE,
    PERMISSION_ROOM_READ,
)
from app.services.room_block_service import (
    ProtectedReservationConflictError,
    RoomBlockAlreadyExistsError,
    RoomBlockError,
    RoomBlockExtensionConflictError,
    RoomBlockReleaseConflictError,
    RoomBlockReservationConflictError,
    create_block_with_allocation_plan,
    extend_block_with_allocation_plan,
    get_block,
    get_block_conflicting_reservation_ids,
    list_active_blocks,
    preview_block_conflicts,
    preview_block_extension,
    propose_room_block_extension_reassignment,
    propose_room_block_reassignment,
    resolve_block,
)

router = APIRouter(prefix="/api/room-blocks", tags=["Room Blocks"])


def _serialize_allocation_run_details(details) -> AllocationRunDetailRead:
    assignment_sources = {
        item.reservation_id: _json_dict(item.details_json).get("source_room_id")
        for item in details.explanations
        if item.explanation_type == "assignment"
    }
    run = details.run
    return AllocationRunDetailRead(
        run_id=run.id,
        status=run.status.value if hasattr(run.status, "value") else str(run.status),
        trigger_type=run.trigger_type,
        objective_score=run.objective_score,
        solver_summary=run.solver_summary,
        error_message=run.error_message,
        policy_version_id=run.policy_version_id,
        horizon_start=run.horizon_start,
        horizon_end=run.horizon_end,
        created_at=run.created_at,
        explanations=[
            AllocationExplanationRead(
                id=item.id,
                allocation_run_id=item.allocation_run_id,
                reservation_id=item.reservation_id,
                explanation_type=item.explanation_type,
                summary=item.summary,
                details=_json_dict(item.details_json),
                created_at=item.created_at,
            )
            for item in details.explanations
        ],
        metrics=[
            SolverMetricRead(metric_key=item.metric_key, metric_value=float(item.metric_value))
            for item in details.metrics
        ],
        assignments=[
            AllocationAssignmentRead(
                id=item.id,
                reservation_id=item.reservation_id,
                source_room_id=assignment_sources.get(item.reservation_id),
                room_id=item.room_id,
                status=item.status.value if hasattr(item.status, "value") else str(item.status),
                explanation_summary=item.explanation_summary,
            )
            for item in details.assignments
        ],
    )


def _json_dict(value: str | None) -> dict:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


class RoomBlockCreate(BaseModel):
    room_id: int
    starts_at: date
    ends_at: date | None = None
    is_indefinite: bool = False
    reason_code: RoomBlockReasonEnum = RoomBlockReasonEnum.OTHER
    reason_note: str | None = Field(default=None, max_length=500)
    allocation_run_id: int | None = Field(default=None, gt=0)


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


class RoomBlockAllocationPreviewRead(BaseModel):
    room_id: int
    starts_at: date
    ends_at: date | None = None
    is_indefinite: bool
    reservation_count: int
    protected_reservation_count: int
    requires_confirmation: bool
    allocation_run: AllocationRunDetailRead | None = None


class RoomBlockExtensionConflictPreview(BaseModel):
    reservation_count: int
    protected_reservation_count: int
    overlapping_block_count: int


class RoomBlockExtensionInput(BaseModel):
    ends_at: date
    allocation_run_id: int | None = Field(default=None, gt=0)


class RoomBlockExtensionAllocationPreviewRead(BaseModel):
    block_id: int
    room_id: int
    previous_ends_at: date
    ends_at: date
    reservation_count: int
    protected_reservation_count: int
    overlapping_block_count: int
    requires_confirmation: bool
    allocation_run: AllocationRunDetailRead | None = None


@router.post("/", response_model=RoomBlockRead, status_code=status.HTTP_201_CREATED)
def create_room_block(
    data: RoomBlockCreate,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(
        require_all_permissions(PERMISSION_ROOM_BLOCK_CREATE, PERMISSION_RESERVATION_MOVE)
    ),
):
    try:
        block = create_block_with_allocation_plan(
            db,
            hotel_id=context.hotel_id,
            room_id=data.room_id,
            starts_at=data.starts_at,
            ends_at=data.ends_at,
            is_indefinite=data.is_indefinite,
            reason_code=data.reason_code,
            reason_note=data.reason_note,
            created_by_user_id=context.user_id,
            allocation_run_id=data.allocation_run_id,
        )
    except ProtectedReservationConflictError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": str(exc), "reservation_ids": exc.reservation_ids},
        ) from exc
    except RoomBlockReservationConflictError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": str(exc), "reservation_ids": exc.reservation_ids},
        ) from exc
    except RoomBlockAlreadyExistsError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except RoomBlockError as exc:
        db.rollback()
        code = status.HTTP_409_CONFLICT if "proposal" in str(exc).lower() or "changed" in str(exc).lower() else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=code, detail=str(exc)) from exc
    db.commit()
    db.refresh(block)
    return block


@router.post("/allocation-preview", response_model=RoomBlockAllocationPreviewRead)
def preview_room_block_allocation(
    data: RoomBlockCreate,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(
        require_all_permissions(PERMISSION_ROOM_BLOCK_CREATE, PERMISSION_RESERVATION_MOVE)
    ),
):
    try:
        conflicts = get_block_conflicting_reservation_ids(
            db,
            hotel_id=context.hotel_id,
            room_id=data.room_id,
            starts_at=data.starts_at,
            ends_at=data.ends_at,
            is_indefinite=data.is_indefinite,
        )
        protected = preview_block_conflicts(
            db,
            hotel_id=context.hotel_id,
            room_id=data.room_id,
            starts_at=data.starts_at,
            ends_at=data.ends_at,
            is_indefinite=data.is_indefinite,
        )["protected_reservation_count"]
        allocation_run = None
        if conflicts:
            details = propose_room_block_reassignment(
                db,
                hotel_id=context.hotel_id,
                room_id=data.room_id,
                starts_at=data.starts_at,
                ends_at=data.ends_at,
                is_indefinite=data.is_indefinite,
            )
            allocation_run = _serialize_allocation_run_details(details)
        return RoomBlockAllocationPreviewRead(
            room_id=data.room_id,
            starts_at=data.starts_at,
            ends_at=data.ends_at,
            is_indefinite=data.is_indefinite,
            reservation_count=len(conflicts),
            protected_reservation_count=protected,
            requires_confirmation=bool(conflicts),
            allocation_run=allocation_run,
        )
    except (ProtectedReservationConflictError, RoomBlockReservationConflictError) as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": str(exc), "reservation_ids": exc.reservation_ids},
        ) from exc
    except RoomBlockAlreadyExistsError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except RoomBlockError as exc:
        db.rollback()
        code = status.HTTP_404_NOT_FOUND if str(exc) == "Room not found" else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=code, detail=str(exc)) from exc


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
    context: AuthContext = Depends(
        require_all_permissions(PERMISSION_ROOM_BLOCK_CREATE, PERMISSION_RESERVATION_MOVE)
    ),
):
    try:
        block = extend_block_with_allocation_plan(
            db,
            hotel_id=context.hotel_id,
            block_id=block_id,
            ends_at=data.ends_at,
            allocation_run_id=data.allocation_run_id,
            created_by_user_id=context.user_id,
        )
    except ProtectedReservationConflictError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": str(exc), "reservation_ids": exc.reservation_ids},
        ) from exc
    except RoomBlockExtensionConflictError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": str(exc),
                "reservation_count": exc.reservation_count,
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


@router.post(
    "/{block_id}/allocation-preview",
    response_model=RoomBlockExtensionAllocationPreviewRead,
)
def preview_room_block_extension_allocation(
    block_id: int,
    data: RoomBlockExtensionInput,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(
        require_all_permissions(PERMISSION_ROOM_BLOCK_CREATE, PERMISSION_RESERVATION_MOVE)
    ),
):
    try:
        block = get_block(db, hotel_id=context.hotel_id, block_id=block_id)
        conflict_preview = preview_block_extension(
            db,
            hotel_id=context.hotel_id,
            block_id=block_id,
            ends_at=data.ends_at,
        )
        if conflict_preview["overlapping_block_count"]:
            raise RoomBlockExtensionConflictError(
                reservation_count=conflict_preview["reservation_count"],
                protected_reservation_count=conflict_preview["protected_reservation_count"],
                overlapping_block_count=conflict_preview["overlapping_block_count"],
            )
        details = None
        if conflict_preview["reservation_count"]:
            details = propose_room_block_extension_reassignment(
                db,
                hotel_id=context.hotel_id,
                block_id=block_id,
                ends_at=data.ends_at,
            )
        return RoomBlockExtensionAllocationPreviewRead(
            block_id=block.id,
            room_id=block.room_id,
            previous_ends_at=block.ends_at,
            ends_at=data.ends_at,
            reservation_count=conflict_preview["reservation_count"],
            protected_reservation_count=conflict_preview["protected_reservation_count"],
            overlapping_block_count=conflict_preview["overlapping_block_count"],
            requires_confirmation=bool(conflict_preview["reservation_count"]),
            allocation_run=_serialize_allocation_run_details(details) if details else None,
        )
    except ProtectedReservationConflictError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": str(exc), "reservation_ids": exc.reservation_ids},
        ) from exc
    except RoomBlockExtensionConflictError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": str(exc),
                "reservation_count": exc.reservation_count,
                "protected_reservation_count": exc.protected_reservation_count,
                "overlapping_block_count": exc.overlapping_block_count,
            },
        ) from exc
    except RoomBlockError as exc:
        db.rollback()
        code = status.HTTP_404_NOT_FOUND if str(exc) == "Room block not found" else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=code, detail=str(exc)) from exc


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
