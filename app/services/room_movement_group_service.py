from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.audit_log import AuditActionEnum
from app.models.operations import RoomMoveEvent, RoomMovementGroup
from app.models.reservation import Reservation
from app.models.room import Room
from app.models.security_audit_log import SecurityAuditLog
from app.services import audit_log_service


class RoomMovementGroupError(Exception):
    """Business error for room movement group operations."""


def get_group(db: Session, *, hotel_id: int, group_id: int) -> RoomMovementGroup | None:
    return (
        db.query(RoomMovementGroup)
        .filter(RoomMovementGroup.id == group_id, RoomMovementGroup.hotel_id == hotel_id)
        .first()
    )


def list_groups(db: Session, *, hotel_id: int, limit: int = 50) -> list[RoomMovementGroup]:
    """Most recent movement groups for a hotel (newest first)."""
    safe_limit = max(1, min(limit, 200))
    return (
        db.query(RoomMovementGroup)
        .filter(RoomMovementGroup.hotel_id == hotel_id)
        .order_by(RoomMovementGroup.created_at.desc(), RoomMovementGroup.id.desc())
        .limit(safe_limit)
        .all()
    )


def create_grouped_room_move(
    db: Session,
    *,
    hotel_id: int,
    reservation: Reservation,
    to_room: Room,
    trigger_reason: str,
    reason_code: str,
    reason_note: str,
    move_type,
    trigger_event: str,
    created_by_user_id: int | None = None,
    group_notes: str | None = None,
) -> tuple[RoomMovementGroup, RoomMoveEvent]:
    if reservation.hotel_id != hotel_id or to_room.hotel_id != hotel_id:
        raise RoomMovementGroupError("Reservation and destination room must belong to the active hotel")
    if reservation.room_id is None:
        raise RoomMovementGroupError("Reservation has no source room to move")

    before = audit_log_service.model_snapshot(reservation)
    from_room_id = reservation.room_id
    state_before = f"room_id={from_room_id};category_id={reservation.category_id}"

    group = RoomMovementGroup(
        hotel_id=hotel_id,
        trigger_reason=trigger_reason,
        notes=group_notes or reason_note,
        is_reverted=False,
        created_by_user_id=created_by_user_id,
    )
    db.add(group)
    db.flush()

    reservation.room_id = to_room.id
    reservation.category_id = to_room.category_id
    reservation.allocation_locked = True
    reservation.requires_manual_review = False
    reservation.allocation_status = "assigned"

    event = RoomMoveEvent(
        hotel_id=hotel_id,
        reservation_id=reservation.id,
        movement_group_id=group.id,
        from_room_id=from_room_id,
        to_room_id=to_room.id,
        move_type=move_type,
        reason_code=reason_code,
        reason_note=reason_note,
        trigger_event=trigger_event,
        state_before=state_before,
        state_after=f"room_id={to_room.id};category_id={to_room.category_id}",
        notes=reason_note,
        created_by_user_id=created_by_user_id,
    )
    db.add(event)
    db.flush()

    audit_log_service.queue_audit_log(
        db,
        hotel_id=hotel_id,
        table_name="reservations",
        record_id=reservation.id,
        action=AuditActionEnum.UPDATE,
        actor_user_id=created_by_user_id,
        payload_before=before,
        payload_after=audit_log_service.model_snapshot(reservation),
    )
    return group, event


def revert_group(
    db: Session,
    *,
    hotel_id: int,
    group_id: int,
    reverted_by_user_id: int | None = None,
) -> RoomMovementGroup:
    group = get_group(db, hotel_id=hotel_id, group_id=group_id)
    if group is None:
        raise RoomMovementGroupError("Movement group not found")
    if group.is_reverted:
        raise RoomMovementGroupError("Movement group is already reverted")

    events = (
        db.query(RoomMoveEvent)
        .filter(
            RoomMoveEvent.hotel_id == hotel_id,
            RoomMoveEvent.movement_group_id == group_id,
        )
        .order_by(RoomMoveEvent.id.desc())
        .all()
    )
    if not events:
        raise RoomMovementGroupError("Movement group has no linked room moves")

    reverted_reservation_ids: list[int] = []
    for event in events:
        if event.from_room_id is None:
            raise RoomMovementGroupError("Movement without source room cannot be reverted automatically")
        reservation = (
            db.query(Reservation)
            .filter(Reservation.id == event.reservation_id, Reservation.hotel_id == hotel_id)
            .first()
        )
        if reservation is None:
            raise RoomMovementGroupError("Linked reservation no longer exists")
        from_room = db.query(Room).filter(Room.id == event.from_room_id, Room.hotel_id == hotel_id).first()
        if from_room is None:
            raise RoomMovementGroupError("Original room no longer exists")

        reservation.room_id = from_room.id
        reservation.category_id = from_room.category_id
        reservation.allocation_locked = True
        reservation.requires_manual_review = False
        reverted_reservation_ids.append(reservation.id)

    group.is_reverted = True
    group.reverted_by_user_id = reverted_by_user_id
    group.reverted_at = datetime.now(timezone.utc)
    db.add(
        SecurityAuditLog(
            hotel_id=hotel_id,
            user_id=reverted_by_user_id,
            action="room_movement_group.reverted",
            resource_type="room_movement_group",
            resource_id=str(group.id),
            details=json.dumps(
                {
                    "group_id": group.id,
                    "move_event_ids": [event.id for event in events],
                    "reservation_ids": reverted_reservation_ids,
                },
                sort_keys=True,
            ),
        )
    )
    db.flush()
    return group
