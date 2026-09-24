"""Operational task inbox and shift handoff endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import AuthContext, require_any_permission, require_permission
from app.models.operational_task import (
    OperationalTaskStatusEnum,
    OperationalTaskTypeEnum,
)
from app.schemas.operational_tasks import (
    OperationalTaskCreate,
    OperationalTaskEventRead,
    OperationalTaskRead,
    OperationalTaskUpdate,
    ShiftHandoffAcknowledge,
    ShiftHandoffCreate,
    ShiftHandoffRead,
)
from app.services.operational_task_service import (
    HandoffVersionConflict,
    OperationalTaskError,
    TaskVersionConflict,
    acknowledge_handoff,
    create_handoff,
    create_task,
    list_handoffs,
    list_tasks,
    serialize_handoff,
    serialize_task,
    task_history,
    update_task,
    validate_task_operator_scope,
)
from app.services.permission_service import (
    PERMISSION_OPERATIONAL_TASK_MANAGE,
    PERMISSION_OPERATIONAL_TASK_READ,
    PERMISSION_OPERATIONAL_TASK_REPORT,
    PERMISSION_RESERVATION_READ,
    PERMISSION_SHIFT_HANDOFF_MANAGE,
    resolve,
)


router = APIRouter(prefix="/api/operational-tasks", tags=["Operational tasks"])


def _can(db: Session, context: AuthContext, permission: str) -> bool:
    return resolve(
        db,
        context.hotel_id,
        context.user_role,
        permission,
        user_id=context.user_id,
    )


def _is_operator_scoped(db: Session, context: AuthContext, *, can_manage: bool | None = None) -> bool:
    """Match direct task access to the user's effective shared-read/manage grants."""
    if can_manage is None:
        can_manage = _can(db, context, PERMISSION_OPERATIONAL_TASK_MANAGE)
    if can_manage:
        return False
    if context.operational_role in {"housekeeping", "receptionist"}:
        return True
    return not _can(db, context, PERMISSION_OPERATIONAL_TASK_READ)


def _can_read_reservation_context(db: Session, context: AuthContext) -> bool:
    return _can(db, context, PERMISSION_RESERVATION_READ)


def _report_type_allowed(context: AuthContext, task_type: OperationalTaskTypeEnum) -> bool:
    if context.operational_role == "housekeeping":
        return task_type in {OperationalTaskTypeEnum.HOUSEKEEPING, OperationalTaskTypeEnum.MAINTENANCE}
    if context.operational_role == "receptionist":
        return task_type in {OperationalTaskTypeEnum.GENERAL, OperationalTaskTypeEnum.RECEPTION}
    return True


def _conflict(exc: TaskVersionConflict | HandoffVersionConflict) -> HTTPException:
    resource = "task" if isinstance(exc, TaskVersionConflict) else "handoff"
    current_version = exc.current_version
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={"code": f"STALE_{resource.upper()}", "message": str(exc), "current_version": current_version},
    )


@router.get("", response_model=list[OperationalTaskRead])
def get_operational_tasks(
    status_filter: OperationalTaskStatusEnum | None = Query(default=None, alias="status"),
    task_type: OperationalTaskTypeEnum | None = None,
    room_id: int | None = Query(default=None, gt=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    context: AuthContext = Depends(
        require_any_permission(PERMISSION_OPERATIONAL_TASK_READ, PERMISSION_OPERATIONAL_TASK_REPORT, PERMISSION_OPERATIONAL_TASK_MANAGE)
    ),
):
    can_manage = _can(db, context, PERMISSION_OPERATIONAL_TASK_MANAGE)
    operator_scoped = _is_operator_scoped(db, context, can_manage=can_manage)
    operational_role = context.operational_role
    tasks = list_tasks(
        db,
        hotel_id=context.hotel_id,
        status=status_filter,
        task_type=task_type if operational_role not in {"housekeeping", "receptionist"} else None,
        task_types=(
            {OperationalTaskTypeEnum.HOUSEKEEPING, OperationalTaskTypeEnum.MAINTENANCE}
            if operational_role == "housekeeping"
            else {OperationalTaskTypeEnum.GENERAL, OperationalTaskTypeEnum.RECEPTION}
            if operational_role == "receptionist"
            else None
        ),
        room_id=room_id,
        assigned_to_user_ids={None, context.user_id} if operator_scoped else None,
        limit=limit,
    )
    return [
        serialize_task(task, include_reservation_context=_can_read_reservation_context(db, context))
        for task in tasks
        if task_type is None or task.task_type == task_type
    ]


@router.post("", response_model=OperationalTaskRead, status_code=status.HTTP_201_CREATED)
def create_operational_task(
    data: OperationalTaskCreate,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(
        require_any_permission(PERMISSION_OPERATIONAL_TASK_REPORT, PERMISSION_OPERATIONAL_TASK_MANAGE)
    ),
):
    can_manage = _can(db, context, PERMISSION_OPERATIONAL_TASK_MANAGE)
    if not can_manage and data.assigned_to_user_id not in {None, context.user_id}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tenés permisos para asignar esta tarea")
    if not can_manage and not _report_type_allowed(context, data.task_type):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Ese tipo de tarea no corresponde a tu operación")
    if data.reservation_id is not None and not _can_read_reservation_context(db, context):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tenés permisos para vincular una reserva")
    try:
        task = create_task(
            db,
            hotel_id=context.hotel_id,
            task_type=data.task_type,
            priority=data.priority,
            title=data.title,
            description=data.description,
            room_id=data.room_id,
            reservation_id=data.reservation_id,
            room_block_id=data.room_block_id,
            assigned_to_user_id=data.assigned_to_user_id,
            due_at=data.due_at,
            created_by_user_id=context.user_id,
        )
        db.commit()
        db.refresh(task)
        return serialize_task(task, include_reservation_context=_can_read_reservation_context(db, context))
    except OperationalTaskError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.patch("/{task_id}", response_model=OperationalTaskRead)
def patch_operational_task(
    task_id: int,
    data: OperationalTaskUpdate,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(
        require_any_permission(PERMISSION_OPERATIONAL_TASK_REPORT, PERMISSION_OPERATIONAL_TASK_MANAGE)
    ),
):
    can_manage = _can(db, context, PERMISSION_OPERATIONAL_TASK_MANAGE)
    if not can_manage:
        try:
            validate_task_operator_scope(
                db,
                hotel_id=context.hotel_id,
                task_id=task_id,
                role=context.operational_role,
                user_id=context.user_id,
            )
        except OperationalTaskError as exc:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tarea no encontrada o no disponible",
            ) from exc
        if data.status not in {None, OperationalTaskStatusEnum.IN_PROGRESS, OperationalTaskStatusEnum.PENDING_REVIEW}:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo una persona responsable puede avanzar la tarea")
        if any(value is not None for value in (data.priority, data.title, data.description, data.assigned_to_user_id, data.due_at)):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tenés permisos para editar ese detalle")
    try:
        task = update_task(
            db,
            hotel_id=context.hotel_id,
            task_id=task_id,
            actor_user_id=context.user_id,
            client_version=data.client_version,
            status=data.status,
            priority=data.priority if can_manage else None,
            title=data.title if can_manage else None,
            description=data.description if can_manage else None,
            assigned_to_user_id=data.assigned_to_user_id if can_manage else None,
            due_at=data.due_at if can_manage else None,
            comment=data.comment,
        )
        db.commit()
        db.refresh(task)
        return serialize_task(task, include_reservation_context=_can_read_reservation_context(db, context))
    except TaskVersionConflict as exc:
        db.rollback()
        raise _conflict(exc) from exc
    except OperationalTaskError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/{task_id}/resolve", response_model=OperationalTaskRead)
def resolve_operational_task(
    task_id: int,
    data: OperationalTaskUpdate,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_OPERATIONAL_TASK_MANAGE)),
):
    try:
        task = update_task(
            db,
            hotel_id=context.hotel_id,
            task_id=task_id,
            actor_user_id=context.user_id,
            client_version=data.client_version,
            status=OperationalTaskStatusEnum.RESOLVED,
            comment=data.comment,
        )
        db.commit()
        db.refresh(task)
        return serialize_task(task, include_reservation_context=_can_read_reservation_context(db, context))
    except TaskVersionConflict as exc:
        db.rollback()
        raise _conflict(exc) from exc
    except OperationalTaskError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/{task_id}/history", response_model=list[OperationalTaskEventRead])
def get_operational_task_history(
    task_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(
        require_any_permission(PERMISSION_OPERATIONAL_TASK_READ, PERMISSION_OPERATIONAL_TASK_REPORT, PERMISSION_OPERATIONAL_TASK_MANAGE)
    ),
):
    can_manage = _can(db, context, PERMISSION_OPERATIONAL_TASK_MANAGE)
    if _is_operator_scoped(db, context, can_manage=can_manage):
        try:
            validate_task_operator_scope(
                db,
                hotel_id=context.hotel_id,
                task_id=task_id,
                role=context.operational_role,
                user_id=context.user_id,
                for_update=True,
            )
        except OperationalTaskError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tarea no encontrada o no disponible",
            ) from exc
    try:
        return task_history(db, hotel_id=context.hotel_id, task_id=task_id)
    except OperationalTaskError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tarea no encontrada o no disponible",
        ) from exc


@router.post("/handoffs", response_model=ShiftHandoffRead, status_code=status.HTTP_201_CREATED)
def create_shift_handoff(
    data: ShiftHandoffCreate,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_SHIFT_HANDOFF_MANAGE)),
):
    try:
        handoff = create_handoff(
            db,
            hotel_id=context.hotel_id,
            delivered_by_user_id=context.user_id,
            task_ids=data.task_ids,
            notes=data.notes,
            cash_close_report_id=data.cash_close_report_id,
        )
        db.commit()
        db.refresh(handoff)
        return serialize_handoff(handoff)
    except OperationalTaskError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/handoffs", response_model=list[ShiftHandoffRead])
def get_shift_handoffs(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_SHIFT_HANDOFF_MANAGE)),
):
    return [serialize_handoff(row) for row in list_handoffs(db, hotel_id=context.hotel_id, limit=limit)]


@router.post("/handoffs/{handoff_id}/acknowledge", response_model=ShiftHandoffRead)
def acknowledge_shift_handoff(
    handoff_id: int,
    data: ShiftHandoffAcknowledge,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_SHIFT_HANDOFF_MANAGE)),
):
    try:
        handoff = acknowledge_handoff(
            db,
            hotel_id=context.hotel_id,
            handoff_id=handoff_id,
            received_by_user_id=context.user_id,
            client_version=data.client_version,
        )
        db.commit()
        db.refresh(handoff)
        return serialize_handoff(handoff)
    except HandoffVersionConflict as exc:
        db.rollback()
        raise _conflict(exc) from exc
    except OperationalTaskError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
