"""Domain services for shared operational work and shift handoffs."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import case
from sqlalchemy.orm import Session

from app.models.cash_register import CashCloseReport
from app.models.hotel_membership import HotelMembership
from app.models.operational_task import (
    OperationalTask,
    OperationalTaskEvent,
    OperationalTaskPriorityEnum,
    OperationalTaskStatusEnum,
    OperationalTaskTypeEnum,
    ShiftHandoff,
    ShiftHandoffStatusEnum,
)
from app.models.reservation import Reservation
from app.models.room import Room
from app.models.room_block import RoomBlock


class OperationalTaskError(ValueError):
    """Expected validation error safe to expose to the operator."""


class TaskVersionConflict(OperationalTaskError):
    def __init__(self, task_id: int, current_version: int):
        super().__init__("La tarea cambió en otra sesión. Actualizá la vista antes de continuar.")
        self.task_id = task_id
        self.current_version = current_version


class HandoffVersionConflict(OperationalTaskError):
    def __init__(self, handoff_id: int, current_version: int):
        super().__init__("El pase de turno cambió en otra sesión. Actualizá la vista antes de reconocerlo.")
        self.handoff_id = handoff_id
        self.current_version = current_version


_ALLOWED_TRANSITIONS: dict[OperationalTaskStatusEnum, set[OperationalTaskStatusEnum]] = {
    OperationalTaskStatusEnum.PENDING: {
        OperationalTaskStatusEnum.IN_PROGRESS,
        OperationalTaskStatusEnum.RESOLVED,
    },
    OperationalTaskStatusEnum.IN_PROGRESS: {
        OperationalTaskStatusEnum.PENDING_REVIEW,
        OperationalTaskStatusEnum.RESOLVED,
        OperationalTaskStatusEnum.PENDING,
    },
    OperationalTaskStatusEnum.PENDING_REVIEW: {
        OperationalTaskStatusEnum.RESOLVED,
        OperationalTaskStatusEnum.IN_PROGRESS,
    },
    OperationalTaskStatusEnum.RESOLVED: set(),
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _enum_value(value):
    return value.value if hasattr(value, "value") else value


def _get_task(db: Session, hotel_id: int, task_id: int, *, for_update: bool = False) -> OperationalTask:
    query = db.query(OperationalTask).filter(OperationalTask.hotel_id == hotel_id, OperationalTask.id == task_id)
    if for_update:
        # PostgreSQL serializes two transitions for the same task. SQLite
        # ignores FOR UPDATE, but the version check remains the conflict
        # contract used by the API and tests there.
        query = query.with_for_update()
    task = query.first()
    if task is None:
        raise OperationalTaskError("Tarea no encontrada")
    return task


def validate_task_operator_scope(
    db: Session,
    *,
    hotel_id: int,
    task_id: int,
    role: str | None,
    user_id: int,
) -> OperationalTask:
    """Keep direct state changes inside the role's operational work queue.

    The list endpoint is filtered for least privilege, but a client can still
    call a detail URL directly. This check keeps the same boundary on every
    state-changing path instead of treating the UI filter as authorization.
    """
    task = _get_task(db, hotel_id, task_id, for_update=True)
    if role == "housekeeping":
        allowed_types = {OperationalTaskTypeEnum.HOUSEKEEPING, OperationalTaskTypeEnum.MAINTENANCE}
    elif role == "receptionist":
        allowed_types = {OperationalTaskTypeEnum.GENERAL, OperationalTaskTypeEnum.RECEPTION}
    else:
        return task
    if task.task_type not in allowed_types or task.assigned_to_user_id not in {None, user_id}:
        raise OperationalTaskError("No tenés acceso operativo a esta tarea")
    return task


def _validate_user_membership(db: Session, hotel_id: int, user_id: int | None) -> None:
    if user_id is None:
        return
    membership = (
        db.query(HotelMembership.id)
        .filter(
            HotelMembership.hotel_id == hotel_id,
            HotelMembership.user_id == user_id,
            HotelMembership.status == "active",
        )
        .first()
    )
    if membership is None:
        raise OperationalTaskError("La persona seleccionada no pertenece al hotel")


def _validate_links(
    db: Session,
    *,
    hotel_id: int,
    room_id: int | None,
    reservation_id: int | None,
    room_block_id: int | None,
    task_type: OperationalTaskTypeEnum,
) -> None:
    room = None
    if room_id is not None:
        room = (
            db.query(Room)
            .filter(Room.id == room_id, Room.hotel_id == hotel_id, Room.deleted_at.is_(None))
            .first()
        )
        if room is None:
            raise OperationalTaskError("La habitación no pertenece al hotel o no está disponible")

    if reservation_id is not None:
        reservation = (
            db.query(Reservation)
            .filter(Reservation.id == reservation_id, Reservation.hotel_id == hotel_id)
            .first()
        )
        if reservation is None:
            raise OperationalTaskError("La reserva no pertenece al hotel")
        if room_id is not None and reservation.room_id is not None and reservation.room_id != room_id:
            raise OperationalTaskError("La habitación y la reserva vinculadas no coinciden")

    if room_block_id is not None:
        block = (
            db.query(RoomBlock)
            .filter(RoomBlock.id == room_block_id, RoomBlock.hotel_id == hotel_id)
            .first()
        )
        if block is None:
            raise OperationalTaskError("El bloqueo de habitación no pertenece al hotel")
        if room is not None and block.room_id != room.id:
            raise OperationalTaskError("El bloqueo y la habitación vinculados no coinciden")
        if task_type != OperationalTaskTypeEnum.MAINTENANCE:
            raise OperationalTaskError("Solo una tarea de mantenimiento puede vincularse a un bloqueo")


def _append_event(
    db: Session,
    *,
    task: OperationalTask,
    actor_user_id: int | None,
    from_status: OperationalTaskStatusEnum | str | None,
    to_status: OperationalTaskStatusEnum | str,
    comment: str | None = None,
) -> OperationalTaskEvent:
    event = OperationalTaskEvent(
        hotel_id=task.hotel_id,
        task_id=task.id,
        actor_user_id=actor_user_id,
        from_status=_enum_value(from_status) if from_status is not None else None,
        to_status=_enum_value(to_status),
        comment=comment,
    )
    task.events.append(event)
    return event


def create_task(
    db: Session,
    *,
    hotel_id: int,
    task_type: OperationalTaskTypeEnum,
    priority: OperationalTaskPriorityEnum,
    title: str,
    description: str | None = None,
    room_id: int | None = None,
    reservation_id: int | None = None,
    room_block_id: int | None = None,
    assigned_to_user_id: int | None = None,
    due_at: datetime | None = None,
    created_by_user_id: int | None = None,
) -> OperationalTask:
    title = title.strip()
    if not title:
        raise OperationalTaskError("La tarea necesita un título")
    _validate_links(
        db,
        hotel_id=hotel_id,
        room_id=room_id,
        reservation_id=reservation_id,
        room_block_id=room_block_id,
        task_type=task_type,
    )
    _validate_user_membership(db, hotel_id, assigned_to_user_id)
    _validate_user_membership(db, hotel_id, created_by_user_id)
    task = OperationalTask(
        hotel_id=hotel_id,
        task_type=task_type,
        priority=priority,
        title=title,
        description=description.strip() if description else None,
        room_id=room_id,
        reservation_id=reservation_id,
        room_block_id=room_block_id,
        assigned_to_user_id=assigned_to_user_id,
        due_at=due_at,
        created_by_user_id=created_by_user_id,
        status=OperationalTaskStatusEnum.PENDING,
        version=0,
    )
    db.add(task)
    db.flush()
    _append_event(
        db,
        task=task,
        actor_user_id=created_by_user_id,
        from_status=None,
        to_status=OperationalTaskStatusEnum.PENDING,
        comment="Tarea creada",
    )
    return task


def list_tasks(
    db: Session,
    *,
    hotel_id: int,
    status: OperationalTaskStatusEnum | None = None,
    task_type: OperationalTaskTypeEnum | None = None,
    task_types: set[OperationalTaskTypeEnum] | None = None,
    room_id: int | None = None,
    assigned_to_user_ids: set[int | None] | None = None,
    limit: int = 100,
) -> list[OperationalTask]:
    query = db.query(OperationalTask).filter(OperationalTask.hotel_id == hotel_id)
    if status is not None:
        query = query.filter(OperationalTask.status == status)
    if task_type is not None:
        query = query.filter(OperationalTask.task_type == task_type)
    if task_types:
        query = query.filter(OperationalTask.task_type.in_(task_types))
    if room_id is not None:
        query = query.filter(OperationalTask.room_id == room_id)
    if assigned_to_user_ids is not None:
        assigned_ids = [item for item in assigned_to_user_ids if item is not None]
        if None in assigned_to_user_ids:
            from sqlalchemy import or_

            query = query.filter(
                or_(
                    OperationalTask.assigned_to_user_id.is_(None),
                    OperationalTask.assigned_to_user_id.in_(assigned_ids),
                )
            )
        elif assigned_ids:
            query = query.filter(OperationalTask.assigned_to_user_id.in_(assigned_ids))
        else:
            return []
    priority_order = {
        OperationalTaskPriorityEnum.CRITICAL: 0,
        OperationalTaskPriorityEnum.HIGH: 1,
        OperationalTaskPriorityEnum.MEDIUM: 2,
        OperationalTaskPriorityEnum.LOW: 3,
    }
    # CASE keeps the ordering deterministic across SQLite and PostgreSQL.
    return (
        query.order_by(
            case(priority_order, value=OperationalTask.priority),
            OperationalTask.due_at.asc().nullslast(),
            OperationalTask.id.asc(),
        )
        .limit(max(1, min(limit, 500)))
        .all()
    )


def update_task(
    db: Session,
    *,
    hotel_id: int,
    task_id: int,
    actor_user_id: int,
    client_version: int,
    status: OperationalTaskStatusEnum | None = None,
    priority: OperationalTaskPriorityEnum | None = None,
    title: str | None = None,
    description: str | None = None,
    assigned_to_user_id: int | None = None,
    due_at: datetime | None = None,
    comment: str | None = None,
) -> OperationalTask:
    task = _get_task(db, hotel_id, task_id, for_update=True)
    if task.version != client_version:
        raise TaskVersionConflict(task.id, task.version)
    _validate_user_membership(db, hotel_id, actor_user_id)
    if assigned_to_user_id is not None:
        _validate_user_membership(db, hotel_id, assigned_to_user_id)
    old_status = task.status
    if status is not None:
        status = OperationalTaskStatusEnum(status)
        if status != old_status and status not in _ALLOWED_TRANSITIONS[old_status]:
            raise OperationalTaskError("La tarea no puede pasar de ese estado al estado solicitado")
        task.status = status
        if status == OperationalTaskStatusEnum.RESOLVED:
            task.resolved_by_user_id = actor_user_id
            task.resolved_at = _now()
        elif old_status == OperationalTaskStatusEnum.RESOLVED:
            task.resolved_by_user_id = None
            task.resolved_at = None
    if priority is not None:
        task.priority = priority
    if title is not None:
        title = title.strip()
        if not title:
            raise OperationalTaskError("La tarea necesita un título")
        task.title = title
    if description is not None:
        task.description = description.strip() or None
    if assigned_to_user_id is not None:
        task.assigned_to_user_id = assigned_to_user_id
    if due_at is not None:
        task.due_at = due_at
    task.version += 1
    task.updated_at = _now()
    if status is not None and status != old_status:
        _append_event(
            db,
            task=task,
            actor_user_id=actor_user_id,
            from_status=old_status,
            to_status=status,
            comment=comment,
        )
    elif comment:
        _append_event(
            db,
            task=task,
            actor_user_id=actor_user_id,
            from_status=task.status,
            to_status=task.status,
            comment=comment,
        )
    db.flush()
    return task


def task_history(db: Session, *, hotel_id: int, task_id: int) -> list[OperationalTaskEvent]:
    _get_task(db, hotel_id, task_id)
    return (
        db.query(OperationalTaskEvent)
        .filter(OperationalTaskEvent.hotel_id == hotel_id, OperationalTaskEvent.task_id == task_id)
        .order_by(OperationalTaskEvent.created_at.asc(), OperationalTaskEvent.id.asc())
        .all()
    )


def create_handoff(
    db: Session,
    *,
    hotel_id: int,
    delivered_by_user_id: int,
    task_ids: list[int],
    notes: str | None = None,
    cash_close_report_id: int | None = None,
) -> ShiftHandoff:
    _validate_user_membership(db, hotel_id, delivered_by_user_id)
    unique_task_ids = list(dict.fromkeys(task_ids))
    if not unique_task_ids:
        raise OperationalTaskError("El pase necesita al menos una tarea")
    tasks = (
        db.query(OperationalTask)
        .filter(OperationalTask.hotel_id == hotel_id, OperationalTask.id.in_(unique_task_ids))
        .all()
    )
    if len(tasks) != len(unique_task_ids):
        raise OperationalTaskError("Una o más tareas no pertenecen al hotel")
    if cash_close_report_id is not None:
        report = (
            db.query(CashCloseReport.id)
            .filter(CashCloseReport.id == cash_close_report_id, CashCloseReport.hotel_id == hotel_id)
            .first()
        )
        if report is None:
            raise OperationalTaskError("El cierre de caja no pertenece al hotel")
    handoff = ShiftHandoff(
        hotel_id=hotel_id,
        delivered_by_user_id=delivered_by_user_id,
        cash_close_report_id=cash_close_report_id,
        notes=notes.strip() if notes else None,
        status=ShiftHandoffStatusEnum.PENDING_ACKNOWLEDGEMENT,
        version=0,
    )
    handoff.tasks = tasks
    db.add(handoff)
    db.flush()
    return handoff


def list_handoffs(db: Session, *, hotel_id: int, limit: int = 50) -> list[ShiftHandoff]:
    return (
        db.query(ShiftHandoff)
        .filter(ShiftHandoff.hotel_id == hotel_id)
        .order_by(ShiftHandoff.delivered_at.desc(), ShiftHandoff.id.desc())
        .limit(max(1, min(limit, 200)))
        .all()
    )


def acknowledge_handoff(
    db: Session,
    *,
    hotel_id: int,
    handoff_id: int,
    received_by_user_id: int,
    client_version: int,
) -> ShiftHandoff:
    handoff = (
        db.query(ShiftHandoff)
        .filter(ShiftHandoff.id == handoff_id, ShiftHandoff.hotel_id == hotel_id)
        .with_for_update()
        .first()
    )
    if handoff is None:
        raise OperationalTaskError("Pase de turno no encontrado")
    if handoff.version != client_version:
        raise HandoffVersionConflict(handoff.id, handoff.version)
    if handoff.status != ShiftHandoffStatusEnum.PENDING_ACKNOWLEDGEMENT:
        raise OperationalTaskError("Este pase de turno ya fue reconocido")
    _validate_user_membership(db, hotel_id, received_by_user_id)
    handoff.received_by_user_id = received_by_user_id
    handoff.acknowledged_at = _now()
    handoff.status = ShiftHandoffStatusEnum.ACKNOWLEDGED
    handoff.version += 1
    db.flush()
    return handoff


def serialize_task(task: OperationalTask, *, include_reservation_context: bool = True) -> dict:
    room = getattr(task, "room", None)
    reservation = getattr(task, "reservation", None)
    return {
        "id": task.id,
        "hotel_id": task.hotel_id,
        "task_type": _enum_value(task.task_type),
        "status": _enum_value(task.status),
        "priority": _enum_value(task.priority),
        "title": task.title,
        "description": task.description,
        "room_id": task.room_id,
        "room_number": getattr(room, "room_number", None),
        "reservation_id": task.reservation_id if include_reservation_context else None,
        "confirmation_code": getattr(reservation, "confirmation_code", None) if include_reservation_context else None,
        "room_block_id": task.room_block_id,
        "assigned_to_user_id": task.assigned_to_user_id,
        "due_at": task.due_at,
        "created_by_user_id": task.created_by_user_id,
        "resolved_by_user_id": task.resolved_by_user_id,
        "resolved_at": task.resolved_at,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
        "version": task.version,
    }


def serialize_handoff(handoff: ShiftHandoff) -> dict:
    return {
        "id": handoff.id,
        "hotel_id": handoff.hotel_id,
        "delivered_by_user_id": handoff.delivered_by_user_id,
        "received_by_user_id": handoff.received_by_user_id,
        "cash_close_report_id": handoff.cash_close_report_id,
        "status": _enum_value(handoff.status),
        "notes": handoff.notes,
        "delivered_at": handoff.delivered_at,
        "acknowledged_at": handoff.acknowledged_at,
        "created_at": handoff.created_at,
        "version": handoff.version,
        "task_ids": [task.id for task in getattr(handoff, "tasks", [])],
    }
