"""Canonical room status transition service.

Every room status mutation must pass through this module so the operational
event projection and persisted reallocation cannot be skipped by a generic
API caller.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.audit_log import AuditActionEnum
from app.models.room import Room, RoomStatusEnum
from app.services import audit_log_service
from app.services.allocation_runtime_service import run_persisted_allocation
from app.services.read_model_cache import invalidate_hotel_operational_caches
from app.services.timeseries_projection import project_room_state_event


UNAVAILABLE_STATUSES = {
    RoomStatusEnum.CLEANING,
    RoomStatusEnum.MAINTENANCE,
    RoomStatusEnum.BLOCKED,
}


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
    before = audit_log_service.model_snapshot(room)
    room.status = status
    if notes is not None:
        room.notes = notes

    db.commit()
    db.refresh(room)
    audit_log_service.safe_create_audit_log(
        db,
        hotel_id=hotel_id,
        table_name="rooms",
        record_id=room.id,
        action=AuditActionEnum.STATUS_CHANGE,
        actor_user_id=actor_user_id,
        payload_before=before,
        payload_after=audit_log_service.model_snapshot(room),
    )
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
