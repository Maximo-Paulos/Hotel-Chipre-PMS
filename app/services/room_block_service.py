from __future__ import annotations

import json
import logging
from collections.abc import Collection
from datetime import date, datetime, timezone

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.allocation import (
    AllocationAssignment,
    AllocationAssignmentStatusEnum,
    AllocationExplanation,
    ReservationAllocationLock,
)
from app.models.operational_task import (
    OperationalTask,
    OperationalTaskStatusEnum,
    OperationalTaskTypeEnum,
)
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.room import Room, RoomStatusEnum
from app.models.room_block import RoomBlock, RoomBlockReasonEnum
from app.services.read_model_cache import invalidate_hotel_operational_caches
from app.services.row_locks import lock_query

logger = logging.getLogger(__name__)


def _load_json_dict(raw_value: str | None) -> dict:
    if not raw_value:
        return {}
    try:
        loaded = json.loads(raw_value)
    except (TypeError, json.JSONDecodeError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


class RoomBlockError(Exception):
    """Base error for room-block business rules."""


class ProtectedReservationConflictError(RoomBlockError):
    """Raised when a new block overlaps reservations that require manual review."""

    def __init__(self, reservation_ids: list[int]):
        self.reservation_ids = reservation_ids
        super().__init__(
            "Room block overlaps protected or checked-in reservations that require manual resolution"
        )


class RoomBlockReservationConflictError(RoomBlockError):
    """Raised when any active reservation still occupies the requested window."""

    def __init__(self, reservation_ids: list[int]):
        self.reservation_ids = reservation_ids
        super().__init__("Room block still overlaps active reservations; reassign them first")


class RoomBlockAlreadyExistsError(RoomBlockError):
    """Raised when an unresolved block already covers the requested window."""


class RoomBlockReleaseConflictError(RoomBlockError):
    """Raised when releasing a block would make an unsafe room state appear sellable."""

    def __init__(
        self,
        *,
        reservation_ids: list[int] | None = None,
        other_block_ids: list[int] | None = None,
        reason: str,
    ):
        self.reservation_ids = reservation_ids or []
        self.other_block_ids = other_block_ids or []
        self.reason = reason
        super().__init__(reason)


def _protected_reservation_filter():
    return or_(
        Reservation.status.in_(
            (ReservationStatusEnum.PARTIAL_CHECK_IN, ReservationStatusEnum.CHECKED_IN)
        ),
        Reservation.actual_check_in.is_not(None),
        Reservation.allocation_locked.is_(True),
    )


def _invalidate_availability_cache(hotel_id: int) -> None:
    try:
        invalidate_hotel_operational_caches(hotel_id)
    except Exception as exc:  # pragma: no cover - defensive cache isolation
        logger.debug(
            "room_block.availability_cache_invalidation_failed",
            extra={"hotel_id": hotel_id, "error_type": type(exc).__name__},
        )


class RoomBlockExtensionConflictError(RoomBlockError):
    """Extending would overlap a stay without an accepted allocation plan."""

    def __init__(
        self,
        *,
        reservation_count: int = 0,
        protected_reservation_count: int = 0,
        overlapping_block_count: int = 0,
    ):
        self.reservation_count = reservation_count
        self.protected_reservation_count = protected_reservation_count
        self.overlapping_block_count = overlapping_block_count
        super().__init__("La extensión necesita una propuesta válida de reasignación antes de guardarse")


def _validate_range(starts_at: date, ends_at: date | None, is_indefinite: bool) -> None:
    if ends_at is None and not is_indefinite:
        raise RoomBlockError("ends_at is required unless the block is indefinite")
    if ends_at is not None and ends_at <= starts_at:
        raise RoomBlockError("ends_at must be after starts_at")
    if is_indefinite and ends_at is not None:
        raise RoomBlockError("indefinite room blocks cannot have ends_at")


def _overlaps_window(starts_at: date, ends_at: date | None, window_start: date, window_end: date):
    return starts_at < window_end and (ends_at is None or ends_at > window_start)


def room_block_overlap_filter(start_date: date, end_date: date):
    """SQLAlchemy predicate for unresolved blocks overlapping [start_date, end_date)."""

    return (
        RoomBlock.resolved_at.is_(None),
        RoomBlock.starts_at < end_date,
        or_(RoomBlock.ends_at.is_(None), RoomBlock.ends_at > start_date),
    )


def blocked_room_ids_for_range(
    db: Session,
    *,
    hotel_id: int,
    start_date: date,
    end_date: date,
    room_ids: Collection[int] | None = None,
) -> set[int]:
    filters = [RoomBlock.hotel_id == hotel_id, *room_block_overlap_filter(start_date, end_date)]
    if room_ids:
        filters.append(RoomBlock.room_id.in_(room_ids))
    rows = db.query(RoomBlock.room_id).filter(*filters).all()
    return {row[0] for row in rows}


def room_has_active_block(db: Session, *, hotel_id: int, room_id: int, start_date: date, end_date: date) -> bool:
    return (
        db.query(RoomBlock.id)
        .filter(
            RoomBlock.hotel_id == hotel_id,
            RoomBlock.room_id == room_id,
            *room_block_overlap_filter(start_date, end_date),
        )
        .first()
        is not None
    )


def _protected_reservation_ids_for_block(
    db: Session,
    *,
    hotel_id: int,
    room_id: int,
    starts_at: date,
    ends_at: date | None,
) -> list[int]:
    from app.services.reservation_service import active_reservations

    conflict_window_end = ends_at or date.max
    overlapping_ids = {
        row[0]
        for row in (
            active_reservations(db, hotel_id)
            .with_entities(Reservation.id)
            .filter(
                Reservation.room_id == room_id,
                Reservation.status.notin_([ReservationStatusEnum.CANCELLED, ReservationStatusEnum.CHECKED_OUT]),
                Reservation.check_in_date < conflict_window_end,
                Reservation.check_out_date > starts_at,
            )
            .all()
        )
    }
    protected_ids = {
        row[0]
        for row in (
            active_reservations(db, hotel_id)
            .with_entities(Reservation.id)
            .filter(
                Reservation.room_id == room_id,
                Reservation.status.notin_([ReservationStatusEnum.CANCELLED, ReservationStatusEnum.CHECKED_OUT]),
                Reservation.check_in_date < conflict_window_end,
                Reservation.check_out_date > starts_at,
                _protected_reservation_filter(),
            )
            .order_by(Reservation.id.asc())
            .all()
        )
    }
    active_lock_ids = {
        row[0]
        for row in db.query(ReservationAllocationLock.reservation_id)
        .filter(
            ReservationAllocationLock.hotel_id == hotel_id,
            ReservationAllocationLock.is_active.is_(True),
        )
        .all()
    }
    return sorted((protected_ids | active_lock_ids) & overlapping_ids)


def _overlapping_reservation_ids_for_block(
    db: Session,
    *,
    hotel_id: int,
    room_id: int,
    starts_at: date,
    ends_at: date | None,
) -> list[int]:
    from app.services.reservation_service import active_reservations

    conflict_window_end = ends_at or date.max
    overlapping = active_reservations(db, hotel_id).filter(
        Reservation.room_id == room_id,
        Reservation.status.notin_([ReservationStatusEnum.CANCELLED, ReservationStatusEnum.CHECKED_OUT]),
        Reservation.check_in_date < conflict_window_end,
        Reservation.check_out_date > starts_at,
    )
    return [
        row[0]
        for row in overlapping.with_entities(Reservation.id).order_by(Reservation.id.asc()).all()
    ]


def get_block_conflicting_reservation_ids(
    db: Session,
    *,
    hotel_id: int,
    room_id: int,
    starts_at: date,
    ends_at: date | None = None,
    is_indefinite: bool = False,
) -> list[int]:
    _validate_range(starts_at, ends_at, is_indefinite)
    if db.query(Room.id).filter(Room.hotel_id == hotel_id, Room.id == room_id).first() is None:
        raise RoomBlockError("Room not found")
    if room_has_active_block(
        db,
        hotel_id=hotel_id,
        room_id=room_id,
        start_date=starts_at,
        end_date=ends_at or date.max,
    ):
        raise RoomBlockAlreadyExistsError("An active room block already overlaps this window")
    return _overlapping_reservation_ids_for_block(
        db,
        hotel_id=hotel_id,
        room_id=room_id,
        starts_at=starts_at,
        ends_at=ends_at if not is_indefinite else None,
    )


def propose_room_block_reassignment(
    db: Session,
    *,
    hotel_id: int,
    room_id: int,
    starts_at: date,
    ends_at: date | None,
    is_indefinite: bool,
):
    """Ask the allocation motor for a human-reviewed room-block plan."""
    from app.services.allocation_runtime_service import (
        AllocationRuntimeError,
        get_allocation_run_details,
        run_persisted_allocation,
    )
    from app.services.reservation_service import active_reservations
    from app.services.timezones import hotel_today

    conflicts = get_block_conflicting_reservation_ids(
        db,
        hotel_id=hotel_id,
        room_id=room_id,
        starts_at=starts_at,
        ends_at=ends_at,
        is_indefinite=is_indefinite,
    )
    if not conflicts:
        return None
    conflict_reservations = active_reservations(db, hotel_id).filter(Reservation.id.in_(conflicts)).all()
    window_end = ends_at or date.max
    reservations_in_window = {
        row[0]
        for row in active_reservations(db, hotel_id)
        .with_entities(Reservation.id)
        .filter(
            Reservation.status.notin_([ReservationStatusEnum.CANCELLED, ReservationStatusEnum.CHECKED_OUT]),
            Reservation.check_in_date < window_end,
            Reservation.check_out_date > starts_at,
        )
        .all()
    }
    horizon_start = min([starts_at, *(item.check_in_date for item in conflict_reservations)])
    horizon_end = max(
        [ends_at or starts_at, *(item.check_out_date for item in conflict_reservations)]
    )
    if horizon_end <= horizon_start:
        raise RoomBlockError("Room block proposal has an invalid allocation horizon")
    context = {
        "kind": "room_block",
        "block": {
            "room_id": room_id,
            "starts_at": starts_at.isoformat(),
            "ends_at": ends_at.isoformat() if ends_at else None,
            "is_indefinite": is_indefinite,
        },
        "conflict_reservation_ids": sorted(conflicts),
        "generated_at_hotel_date": hotel_today(db, hotel_id).isoformat(),
    }
    with db.begin_nested():
        persisted = run_persisted_allocation(
            db,
            hotel_id=hotel_id,
            trigger_type="room_block_proposal",
            apply=False,
            horizon_start=horizon_start,
            horizon_end=horizon_end,
            forbidden_room_ids_by_reservation={item_id: {room_id} for item_id in reservations_in_window},
            proposal_context=context,
        )
        if not persisted.solver_result.success:
            raise RoomBlockReservationConflictError(sorted(conflicts))
        proposal_rows = (
            db.query(AllocationAssignment)
            .filter(
                AllocationAssignment.hotel_id == hotel_id,
                AllocationAssignment.allocation_run_id == persisted.run.id,
                AllocationAssignment.reservation_id.in_(conflicts),
            )
            .all()
        )
        proposed_ids = {
            row.reservation_id
            for row in proposal_rows
            if row.status == AllocationAssignmentStatusEnum.PROPOSED
            and row.room_id is not None
            and row.room_id != room_id
        }
        if proposed_ids != set(conflicts):
            raise RoomBlockReservationConflictError(sorted(set(conflicts) - proposed_ids))
        details = get_allocation_run_details(db, hotel_id=hotel_id, run_id=persisted.run.id)
        if details is None:
            raise AllocationRuntimeError("Allocation run could not be loaded")
        return details


def _raise_for_protected_reservations(reservation_ids: list[int]) -> None:
    if reservation_ids:
        raise ProtectedReservationConflictError(reservation_ids)


def _lock_room_for_block_mutation(db: Session, *, hotel_id: int, room_id: int) -> Room | None:
    """Lock a tenant-scoped room; all block mutations take this lock first."""
    query = db.query(Room).filter(Room.id == room_id, Room.hotel_id == hotel_id).populate_existing()
    return lock_query(query, Room).one_or_none()


def _read_block_room_id(db: Session, *, hotel_id: int, block_id: int) -> int:
    room_id = (
        db.query(RoomBlock.room_id)
        .filter(RoomBlock.hotel_id == hotel_id, RoomBlock.id == block_id)
        .scalar()
    )
    if room_id is None:
        raise RoomBlockError("Room block not found")
    return room_id


def _lock_room_then_block(db: Session, *, hotel_id: int, block_id: int) -> tuple[Room, RoomBlock]:
    """Acquire mutation locks in the shared order: Room, then RoomBlock."""
    candidate_room_id = _read_block_room_id(db, hotel_id=hotel_id, block_id=block_id)
    room = _lock_room_for_block_mutation(db, hotel_id=hotel_id, room_id=candidate_room_id)
    if room is None:
        raise RoomBlockError("La habitación del bloqueo ya no está disponible")

    block_query = (
        db.query(RoomBlock)
        .filter(RoomBlock.hotel_id == hotel_id, RoomBlock.id == block_id)
        .populate_existing()
    )
    block = lock_query(block_query, RoomBlock).one_or_none()
    if block is None:
        raise RoomBlockError("Room block not found")
    if block.room_id != room.id:
        # A block's target room should be immutable. If it changed between the
        # initial read and lock acquisition, retry after releasing this tx;
        # acquiring a second Room now would invert the global lock order.
        raise RoomBlockError("La habitación del bloqueo cambió; reintentá la operación")
    return room, block


def create_block(
    db: Session,
    *,
    hotel_id: int,
    room_id: int,
    starts_at: date,
    ends_at: date | None = None,
    is_indefinite: bool = False,
    reason_code: RoomBlockReasonEnum = RoomBlockReasonEnum.OTHER,
    reason_note: str | None = None,
    created_by_user_id: int | None = None,
) -> RoomBlock:
    _validate_range(starts_at, ends_at, is_indefinite)

    room_exists = db.query(Room.id).filter(Room.id == room_id, Room.hotel_id == hotel_id).first()
    if room_exists is None:
        raise RoomBlockError("Room not found")

    # Fail quickly for occupied nights, then lock the room and repeat against
    # the post-wait state. The optimizer proposal flow must clear every active
    # stay before this operation can persist a maintenance block.
    conflicts = _overlapping_reservation_ids_for_block(
            db,
            hotel_id=hotel_id,
            room_id=room_id,
            starts_at=starts_at,
            ends_at=ends_at if not is_indefinite else None,
        )
    if conflicts:
        if set(conflicts) & set(_protected_reservation_ids_for_block(
            db,
            hotel_id=hotel_id,
            room_id=room_id,
            starts_at=starts_at,
            ends_at=ends_at if not is_indefinite else None,
        )):
            raise ProtectedReservationConflictError(conflicts)
        raise RoomBlockReservationConflictError(conflicts)

    room = _lock_room_for_block_mutation(db, hotel_id=hotel_id, room_id=room_id)
    if room is None:
        raise RoomBlockError("Room not found")
    conflicts = _overlapping_reservation_ids_for_block(
            db,
            hotel_id=hotel_id,
            room_id=room_id,
            starts_at=starts_at,
            ends_at=ends_at if not is_indefinite else None,
        )
    if conflicts:
        protected_ids = set(_protected_reservation_ids_for_block(
            db,
            hotel_id=hotel_id,
            room_id=room_id,
            starts_at=starts_at,
            ends_at=ends_at if not is_indefinite else None,
        ))
        if set(conflicts) & protected_ids:
            raise ProtectedReservationConflictError(conflicts)
        raise RoomBlockReservationConflictError(conflicts)

    window_end = ends_at or date.max
    existing_block = db.query(RoomBlock.id).filter(
        RoomBlock.hotel_id == hotel_id,
        RoomBlock.room_id == room_id,
        RoomBlock.resolved_at.is_(None),
        RoomBlock.starts_at < window_end,
        or_(RoomBlock.ends_at.is_(None), RoomBlock.ends_at > starts_at),
    ).first()
    if existing_block:
        raise RoomBlockAlreadyExistsError("An active room block already overlaps this window")

    block = RoomBlock(
        hotel_id=hotel_id,
        room_id=room_id,
        starts_at=starts_at,
        ends_at=ends_at,
        is_indefinite=is_indefinite,
        reason_code=reason_code,
        reason_note=reason_note,
        created_by_user_id=created_by_user_id,
    )
    db.add(block)
    db.flush()
    _invalidate_availability_cache(hotel_id)
    return block


def create_block_with_allocation_plan(
    db: Session,
    *,
    hotel_id: int,
    room_id: int,
    starts_at: date,
    ends_at: date | None,
    is_indefinite: bool,
    reason_code: RoomBlockReasonEnum,
    reason_note: str | None,
    created_by_user_id: int | None,
    allocation_run_id: int | None,
) -> RoomBlock:
    """Create a maintenance block only after its exact solver plan is accepted.

    Plan acceptance and block insertion share one transaction/savepoint. Any
    stale conflict set, solver rejection, or final block validation rolls back
    every proposed room move with the block.
    """
    from app.services.allocation_runtime_service import (
        AllocationRuntimeError,
        accept_allocation_run,
    )

    _validate_range(starts_at, ends_at, is_indefinite)
    with db.begin_nested():
        conflicts = get_block_conflicting_reservation_ids(
            db,
            hotel_id=hotel_id,
            room_id=room_id,
            starts_at=starts_at,
            ends_at=ends_at,
            is_indefinite=is_indefinite,
        )
        if allocation_run_id is None:
            if conflicts:
                protected_ids = set(
                    _protected_reservation_ids_for_block(
                        db,
                        hotel_id=hotel_id,
                        room_id=room_id,
                        starts_at=starts_at,
                        ends_at=ends_at if not is_indefinite else None,
                    )
                )
                if set(conflicts) & protected_ids:
                    raise ProtectedReservationConflictError(conflicts)
                raise RoomBlockReservationConflictError(conflicts)
            return create_block(
                db,
                hotel_id=hotel_id,
                room_id=room_id,
                starts_at=starts_at,
                ends_at=ends_at,
                is_indefinite=is_indefinite,
                reason_code=reason_code,
                reason_note=reason_note,
                created_by_user_id=created_by_user_id,
            )

        context_row = (
            db.query(AllocationExplanation)
            .filter(
                AllocationExplanation.hotel_id == hotel_id,
                AllocationExplanation.allocation_run_id == allocation_run_id,
                AllocationExplanation.explanation_type == "proposal_context",
            )
            .order_by(AllocationExplanation.id.asc())
            .first()
        )
        if context_row is None:
            raise RoomBlockError("Allocation run is not a room-block proposal")
        try:
            proposal_context = json.loads(context_row.details_json or "{}")
        except (TypeError, json.JSONDecodeError) as exc:
            raise RoomBlockError("Allocation run has invalid room-block proposal context") from exc
        if not isinstance(proposal_context, dict):
            raise RoomBlockError("Allocation run has invalid room-block proposal context")
        expected_block = {
            "room_id": room_id,
            "starts_at": starts_at.isoformat(),
            "ends_at": ends_at.isoformat() if ends_at else None,
            "is_indefinite": is_indefinite,
        }
        if proposal_context.get("kind") != "room_block" or proposal_context.get("block") != expected_block:
            raise RoomBlockError("Allocation proposal does not match this room block")
        expected_conflicts = set(proposal_context.get("conflict_reservation_ids") or [])
        if not expected_conflicts or set(conflicts) != expected_conflicts:
            raise RoomBlockReservationConflictError(conflicts or sorted(expected_conflicts))

        assignment_rows = (
            db.query(AllocationAssignment)
            .filter(
                AllocationAssignment.hotel_id == hotel_id,
                AllocationAssignment.allocation_run_id == allocation_run_id,
                AllocationAssignment.reservation_id.in_(expected_conflicts),
            )
            .all()
        )
        movable_conflicts = {
            row.reservation_id
            for row in assignment_rows
            if row.status == AllocationAssignmentStatusEnum.PROPOSED
            and row.room_id is not None
            and row.room_id != room_id
        }
        if movable_conflicts != expected_conflicts:
            raise RoomBlockReservationConflictError(sorted(expected_conflicts - movable_conflicts))

        try:
            accept_allocation_run(
                db,
                hotel_id=hotel_id,
                run_id=allocation_run_id,
                user_id=created_by_user_id,
                allow_room_block_plan=True,
            )
        except AllocationRuntimeError as exc:
            raise RoomBlockError(str(exc)) from exc

        return create_block(
            db,
            hotel_id=hotel_id,
            room_id=room_id,
            starts_at=starts_at,
            ends_at=ends_at,
            is_indefinite=is_indefinite,
            reason_code=reason_code,
            reason_note=reason_note,
            created_by_user_id=created_by_user_id,
        )


def preview_block_conflicts(
    db: Session,
    *,
    hotel_id: int,
    room_id: int,
    starts_at: date,
    ends_at: date | None = None,
    is_indefinite: bool = False,
) -> dict[str, int]:
    """Count active reservations overlapping a proposed block without returning guest data."""
    from app.services.reservation_service import active_reservations

    _validate_range(starts_at, ends_at, is_indefinite)
    room_exists = db.query(Room.id).filter(Room.id == room_id, Room.hotel_id == hotel_id).first()
    if room_exists is None:
        raise RoomBlockError("Room not found")

    conflict_window_end = ends_at or date.max
    overlapping = active_reservations(db, hotel_id).filter(
        Reservation.room_id == room_id,
        Reservation.status.notin_([ReservationStatusEnum.CANCELLED, ReservationStatusEnum.CHECKED_OUT]),
        Reservation.check_in_date < conflict_window_end,
        Reservation.check_out_date > starts_at,
    )
    protected_count = len(
        _protected_reservation_ids_for_block(
            db,
            hotel_id=hotel_id,
            room_id=room_id,
            starts_at=starts_at,
            ends_at=conflict_window_end,
        )
    )
    return {
        "reservation_count": overlapping.count(),
        "protected_reservation_count": protected_count,
    }


def list_active_blocks(
    db: Session,
    *,
    hotel_id: int,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[RoomBlock]:
    query = db.query(RoomBlock).filter(RoomBlock.hotel_id == hotel_id, RoomBlock.resolved_at.is_(None))
    if start_date is not None and end_date is not None:
        if end_date <= start_date:
            raise RoomBlockError("end_date must be after start_date")
        query = query.filter(RoomBlock.starts_at < end_date, or_(RoomBlock.ends_at.is_(None), RoomBlock.ends_at > start_date))
    return query.order_by(RoomBlock.starts_at.asc(), RoomBlock.id.asc()).all()


def get_block(db: Session, *, hotel_id: int, block_id: int) -> RoomBlock:
    block = db.query(RoomBlock).filter(RoomBlock.id == block_id, RoomBlock.hotel_id == hotel_id).first()
    if block is None:
        raise RoomBlockError("Room block not found")
    return block


def preview_block_extension(
    db: Session,
    *,
    hotel_id: int,
    block_id: int,
    ends_at: date,
) -> dict[str, int]:
    """Count conflicts in the newly added half-open window [old_end, ends_at)."""
    block = get_block(db, hotel_id=hotel_id, block_id=block_id)
    return _preview_block_extension_for_block(db, hotel_id=hotel_id, block=block, ends_at=ends_at)


def _preview_block_extension_for_block(
    db: Session,
    *,
    hotel_id: int,
    block: RoomBlock,
    ends_at: date,
) -> dict[str, int]:
    if block.resolved_at is not None or block.is_indefinite or block.ends_at is None:
        raise RoomBlockError("Solo se pueden extender bloqueos activos con fecha de fin")
    if ends_at <= block.ends_at:
        raise RoomBlockError("La nueva fecha debe ser posterior a la fecha de fin actual")

    from app.services.reservation_service import active_reservations

    overlapping = active_reservations(db, hotel_id).filter(
        Reservation.room_id == block.room_id,
        Reservation.status.notin_([ReservationStatusEnum.CANCELLED, ReservationStatusEnum.CHECKED_OUT]),
        Reservation.check_in_date < ends_at,
        Reservation.check_out_date > block.ends_at,
    )
    protected_count = len(
        _protected_reservation_ids_for_block(
            db,
            hotel_id=hotel_id,
            room_id=block.room_id,
            starts_at=block.ends_at,
            ends_at=ends_at,
        )
    )
    other_blocks = (
        db.query(RoomBlock.id)
        .filter(
            RoomBlock.hotel_id == hotel_id,
            RoomBlock.room_id == block.room_id,
            RoomBlock.id != block.id,
            RoomBlock.resolved_at.is_(None),
            RoomBlock.starts_at < ends_at,
            or_(RoomBlock.ends_at.is_(None), RoomBlock.ends_at > block.ends_at),
        )
    )
    return {
        "reservation_count": overlapping.count(),
        "protected_reservation_count": protected_count,
        "overlapping_block_count": other_blocks.count(),
    }


def propose_room_block_extension_reassignment(
    db: Session,
    *,
    hotel_id: int,
    block_id: int,
    ends_at: date,
):
    """Generate a human-reviewed allocation plan for the added block window."""
    from app.services.allocation_runtime_service import (
        AllocationRuntimeError,
        get_allocation_run_details,
        run_persisted_allocation,
    )
    from app.services.reservation_service import active_reservations
    from app.services.timezones import hotel_today

    block = get_block(db, hotel_id=hotel_id, block_id=block_id)
    conflicts = _preview_block_extension_for_block(
        db,
        hotel_id=hotel_id,
        block=block,
        ends_at=ends_at,
    )
    if conflicts["overlapping_block_count"]:
        raise RoomBlockExtensionConflictError(
            reservation_count=conflicts["reservation_count"],
            protected_reservation_count=conflicts["protected_reservation_count"],
            overlapping_block_count=conflicts["overlapping_block_count"],
        )

    conflict_ids = _overlapping_reservation_ids_for_block(
        db,
        hotel_id=hotel_id,
        room_id=block.room_id,
        starts_at=block.ends_at,
        ends_at=ends_at,
    )
    if not conflict_ids:
        return None
    protected_ids = set(
        _protected_reservation_ids_for_block(
            db,
            hotel_id=hotel_id,
            room_id=block.room_id,
            starts_at=block.ends_at,
            ends_at=ends_at,
        )
    )
    if protected_ids.intersection(conflict_ids):
        raise ProtectedReservationConflictError(sorted(protected_ids.intersection(conflict_ids)))

    conflict_reservations = active_reservations(db, hotel_id).filter(
        Reservation.id.in_(conflict_ids)
    ).all()
    reservations_in_window = {
        row[0]
        for row in active_reservations(db, hotel_id)
        .with_entities(Reservation.id)
        .filter(
            Reservation.status.notin_([ReservationStatusEnum.CANCELLED, ReservationStatusEnum.CHECKED_OUT]),
            Reservation.check_in_date < ends_at,
            Reservation.check_out_date > block.ends_at,
        )
        .all()
    }
    horizon_start = min([block.ends_at, *(item.check_in_date for item in conflict_reservations)])
    horizon_end = max([ends_at, *(item.check_out_date for item in conflict_reservations)])
    if horizon_end <= horizon_start:
        raise RoomBlockError("Room block extension proposal has an invalid allocation horizon")

    context = {
        "kind": "room_block_extension",
        "block": {
            "block_id": block.id,
            "room_id": block.room_id,
            "previous_ends_at": block.ends_at.isoformat(),
            "ends_at": ends_at.isoformat(),
        },
        "conflict_reservation_ids": sorted(conflict_ids),
        "generated_at_hotel_date": hotel_today(db, hotel_id).isoformat(),
    }
    with db.begin_nested():
        persisted = run_persisted_allocation(
            db,
            hotel_id=hotel_id,
            trigger_type="room_block_extension_proposal",
            apply=False,
            horizon_start=horizon_start,
            horizon_end=horizon_end,
            forbidden_room_ids_by_reservation={
                reservation_id: {block.room_id} for reservation_id in reservations_in_window
            },
            proposal_context=context,
        )
        if not persisted.solver_result.success:
            raise RoomBlockExtensionConflictError(
                reservation_count=len(conflict_ids),
                protected_reservation_count=conflicts["protected_reservation_count"],
            )
        proposal_rows = (
            db.query(AllocationAssignment)
            .filter(
                AllocationAssignment.hotel_id == hotel_id,
                AllocationAssignment.allocation_run_id == persisted.run.id,
                AllocationAssignment.reservation_id.in_(conflict_ids),
            )
            .all()
        )
        proposed_ids = {
            row.reservation_id
            for row in proposal_rows
            if row.status == AllocationAssignmentStatusEnum.PROPOSED
            and row.room_id is not None
            and row.room_id != block.room_id
        }
        if proposed_ids != set(conflict_ids):
            raise RoomBlockExtensionConflictError(
                reservation_count=len(set(conflict_ids) - proposed_ids),
                protected_reservation_count=conflicts["protected_reservation_count"],
            )
        details = get_allocation_run_details(db, hotel_id=hotel_id, run_id=persisted.run.id)
        if details is None:
            raise AllocationRuntimeError("Allocation run could not be loaded")
        return details


def extend_block_with_allocation_plan(
    db: Session,
    *,
    hotel_id: int,
    block_id: int,
    ends_at: date,
    allocation_run_id: int | None,
    created_by_user_id: int | None = None,
) -> RoomBlock:
    """Accept a fresh extension plan and extend the block in one transaction."""
    from app.services.allocation_runtime_service import (
        AllocationRuntimeError,
        accept_allocation_run,
    )

    with db.begin_nested():
        _room, block = _lock_room_then_block(db, hotel_id=hotel_id, block_id=block_id)
        current = _preview_block_extension_for_block(
            db,
            hotel_id=hotel_id,
            block=block,
            ends_at=ends_at,
        )
        if current["overlapping_block_count"]:
            raise RoomBlockExtensionConflictError(
                reservation_count=current["reservation_count"],
                protected_reservation_count=current["protected_reservation_count"],
                overlapping_block_count=current["overlapping_block_count"],
            )

        conflict_ids = _overlapping_reservation_ids_for_block(
            db,
            hotel_id=hotel_id,
            room_id=block.room_id,
            starts_at=block.ends_at,
            ends_at=ends_at,
        )
        protected_ids = set(
            _protected_reservation_ids_for_block(
                db,
                hotel_id=hotel_id,
                room_id=block.room_id,
                starts_at=block.ends_at,
                ends_at=ends_at,
            )
        )
        if protected_ids.intersection(conflict_ids):
            raise RoomBlockExtensionConflictError(
                reservation_count=len(conflict_ids),
                protected_reservation_count=len(protected_ids.intersection(conflict_ids)),
            )
        if allocation_run_id is None:
            if conflict_ids:
                raise RoomBlockExtensionConflictError(
                    reservation_count=len(conflict_ids),
                    protected_reservation_count=current["protected_reservation_count"],
                )
        else:
            context_row = (
                db.query(AllocationExplanation)
                .filter(
                    AllocationExplanation.hotel_id == hotel_id,
                    AllocationExplanation.allocation_run_id == allocation_run_id,
                    AllocationExplanation.explanation_type == "proposal_context",
                )
                .order_by(AllocationExplanation.id.asc())
                .first()
            )
            proposal_context = _load_json_dict(context_row.details_json) if context_row else {}
            expected_block = {
                "block_id": block.id,
                "room_id": block.room_id,
                "previous_ends_at": block.ends_at.isoformat(),
                "ends_at": ends_at.isoformat(),
            }
            expected_conflicts = set(proposal_context.get("conflict_reservation_ids") or [])
            if (
                proposal_context.get("kind") != "room_block_extension"
                or proposal_context.get("block") != expected_block
                or not expected_conflicts
                or expected_conflicts != set(conflict_ids)
            ):
                raise RoomBlockExtensionConflictError(
                    reservation_count=len(conflict_ids),
                    protected_reservation_count=current["protected_reservation_count"],
                )

            assignments = (
                db.query(AllocationAssignment)
                .filter(
                    AllocationAssignment.hotel_id == hotel_id,
                    AllocationAssignment.allocation_run_id == allocation_run_id,
                    AllocationAssignment.reservation_id.in_(expected_conflicts),
                )
                .all()
            )
            proposed_ids = {
                assignment.reservation_id
                for assignment in assignments
                if assignment.status == AllocationAssignmentStatusEnum.PROPOSED
                and assignment.room_id is not None
                and assignment.room_id != block.room_id
            }
            if proposed_ids != expected_conflicts:
                raise RoomBlockExtensionConflictError(
                    reservation_count=len(expected_conflicts - proposed_ids),
                    protected_reservation_count=current["protected_reservation_count"],
                )
            try:
                accept_allocation_run(
                    db,
                    hotel_id=hotel_id,
                    run_id=allocation_run_id,
                    user_id=created_by_user_id,
                    allow_room_block_plan=True,
                )
            except AllocationRuntimeError as exc:
                raise RoomBlockError(str(exc)) from exc

            remaining = _overlapping_reservation_ids_for_block(
                db,
                hotel_id=hotel_id,
                room_id=block.room_id,
                starts_at=block.ends_at,
                ends_at=ends_at,
            )
            if remaining:
                raise RoomBlockExtensionConflictError(reservation_count=len(remaining))

        block.ends_at = ends_at
        block.is_indefinite = False
        block.updated_at = datetime.now(timezone.utc)
        db.flush()
        _invalidate_availability_cache(hotel_id)
        return block


def extend_block(
    db: Session,
    *,
    hotel_id: int,
    block_id: int,
    ends_at: date,
) -> RoomBlock:
    """Extend only when the added window has no stays to reassign."""
    return extend_block_with_allocation_plan(
        db,
        hotel_id=hotel_id,
        block_id=block_id,
        ends_at=ends_at,
        allocation_run_id=None,
    )


def resolve_block(
    db: Session,
    *,
    hotel_id: int,
    block_id: int,
    resolved_by_user_id: int | None = None,
) -> RoomBlock:
    candidate_query = (
        db.query(RoomBlock)
        .filter(RoomBlock.hotel_id == hotel_id, RoomBlock.id == block_id)
        .populate_existing()
    )
    candidate = candidate_query.one_or_none()
    if candidate is None:
        raise RoomBlockError("Room block not found")
    if candidate.resolved_at is not None:
        return candidate

    # Preserve the existing fast failure, then repeat every mutable check only
    # after taking Room -> RoomBlock locks.
    candidate_room = (
        db.query(Room)
        .filter(
            Room.id == candidate.room_id,
            Room.hotel_id == hotel_id,
            Room.deleted_at.is_(None),
        )
        .populate_existing()
        .first()
    )
    if candidate_room is None:
        raise RoomBlockError("La habitación del bloqueo ya no está disponible")
    _validate_block_resolution(db, hotel_id=hotel_id, room=candidate_room, block=candidate)

    room, block = _lock_room_then_block(db, hotel_id=hotel_id, block_id=block_id)
    if block.resolved_at is None:
        _validate_block_resolution(db, hotel_id=hotel_id, room=room, block=block)
        block.resolved_at = datetime.now(timezone.utc)
        block.resolved_by_user_id = resolved_by_user_id
        db.flush()
        _invalidate_availability_cache(hotel_id)
    return block


def _validate_block_resolution(db: Session, *, hotel_id: int, room: Room, block: RoomBlock) -> None:
    if room.deleted_at is not None:
        raise RoomBlockError("La habitación del bloqueo ya no está disponible")
    if room.status != RoomStatusEnum.AVAILABLE:
        raise RoomBlockReleaseConflictError(
            reason="La habitación debe estar disponible y lista para vender antes de liberar el bloqueo"
        )

    window_end = block.ends_at or date.max
    other_blocks = (
        db.query(RoomBlock.id)
        .filter(
            RoomBlock.hotel_id == hotel_id,
            RoomBlock.room_id == block.room_id,
            RoomBlock.id != block.id,
            RoomBlock.resolved_at.is_(None),
            RoomBlock.starts_at < window_end,
            or_(RoomBlock.ends_at.is_(None), RoomBlock.ends_at > block.starts_at),
        )
        .order_by(RoomBlock.id.asc())
        .all()
    )
    if other_blocks:
        raise RoomBlockReleaseConflictError(
            other_block_ids=[row[0] for row in other_blocks],
            reason="La habitación todavía tiene otro bloqueo operativo superpuesto",
        )

    pending_maintenance = (
        db.query(OperationalTask.id)
        .filter(
            OperationalTask.hotel_id == hotel_id,
            OperationalTask.room_block_id == block.id,
            OperationalTask.task_type == OperationalTaskTypeEnum.MAINTENANCE,
            OperationalTask.status != OperationalTaskStatusEnum.RESOLVED,
        )
        .order_by(OperationalTask.id.asc())
        .all()
    )
    if pending_maintenance:
        raise RoomBlockReleaseConflictError(
            reason="La incidencia de mantenimiento debe quedar resuelta antes de liberar la habitación"
        )

    affected_reservations = (
        db.query(Reservation.id)
        .filter(
            Reservation.hotel_id == hotel_id,
            Reservation.room_id == block.room_id,
            Reservation.status.notin_(
                [ReservationStatusEnum.CANCELLED, ReservationStatusEnum.CHECKED_OUT, ReservationStatusEnum.NO_SHOW]
            ),
            Reservation.check_in_date < window_end,
            Reservation.check_out_date > block.starts_at,
        )
        .order_by(Reservation.id.asc())
        .all()
    )
    if affected_reservations:
        raise RoomBlockReleaseConflictError(
            reservation_ids=[row[0] for row in affected_reservations],
            reason="La habitación tiene reservas afectadas; reasignalas antes de liberarla",
        )
