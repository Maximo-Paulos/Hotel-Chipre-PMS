"""Canonical, transaction-local room state mutation and orchestration.

``mutate_room_state`` changes a tenant-owned room and writes its strict audit
row in the caller's transaction. It deliberately does not commit, publish,
invalidate caches, or run allocation. ``change_room_status`` remains the
compatibility boundary for callers that need those orchestration effects.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.audit_log import AuditActionEnum
from app.models.room import Room, RoomHousekeepingStatusEnum, RoomStatusEnum
from app.services import audit_log_service
from app.services.allocation_runtime_service import (
    auto_apply_safe_allocation_run,
    run_persisted_allocation,
)
from app.services.housekeeping_checklist_policy import (
    open_housekeeping_checklist_exists,
)
from app.services.read_model_cache import invalidate_hotel_operational_caches
from app.services.timeseries_projection import project_room_state_event


class RoomStateTransitionError(ValueError):
    """A requested room status conflicts with its operational checklist."""


UNAVAILABLE_STATUSES = {
    RoomStatusEnum.CLEANING,
    RoomStatusEnum.MAINTENANCE,
    RoomStatusEnum.BLOCKED,
}


def mutate_room_state(
    db: Session,
    *,
    room: Room,
    hotel_id: int,
    status: RoomStatusEnum | None = None,
    housekeeping_status: RoomHousekeepingStatusEnum | None = None,
    notes: str | None = None,
    actor_user_id: int | None = None,
    audit_on_noop: bool = False,
    allow_open_checklist_occupancy_override: bool = False,
    checklist_override_reason: str | None = None,
) -> bool:
    """Mutate one tenant-scoped room and audit the change without committing.

    Callers own the transaction and must acquire any required room lock before
    calling this function. Release/occupancy and housekeeping-ready transitions
    are blocked while a fixed post-checkout checklist remains open. The only
    override is an explicitly authorized in-house room move to OCCUPIED with a
    nonblank reason. The strict audit row is flushed in the same transaction
    as the room mutation.

    Returns whether the persisted room state changed. ``audit_on_noop`` exists
    for the legacy status endpoint, which historically records each explicit
    status command even when its requested value already matches the room.
    """
    if room.id is None or room not in db or room.hotel_id != hotel_id:
        raise RoomStateTransitionError("La habitación no pertenece al hotel solicitado.")
    if status is None and housekeeping_status is None and notes is None:
        raise RoomStateTransitionError("Se requiere un cambio de estado de habitación.")

    # Recheck ownership against persisted data without flushing unrelated
    # changes staged by the caller. The ORM object itself must also be attached
    # to this session so an untrusted detached object cannot be mutated here.
    with db.no_autoflush:
        tenant_room_exists = (
            db.query(Room.id)
            .filter(Room.id == room.id, Room.hotel_id == hotel_id)
            .one_or_none()
        )
    if tenant_room_exists is None:
        raise RoomStateTransitionError("La habitación no pertenece al hotel solicitado.")

    release_or_occupancy = status in {RoomStatusEnum.AVAILABLE, RoomStatusEnum.OCCUPIED}
    normalized_override_reason = (checklist_override_reason or "").strip()
    if allow_open_checklist_occupancy_override and (
        status != RoomStatusEnum.OCCUPIED or not normalized_override_reason
    ):
        raise RoomStateTransitionError(
            "El override de checklist requiere ocupar la habitación y registrar un motivo."
        )
    housekeeping_ready = housekeeping_status in {
        RoomHousekeepingStatusEnum.CLEAN,
        RoomHousekeepingStatusEnum.INSPECTED,
    }
    checklist_open = open_housekeeping_checklist_exists(
        db,
        hotel_id=hotel_id,
        room_id=room.id,
    )
    checklist_override_active = (
        checklist_open and allow_open_checklist_occupancy_override
    )
    if (release_or_occupancy or housekeeping_ready) and checklist_open and not checklist_override_active:
        if release_or_occupancy:
            detail = "No se puede liberar ni ocupar la habitación mientras tenga un checklist de limpieza pendiente."
        else:
            detail = "Completá los cinco puntos del checklist antes de marcar la habitación como limpia."
        raise RoomStateTransitionError(detail)

    before = audit_log_service.model_snapshot(room)
    if status is not None:
        room.status = status
    if housekeeping_status is not None:
        room.housekeeping_status = housekeeping_status
    if status == RoomStatusEnum.CLEANING:
        room.housekeeping_status = RoomHousekeepingStatusEnum.DIRTY
    if notes is not None:
        room.notes = notes
    after = audit_log_service.model_snapshot(room)
    changed = before != after
    audit_after = after
    if checklist_override_active:
        audit_after = {
            **after,
            "checklist_override": True,
            "checklist_override_reason": normalized_override_reason,
        }

    if changed or audit_on_noop or checklist_override_active:
        audit_log_service.create_audit_log(
            db,
            hotel_id=hotel_id,
            table_name="rooms",
            record_id=room.id,
            action=AuditActionEnum.STATUS_CHANGE,
            actor_user_id=actor_user_id,
            payload_before=before,
            payload_after=audit_after,
        )
    return changed


def change_room_status(
    db: Session,
    *,
    room: Room,
    hotel_id: int,
    status: RoomStatusEnum,
    notes: str | None = None,
    actor_user_id: int | None = None,
    source: str = "rooms.status.patch",
) -> dict | None:
    """Persist a room status transition and run all required side effects.

    The returned value is the serialized allocation result, or ``None`` when
    the new state does not require reallocation. Allocation failures retain the
    existing API contract and are returned as a safe error payload.
    """
    mutate_room_state(
        db,
        room=room,
        hotel_id=hotel_id,
        status=status,
        notes=notes,
        actor_user_id=actor_user_id,
        audit_on_noop=True,
    )
    db.commit()
    db.refresh(room)
    invalidate_hotel_operational_caches(hotel_id)
    project_room_state_event(
        hotel_id,
        room.id,
        status.value,
        datetime.now(timezone.utc),
        {"source": source, "notes": notes},
    )

    if status not in UNAVAILABLE_STATUSES:
        return None

    try:
        result = run_persisted_allocation(
            db,
            hotel_id=hotel_id,
            trigger_type=f"room_status_{status.value}",
            apply=True,
        )
        if result.solver_result.success:
            auto_apply_safe_allocation_run(
                db, hotel_id=hotel_id, run_id=result.run.id
            )
        if result.solver_result.assignments or result.solver_result.unassigned_reservations:
            db.commit()
            return {
                "run_id": result.run.id,
                "status": result.run.status.value if hasattr(result.run.status, "value") else str(result.run.status),
                "assignments": len(result.solver_result.assignments),
                "moved": len(result.solver_result.moved_reservations),
                "moved_ids": result.solver_result.moved_reservations,
                "unassigned": len(result.solver_result.unassigned_reservations),
                "unassigned_ids": result.solver_result.unassigned_reservations,
                "objective_value": result.solver_result.objective_value,
                "error": result.solver_result.error,
            }
    except Exception as exc:  # allocation must not undo the persisted room state
        return {"error": str(exc)}
    return None
