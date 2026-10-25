"""Tenant-scoped lifecycle for fixed post-checkout housekeeping checklists."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.audit_log import AuditActionEnum
from app.models.housekeeping_checklist import (
    HousekeepingChecklist,
    HousekeepingChecklistItem,
    HousekeepingChecklistItemCodeEnum,
    HousekeepingChecklistStatusEnum,
)
from app.models.room import Room, RoomHousekeepingStatusEnum, RoomStatusEnum
from app.schemas.housekeeping_checklist import (
    HousekeepingChecklistItemRead,
    HousekeepingChecklistListRead,
    HousekeepingChecklistRead,
    HousekeepingChecklistRoomRead,
)
from app.services import audit_log_service
from app.services.housekeeping_checklist_policy import (
    REQUIRED_HOUSEKEEPING_CHECKLIST_CODES,
    REQUIRED_HOUSEKEEPING_CHECKLIST_ITEMS,
)
from app.services.room_state_service import RoomStateTransitionError, mutate_room_state


class HousekeepingChecklistError(Exception):
    """Base error for checklist operations."""


class HousekeepingChecklistNotFound(HousekeepingChecklistError):
    """Checklist, room, or fixed item is outside the requested hotel/scope."""


class HousekeepingChecklistConflict(HousekeepingChecklistError):
    """A checklist transition conflicts with the current room/checklist state."""


@dataclass(frozen=True)
class HousekeepingChecklistCompletionResult:
    checklist: HousekeepingChecklistRead
    changed: bool
    completed_now: bool


def create_checkout_checklist(
    db: Session,
    *,
    hotel_id: int,
    room_id: int,
    reservation_id: int,
    actor_user_id: int | None,
) -> HousekeepingChecklist:
    """Create exactly the five fixed items as part of checkout's transaction."""
    checklist = HousekeepingChecklist(
        hotel_id=hotel_id,
        room_id=room_id,
        reservation_id=reservation_id,
        status=HousekeepingChecklistStatusEnum.OPEN.value,
        version=1,
        created_by_user_id=actor_user_id,
    )
    db.add(checklist)
    db.flush()
    db.add_all(
        [
            HousekeepingChecklistItem(
                hotel_id=hotel_id,
                checklist_id=checklist.id,
                code=code.value,
                label=label,
                completed=False,
            )
            for code, label in REQUIRED_HOUSEKEEPING_CHECKLIST_ITEMS
        ]
    )
    db.flush()
    audit_log_service.create_audit_log(
        db,
        hotel_id=hotel_id,
        table_name="housekeeping_checklists",
        record_id=checklist.id,
        action=AuditActionEnum.CREATE,
        actor_user_id=actor_user_id,
        payload_after={
            "hotel_id": hotel_id,
            "room_id": room_id,
            "reservation_id": reservation_id,
            "status": HousekeepingChecklistStatusEnum.OPEN.value,
            "item_codes": sorted(REQUIRED_HOUSEKEEPING_CHECKLIST_CODES),
        },
    )
    return checklist


def _read_checklist(
    db: Session,
    *,
    checklist: HousekeepingChecklist,
    room: Room | None = None,
) -> HousekeepingChecklistRead:
    if room is None:
        room = (
            db.query(Room)
            .filter(Room.id == checklist.room_id, Room.hotel_id == checklist.hotel_id)
            .one_or_none()
        )
    if room is None:
        raise HousekeepingChecklistNotFound("No se encontró la habitación del checklist")

    items = (
        db.query(HousekeepingChecklistItem)
        .filter(
            HousekeepingChecklistItem.hotel_id == checklist.hotel_id,
            HousekeepingChecklistItem.checklist_id == checklist.id,
        )
        .order_by(HousekeepingChecklistItem.id.asc())
        .all()
    )
    return _build_checklist_read(
        checklist=checklist,
        room_id=room.id,
        room_number=room.room_number,
        operational_status=room.status,
        housekeeping_status=room.housekeeping_status,
        items=items,
    )


def _build_checklist_read(
    *,
    checklist: HousekeepingChecklist,
    room_id: int,
    room_number: str,
    operational_status: RoomStatusEnum,
    housekeeping_status: RoomHousekeepingStatusEnum,
    items: list[HousekeepingChecklistItem],
) -> HousekeepingChecklistRead:
    return HousekeepingChecklistRead(
        checklist_id=checklist.id,
        room=HousekeepingChecklistRoomRead(
            id=room_id,
            number=room_number,
            operational_status=operational_status,
            housekeeping_status=housekeeping_status,
        ),
        status=HousekeepingChecklistStatusEnum(checklist.status),
        version=checklist.version,
        created_at=checklist.created_at,
        completed_at=checklist.completed_at,
        items=[
            HousekeepingChecklistItemRead(
                code=HousekeepingChecklistItemCodeEnum(item.code),
                label=item.label,
                completed=item.completed,
                completed_at=item.completed_at,
            )
            for item in items
        ],
    )


def list_open_checklists(db: Session, *, hotel_id: int) -> HousekeepingChecklistListRead:
    """Return only open checklists belonging to the authenticated hotel."""
    checklists = (
        db.query(HousekeepingChecklist)
        .filter(
            HousekeepingChecklist.hotel_id == hotel_id,
            HousekeepingChecklist.status == HousekeepingChecklistStatusEnum.OPEN.value,
        )
        .order_by(HousekeepingChecklist.created_at.asc(), HousekeepingChecklist.id.asc())
        .all()
    )

    if not checklists:
        return HousekeepingChecklistListRead(checklists=[])

    checklist_ids = [checklist.id for checklist in checklists]
    room_ids = {checklist.room_id for checklist in checklists}
    rooms_by_id = {
        row.id: row
        for row in (
            db.query(
                Room.id,
                Room.room_number,
                Room.status,
                Room.housekeeping_status,
            )
            .filter(Room.hotel_id == hotel_id, Room.id.in_(room_ids))
            .all()
        )
    }
    items_by_checklist_id: dict[int, list[HousekeepingChecklistItem]] = {
        checklist_id: [] for checklist_id in checklist_ids
    }
    items = (
        db.query(HousekeepingChecklistItem)
        .filter(
            HousekeepingChecklistItem.hotel_id == hotel_id,
            HousekeepingChecklistItem.checklist_id.in_(checklist_ids),
        )
        .order_by(HousekeepingChecklistItem.id.asc())
        .all()
    )
    for item in items:
        items_by_checklist_id[item.checklist_id].append(item)

    serialized_checklists: list[HousekeepingChecklistRead] = []
    for checklist in checklists:
        room = rooms_by_id.get(checklist.room_id)
        if room is None:
            raise HousekeepingChecklistNotFound("No se encontró la habitación del checklist")
        serialized_checklists.append(
            _build_checklist_read(
                checklist=checklist,
                room_id=room.id,
                room_number=room.room_number,
                operational_status=room.status,
                housekeeping_status=room.housekeeping_status,
                items=items_by_checklist_id[checklist.id],
            )
        )

    return HousekeepingChecklistListRead(
        checklists=serialized_checklists
    )


def complete_checklist_item(
    db: Session,
    *,
    hotel_id: int,
    checklist_id: int,
    item_code: HousekeepingChecklistItemCodeEnum,
    actor_user_id: int,
) -> HousekeepingChecklistCompletionResult:
    """Mark one fixed item complete, idempotently; the room lock serializes all items."""
    candidate = (
        db.query(HousekeepingChecklist)
        .filter(
            HousekeepingChecklist.id == checklist_id,
            HousekeepingChecklist.hotel_id == hotel_id,
        )
        .one_or_none()
    )
    if candidate is None:
        raise HousekeepingChecklistNotFound("No se encontró el checklist")

    # A stable lock order (room → checklist → item) serializes different item
    # completions and checkout/status mutations for the same physical room.
    room = (
        db.query(Room)
        .filter(Room.id == candidate.room_id, Room.hotel_id == hotel_id)
        .populate_existing()
        .with_for_update(of=Room)
        .one_or_none()
    )
    if room is None:
        raise HousekeepingChecklistNotFound("No se encontró la habitación del checklist")

    checklist = (
        db.query(HousekeepingChecklist)
        .filter(
            HousekeepingChecklist.id == checklist_id,
            HousekeepingChecklist.hotel_id == hotel_id,
            HousekeepingChecklist.room_id == room.id,
        )
        .populate_existing()
        .with_for_update(of=HousekeepingChecklist)
        .one_or_none()
    )
    if checklist is None:
        raise HousekeepingChecklistNotFound("No se encontró el checklist")

    item = (
        db.query(HousekeepingChecklistItem)
        .filter(
            HousekeepingChecklistItem.hotel_id == hotel_id,
            HousekeepingChecklistItem.checklist_id == checklist.id,
            HousekeepingChecklistItem.code == item_code.value,
        )
        .populate_existing()
        .with_for_update(of=HousekeepingChecklistItem)
        .one_or_none()
    )
    if item is None:
        raise HousekeepingChecklistNotFound("No se encontró el punto del checklist")

    if item.completed or checklist.status == HousekeepingChecklistStatusEnum.COMPLETED.value:
        return HousekeepingChecklistCompletionResult(
            checklist=_read_checklist(db, checklist=checklist, room=room),
            changed=False,
            completed_now=False,
        )
    if room.status == RoomStatusEnum.OCCUPIED:
        raise HousekeepingChecklistConflict("No se puede completar la limpieza mientras la habitación está ocupada")
    if checklist.status != HousekeepingChecklistStatusEnum.OPEN.value:
        raise HousekeepingChecklistConflict("El checklist no está abierto")

    now = datetime.now(UTC)
    item_before = {"code": item.code, "completed": item.completed}
    item.completed = True
    item.completed_at = now
    item.completed_by_user_id = actor_user_id
    checklist.version += 1
    db.flush()
    audit_log_service.create_audit_log(
        db,
        hotel_id=hotel_id,
        table_name="housekeeping_checklist_items",
        record_id=item.id,
        action=AuditActionEnum.STATUS_CHANGE,
        actor_user_id=actor_user_id,
        payload_before=item_before,
        payload_after={"code": item.code, "completed": True, "checklist_id": checklist.id},
    )

    all_items = (
        db.query(HousekeepingChecklistItem)
        .filter(
            HousekeepingChecklistItem.hotel_id == hotel_id,
            HousekeepingChecklistItem.checklist_id == checklist.id,
        )
        .order_by(HousekeepingChecklistItem.id.asc())
        .all()
    )
    item_codes = {checklist_item.code for checklist_item in all_items}
    all_complete = (
        len(all_items) == len(REQUIRED_HOUSEKEEPING_CHECKLIST_CODES)
        and item_codes == REQUIRED_HOUSEKEEPING_CHECKLIST_CODES
        and all(checklist_item.completed for checklist_item in all_items)
    )

    if not all_complete:
        if room.housekeeping_status != RoomHousekeepingStatusEnum.IN_PROGRESS:
            mutate_room_state(
                db,
                room=room,
                hotel_id=hotel_id,
                housekeeping_status=RoomHousekeepingStatusEnum.IN_PROGRESS,
                actor_user_id=actor_user_id,
            )
        db.flush()
        return HousekeepingChecklistCompletionResult(
            checklist=_read_checklist(db, checklist=checklist, room=room),
            changed=True,
            completed_now=False,
        )

    checklist.status = HousekeepingChecklistStatusEnum.COMPLETED.value
    checklist.completed_at = now
    checklist.completed_by_user_id = actor_user_id
    db.flush()
    audit_log_service.create_audit_log(
        db,
        hotel_id=hotel_id,
        table_name="housekeeping_checklists",
        record_id=checklist.id,
        action=AuditActionEnum.STATUS_CHANGE,
        actor_user_id=actor_user_id,
        payload_before={"status": HousekeepingChecklistStatusEnum.OPEN.value},
        payload_after={
            "status": HousekeepingChecklistStatusEnum.COMPLETED.value,
            "version": checklist.version,
        },
    )

    # Completing housekeeping only releases a room that is currently in the
    # cleaning state. Maintenance and blocked rooms can be clean while their
    # operational restriction remains in place.
    try:
        mutate_room_state(
            db,
            room=room,
            hotel_id=hotel_id,
            status=RoomStatusEnum.AVAILABLE if room.status == RoomStatusEnum.CLEANING else None,
            housekeeping_status=RoomHousekeepingStatusEnum.CLEAN,
            actor_user_id=actor_user_id,
        )
    except RoomStateTransitionError as exc:
        raise HousekeepingChecklistConflict(str(exc)) from exc

    db.flush()

    return HousekeepingChecklistCompletionResult(
        checklist=_read_checklist(db, checklist=checklist, room=room),
        changed=True,
        completed_now=True,
    )
