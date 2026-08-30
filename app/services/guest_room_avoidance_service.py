"""Lifecycle rules for tenant-scoped guest room rejections."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.guest import Guest
from app.models.guest_room_avoidance import GuestRoomAvoidance, GuestRoomAvoidanceStatusEnum
from app.models.room import Room


class GuestRoomAvoidanceServiceError(Exception):
    """Base error for guest room-avoidance operations."""


class GuestRoomAvoidanceNotFoundError(GuestRoomAvoidanceServiceError):
    pass


class GuestRoomAvoidanceConflictError(GuestRoomAvoidanceServiceError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _get_tenant_guest(db: Session, *, hotel_id: int, guest_id: int) -> Guest:
    guest = db.query(Guest).filter(Guest.hotel_id == hotel_id, Guest.id == guest_id).one_or_none()
    if guest is None:
        raise GuestRoomAvoidanceNotFoundError("Guest not found")
    return guest


def _get_tenant_room(db: Session, *, hotel_id: int, room_id: int) -> Room:
    room = db.query(Room).filter(Room.hotel_id == hotel_id, Room.id == room_id).one_or_none()
    if room is None:
        # Do not disclose rooms belonging to another hotel.
        raise GuestRoomAvoidanceNotFoundError("Room not found")
    return room


def record_guest_room_avoidance(
    db: Session,
    *,
    hotel_id: int,
    guest_id: int,
    room_id: int,
    source_move_event_id: int | None,
    reason: str | None,
    created_by_user_id: int | None,
) -> GuestRoomAvoidance:
    """Create or reactivate the one rejection for a guest-room pair.

    A later complaint against a resolved room deliberately restores the same
    row so the unique pair remains the durable lifecycle identity.
    """
    _get_tenant_guest(db, hotel_id=hotel_id, guest_id=guest_id)
    _get_tenant_room(db, hotel_id=hotel_id, room_id=room_id)
    avoidance = (
        db.query(GuestRoomAvoidance)
        .filter(
            GuestRoomAvoidance.hotel_id == hotel_id,
            GuestRoomAvoidance.guest_id == guest_id,
            GuestRoomAvoidance.room_id == room_id,
        )
        .one_or_none()
    )
    if avoidance is None:
        avoidance = GuestRoomAvoidance(
            hotel_id=hotel_id,
            guest_id=guest_id,
            room_id=room_id,
            status=GuestRoomAvoidanceStatusEnum.ACTIVE,
            source_move_event_id=source_move_event_id,
            reason=reason,
            created_by_user_id=created_by_user_id,
        )
        db.add(avoidance)
    else:
        avoidance.status = GuestRoomAvoidanceStatusEnum.ACTIVE
        avoidance.source_move_event_id = source_move_event_id
        avoidance.reason = reason
        avoidance.created_by_user_id = created_by_user_id
        avoidance.resolved_by_user_id = None
        avoidance.resolved_at = None
        avoidance.resolution_note = None
    db.flush()
    return avoidance


def get_active_guest_room_avoidances(
    db: Session,
    *,
    hotel_id: int,
    guest_id: int,
) -> list[GuestRoomAvoidance]:
    _get_tenant_guest(db, hotel_id=hotel_id, guest_id=guest_id)
    return (
        db.query(GuestRoomAvoidance)
        .filter(
            GuestRoomAvoidance.hotel_id == hotel_id,
            GuestRoomAvoidance.guest_id == guest_id,
            GuestRoomAvoidance.status == GuestRoomAvoidanceStatusEnum.ACTIVE,
        )
        .order_by(GuestRoomAvoidance.created_at.desc(), GuestRoomAvoidance.id.desc())
        .all()
    )


def resolve_guest_room_avoidance(
    db: Session,
    *,
    hotel_id: int,
    guest_id: int,
    avoidance_id: int,
    resolved_by_user_id: int | None,
    resolution_note: str,
) -> GuestRoomAvoidance:
    _get_tenant_guest(db, hotel_id=hotel_id, guest_id=guest_id)
    avoidance = (
        db.query(GuestRoomAvoidance)
        .filter(
            GuestRoomAvoidance.id == avoidance_id,
            GuestRoomAvoidance.hotel_id == hotel_id,
            GuestRoomAvoidance.guest_id == guest_id,
        )
        .one_or_none()
    )
    if avoidance is None:
        raise GuestRoomAvoidanceNotFoundError("Guest room avoidance not found")
    if avoidance.status == GuestRoomAvoidanceStatusEnum.RESOLVED:
        raise GuestRoomAvoidanceConflictError("Guest room avoidance already resolved")

    avoidance.status = GuestRoomAvoidanceStatusEnum.RESOLVED
    avoidance.resolved_by_user_id = resolved_by_user_id
    avoidance.resolved_at = _now()
    avoidance.resolution_note = resolution_note
    db.flush()
    return avoidance
