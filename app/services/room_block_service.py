from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.room import Room
from app.models.room_block import RoomBlock, RoomBlockReasonEnum


class RoomBlockError(Exception):
    """Base error for room-block business rules."""


class ProtectedReservationConflictError(RoomBlockError):
    """Raised when a new block overlaps reservations that require manual review."""

    def __init__(self, reservation_ids: list[int]):
        self.reservation_ids = reservation_ids
        super().__init__(
            "Room block overlaps protected or checked-in reservations that require manual resolution"
        )


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


def blocked_room_ids_for_range(db: Session, *, hotel_id: int, start_date: date, end_date: date) -> set[int]:
    rows = (
        db.query(RoomBlock.room_id)
        .filter(RoomBlock.hotel_id == hotel_id, *room_block_overlap_filter(start_date, end_date))
        .all()
    )
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

    room = db.query(Room).filter(Room.id == room_id, Room.hotel_id == hotel_id).first()
    if room is None:
        raise RoomBlockError("Room not found")

    conflict_window_end = ends_at or date.max
    protected_reservations = (
        db.query(Reservation.id)
        .filter(
            Reservation.hotel_id == hotel_id,
            Reservation.room_id == room_id,
            Reservation.status.notin_([ReservationStatusEnum.CANCELLED, ReservationStatusEnum.CHECKED_OUT]),
            Reservation.check_in_date < conflict_window_end,
            Reservation.check_out_date > starts_at,
            or_(
                Reservation.status.in_([ReservationStatusEnum.CHECKED_IN, ReservationStatusEnum.PRE_CHECK_IN]),
                Reservation.allocation_locked.is_(True),
                Reservation.company_id.is_not(None),
            ),
        )
        .order_by(Reservation.id.asc())
        .all()
    )
    if protected_reservations:
        raise ProtectedReservationConflictError([row[0] for row in protected_reservations])

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
    return block


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


def resolve_block(
    db: Session,
    *,
    hotel_id: int,
    block_id: int,
    resolved_by_user_id: int | None = None,
) -> RoomBlock:
    block = get_block(db, hotel_id=hotel_id, block_id=block_id)
    if block.resolved_at is None:
        block.resolved_at = datetime.now(timezone.utc)
        block.resolved_by_user_id = resolved_by_user_id
        db.flush()
    return block
