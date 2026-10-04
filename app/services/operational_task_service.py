"""Domain services for shared operational work and shift handoffs."""
from __future__ import annotations

import base64
import binascii
import hashlib
import re
import secrets
from datetime import datetime, timezone

from sqlalchemy import and_, case, or_
from sqlalchemy.orm import Session

from app.services.row_locks import lock_query
from app.models.cash_register import CashCloseReport
from app.models.hotel_membership import HotelMembership
from app.models.hotel_role import HotelRole
from app.models.operational_task import (
    OperationalTaskAttachment,
    OperationalTask,
    OperationalTaskEvent,
    OperationalTaskPriorityEnum,
    OperationalTaskStatusEnum,
    OperationalTaskTypeEnum,
    ShiftHandoff,
    ShiftHandoffStatusEnum,
)
from app.models.stored_object import StoredObject
from app.models.user import User
from app.models.reservation import Reservation
from app.models.room import Room
from app.models.room_block import RoomBlock
from app.services.object_storage import get_object_storage
from app.services.stored_object_service import register_uploaded_object


class OperationalTaskError(ValueError):
    """Expected validation error safe to expose to the operator."""


MAX_OPERATIONAL_TASK_PHOTO_BYTES = 5 * 1024 * 1024
_IMAGE_SIGNATURES = {
    "image/jpeg": lambda data: data.startswith(b"\xff\xd8\xff"),
    "image/png": lambda data: data.startswith(b"\x89PNG\r\n\x1a\n"),
    "image/webp": lambda data: len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP",
}
_IMAGE_EXTENSIONS = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}


def _decode_task_photo(content_base64: str, declared_type: str) -> tuple[bytes, str]:
    raw = (content_base64 or "").strip()
    if raw.startswith("data:"):
        header, separator, raw = raw.partition(",")
        if not separator or ";base64" not in header.lower():
            raise OperationalTaskError("La foto debe ser JPG, PNG o WebP válida")
        embedded_type = header[5:].split(";", 1)[0].lower()
        if embedded_type != declared_type.lower():
            raise OperationalTaskError("El formato declarado no coincide con la foto")
    try:
        content = base64.b64decode(raw, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise OperationalTaskError("La foto debe ser JPG, PNG o WebP válida") from exc
    if not content or len(content) > MAX_OPERATIONAL_TASK_PHOTO_BYTES:
        raise OperationalTaskError("La foto debe pesar como máximo 5 MB")
    content_type = declared_type.lower()
    signature_check = _IMAGE_SIGNATURES.get(content_type)
    if signature_check is None or not signature_check(content):
        raise OperationalTaskError("El contenido no coincide con una imagen JPG, PNG o WebP")
    return content, content_type


def _safe_task_photo_name(file_name: str, content_type: str) -> str:
    basename = file_name.replace("\\", "/").rsplit("/", 1)[-1].strip()
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "_", basename)[:240]
    extension = _IMAGE_EXTENSIONS[content_type]
    if not cleaned:
        cleaned = f"foto.{extension}"
    elif "." not in cleaned:
        cleaned = f"{cleaned}.{extension}"
    return cleaned[:255]


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
        query = lock_query(query, OperationalTask)
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
    for_update: bool = True,
) -> OperationalTask:
    """Keep direct state changes inside the role's operational work queue.

    The list endpoint is filtered for least privilege, but a client can still
    call a detail URL directly. This check keeps the same boundary on every
    state-changing path instead of treating the UI filter as authorization.
    """
    task = _get_task(db, hotel_id, task_id, for_update=for_update)
    if role == "housekeeping":
        allowed_types = {OperationalTaskTypeEnum.HOUSEKEEPING, OperationalTaskTypeEnum.MAINTENANCE}
    elif role == "receptionist":
        allowed_types = {OperationalTaskTypeEnum.GENERAL, OperationalTaskTypeEnum.RECEPTION}
    else:
        allowed_types = None
    if (
        (allowed_types is not None and task.task_type not in allowed_types)
        or task.assigned_to_user_id not in {None, user_id}
    ):
        raise OperationalTaskError("No tenés acceso operativo a esta tarea")
    return task


def validate_task_operator_read_scope(
    db: Session,
    *,
    hotel_id: int,
    task_id: int,
    role: str | None,
    user_id: int,
) -> OperationalTask:
    """Check tenant-scoped read access, including read-only General tasks.

    Housekeeping can review all General tasks to understand hotel context, but
    may only act on unassigned or personally assigned housekeeping and
    maintenance work. Reception keeps its existing scoped queue.
    """
    task = _get_task(db, hotel_id, task_id)
    if role == "housekeeping":
        if task.task_type == OperationalTaskTypeEnum.GENERAL:
            return task
        allowed_types = {OperationalTaskTypeEnum.HOUSEKEEPING, OperationalTaskTypeEnum.MAINTENANCE}
    elif role == "receptionist":
        allowed_types = {OperationalTaskTypeEnum.GENERAL, OperationalTaskTypeEnum.RECEPTION}
    else:
        allowed_types = None
    if (
        (allowed_types is not None and task.task_type not in allowed_types)
        or task.assigned_to_user_id not in {None, user_id}
    ):
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
    read_all_task_types: set[OperationalTaskTypeEnum] | None = None,
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
        assignment_filter = None
        if None in assigned_to_user_ids:
            assignment_filter = or_(
                OperationalTask.assigned_to_user_id.is_(None),
                OperationalTask.assigned_to_user_id.in_(assigned_ids),
            )
        elif assigned_ids:
            assignment_filter = OperationalTask.assigned_to_user_id.in_(assigned_ids)
        else:
            assignment_filter = None

        if assignment_filter is None:
            if not read_all_task_types:
                return []
            query = query.filter(OperationalTask.task_type.in_(read_all_task_types))
        elif read_all_task_types:
            scoped_types = set(task_types or ()) - set(read_all_task_types)
            if scoped_types:
                query = query.filter(
                    or_(
                        OperationalTask.task_type.in_(read_all_task_types),
                        and_(OperationalTask.task_type.in_(scoped_types), assignment_filter),
                    )
                )
            else:
                query = query.filter(OperationalTask.task_type.in_(read_all_task_types))
        else:
            query = query.filter(assignment_filter)
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


_TASK_AUTHOR_ROLE_LABELS = {
    "owner": "Dueño",
    "co_owner": "Codueña",
    "manager": "Gerencia",
    "receptionist": "Recepción",
    "housekeeping": "Limpieza",
}
_UNKNOWN_TASK_AUTHOR_LABEL = "Personal del hotel"


def task_author_labels(
    db: Session,
    *,
    hotel_id: int,
    user_ids: set[int | None],
) -> dict[int, str]:
    """Resolve task author names only through membership in the task's hotel.

    The display name is selected without retrieving email or other account
    fields. If it is missing, a built-in role label (including a custom role's
    hotel-scoped base role) gives operators useful context without identifying
    the person. Memberships are not filtered by active status so old tasks
    remain attributable after a membership is revoked.
    """
    scoped_user_ids = {user_id for user_id in user_ids if user_id is not None}
    if not scoped_user_ids:
        return {}

    rows = (
        db.query(
            HotelMembership.user_id,
            HotelMembership.role,
            HotelRole.base_role,
            User.display_name,
        )
        .join(User, User.id == HotelMembership.user_id)
        .outerjoin(
            HotelRole,
            and_(
                HotelRole.hotel_id == HotelMembership.hotel_id,
                HotelRole.code == HotelMembership.role,
            ),
        )
        .filter(
            HotelMembership.hotel_id == hotel_id,
            HotelMembership.user_id.in_(scoped_user_ids),
        )
        .all()
    )
    labels: dict[int, str] = {}
    for user_id, role, base_role, display_name in rows:
        cleaned_name = display_name.strip() if isinstance(display_name, str) else ""
        role_key = base_role if role.startswith("cr_") else role
        labels[user_id] = cleaned_name or _TASK_AUTHOR_ROLE_LABELS.get(role_key, _UNKNOWN_TASK_AUTHOR_LABEL)
    return labels


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
    handoff = lock_query(
        db.query(ShiftHandoff).filter(ShiftHandoff.id == handoff_id, ShiftHandoff.hotel_id == hotel_id),
        ShiftHandoff,
    ).first()
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


def serialize_task(
    task: OperationalTask,
    *,
    author_name: str | None = None,
    include_reservation_context: bool = True,
) -> dict:
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
        "created_by_name": (author_name or "").strip() or _UNKNOWN_TASK_AUTHOR_LABEL,
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
        "delivered_by_name": getattr(getattr(handoff, "delivered_by", None), "display_name", None),
        "received_by_user_id": handoff.received_by_user_id,
        "received_by_name": getattr(getattr(handoff, "received_by", None), "display_name", None),
        "cash_close_report_id": handoff.cash_close_report_id,
        "status": _enum_value(handoff.status),
        "notes": handoff.notes,
        "delivered_at": handoff.delivered_at,
        "acknowledged_at": handoff.acknowledged_at,
        "created_at": handoff.created_at,
        "version": handoff.version,
        "task_ids": [task.id for task in getattr(handoff, "tasks", [])],
    }


def serialize_task_event(event: OperationalTaskEvent) -> dict:
    return {
        "id": event.id,
        "from_status": event.from_status,
        "to_status": event.to_status,
        "actor_user_id": event.actor_user_id,
        "actor_name": getattr(getattr(event, "actor", None), "display_name", None),
        "comment": event.comment,
        "created_at": event.created_at,
    }


def serialize_task_attachment(attachment: OperationalTaskAttachment) -> dict:
    return {
        "id": attachment.id,
        "file_name": attachment.file_name,
        "content_type": attachment.content_type,
        "byte_size": attachment.byte_size,
        "created_by_user_id": attachment.created_by_user_id,
        "created_by_name": getattr(getattr(attachment, "created_by", None), "display_name", None),
        "created_at": attachment.created_at,
    }


def create_task_attachment(
    db: Session,
    *,
    hotel_id: int,
    task_id: int,
    actor_user_id: int,
    file_name: str,
    content_type: str,
    content_base64: str,
) -> OperationalTaskAttachment:
    task = _get_task(db, hotel_id, task_id)
    _validate_user_membership(db, hotel_id, actor_user_id)
    content, verified_type = _decode_task_photo(content_base64, content_type)
    safe_name = _safe_task_photo_name(file_name, verified_type)
    object_key = f"operational-task-photos/{hotel_id}/{task_id}/{secrets.token_urlsafe(24)}.{_IMAGE_EXTENSIONS[verified_type]}"
    try:
        stored_object = register_uploaded_object(
            db,
            hotel_id=hotel_id,
            purpose="operational_task_photo",
            object_key=object_key,
            data=content,
            content_type=verified_type,
            created_by_user_id=actor_user_id,
        )
        attachment = OperationalTaskAttachment(
            hotel_id=hotel_id,
            task_id=task.id,
            stored_object_id=stored_object.id,
            file_name=safe_name,
            content_type=verified_type,
            byte_size=len(content),
            created_by_user_id=actor_user_id,
        )
        db.add(attachment)
        db.flush()
    except Exception:
        db.rollback()
        try:
            get_object_storage().delete(object_key)
        except Exception:
            pass
        raise
    attachment._uncommitted_object_key = object_key
    return attachment


def list_task_attachments(
    db: Session,
    *,
    hotel_id: int,
    task_id: int,
) -> list[OperationalTaskAttachment]:
    _get_task(db, hotel_id, task_id)
    return (
        db.query(OperationalTaskAttachment)
        .filter(
            OperationalTaskAttachment.hotel_id == hotel_id,
            OperationalTaskAttachment.task_id == task_id,
        )
        .order_by(OperationalTaskAttachment.created_at.asc(), OperationalTaskAttachment.id.asc())
        .all()
    )


def task_attachment_content(
    db: Session,
    *,
    hotel_id: int,
    task_id: int,
    attachment_id: int,
) -> dict[str, str | int]:
    attachment = (
        db.query(OperationalTaskAttachment)
        .filter(
            OperationalTaskAttachment.hotel_id == hotel_id,
            OperationalTaskAttachment.task_id == task_id,
            OperationalTaskAttachment.id == attachment_id,
        )
        .one_or_none()
    )
    if attachment is None:
        raise OperationalTaskError("Foto no encontrada")
    stored_object = (
        db.query(StoredObject)
        .filter(
            StoredObject.id == attachment.stored_object_id,
            StoredObject.hotel_id == hotel_id,
            StoredObject.purpose == "operational_task_photo",
            StoredObject.status == "ready",
            StoredObject.deleted_at.is_(None),
        )
        .one_or_none()
    )
    if stored_object is None:
        raise OperationalTaskError("Foto no encontrada")
    try:
        content = get_object_storage().get_bytes(stored_object.object_key)
    except Exception as exc:
        raise OperationalTaskError("No se pudo abrir la foto en este momento") from exc
    if (
        len(content) != attachment.byte_size
        or len(content) > MAX_OPERATIONAL_TASK_PHOTO_BYTES
        or hashlib.sha256(content).hexdigest() != stored_object.sha256_hex
    ):
        raise OperationalTaskError("La foto no está disponible en este momento")
    try:
        verified_content, content_type = _decode_task_photo(base64.b64encode(content).decode("ascii"), attachment.content_type)
    except OperationalTaskError as exc:
        raise OperationalTaskError("La foto no está disponible en este momento") from exc
    return {
        "content_type": content_type,
        "content_base64": base64.b64encode(verified_content).decode("ascii"),
        "byte_size": len(verified_content),
    }
