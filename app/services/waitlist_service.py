"""Hotel-scoped waitlist lifecycle service."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.guest import Guest
from app.models.room import RoomCategory
from app.models.waitlist import WaitlistEntry, WaitlistStatusEnum
from app.schemas.reservation import ReservationCreate
from app.schemas.waitlist import WaitlistEntryCreate, WaitlistEntryUpdate
from app.services.reservation_service import ReservationError, create_reservation


class WaitlistError(Exception):
    """Business error for waitlist operations."""


def _get_waitlist_entry(db: Session, hotel_id: int, entry_id: int) -> WaitlistEntry:
    entry = (
        db.query(WaitlistEntry)
        .filter(WaitlistEntry.id == entry_id, WaitlistEntry.hotel_id == hotel_id)
        .first()
    )
    if not entry:
        raise WaitlistError("Waitlist entry not found for this hotel")
    return entry


def add_to_waitlist(db: Session, hotel_id: int, data: WaitlistEntryCreate) -> WaitlistEntry:
    if data.check_out_date <= data.check_in_date:
        raise WaitlistError("Check-out date must be after check-in date")

    guest = db.query(Guest).filter(Guest.id == data.guest_id, Guest.hotel_id == hotel_id).first()
    if not guest:
        raise WaitlistError("Guest not found for this hotel")
    category = (
        db.query(RoomCategory)
        .filter(RoomCategory.id == data.category_id, RoomCategory.hotel_id == hotel_id)
        .first()
    )
    if not category:
        raise WaitlistError("Room category not found for this hotel")

    entry = WaitlistEntry(
        hotel_id=hotel_id,
        guest_id=data.guest_id,
        category_id=data.category_id,
        check_in_date=data.check_in_date,
        check_out_date=data.check_out_date,
        num_adults=data.num_adults,
        num_children=data.num_children,
        status=WaitlistStatusEnum.WAITING,
        priority=data.priority,
        notes=data.notes,
        contact_phone=data.contact_phone,
    )
    db.add(entry)
    db.flush()
    return entry


def list_waitlist_entries(
    db: Session,
    hotel_id: int,
    *,
    status_filter: WaitlistStatusEnum | None = None,
) -> list[WaitlistEntry]:
    query = db.query(WaitlistEntry).filter(WaitlistEntry.hotel_id == hotel_id)
    if status_filter is not None:
        query = query.filter(WaitlistEntry.status == status_filter)
    return query.order_by(WaitlistEntry.priority.asc(), WaitlistEntry.created_at.asc(), WaitlistEntry.id.asc()).all()


def get_waitlist_entry(db: Session, hotel_id: int, entry_id: int) -> WaitlistEntry:
    return _get_waitlist_entry(db, hotel_id, entry_id)


def update_waitlist_entry(
    db: Session,
    hotel_id: int,
    entry_id: int,
    data: WaitlistEntryUpdate,
) -> WaitlistEntry:
    entry = _get_waitlist_entry(db, hotel_id, entry_id)
    if entry.status != WaitlistStatusEnum.WAITING:
        raise WaitlistError("Only waiting entries can be updated")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(entry, field, value)
    db.flush()
    return entry


def promote_from_waitlist(
    db: Session,
    hotel_id: int,
    entry_id: int,
    *,
    room_id: int | None = None,
    notes: str | None = None,
):
    entry = _get_waitlist_entry(db, hotel_id, entry_id)
    if entry.status != WaitlistStatusEnum.WAITING:
        raise WaitlistError("Only waiting entries can be promoted")

    payload = ReservationCreate(
        guest_id=entry.guest_id,
        category_id=entry.category_id,
        room_id=room_id,
        check_in_date=entry.check_in_date,
        check_out_date=entry.check_out_date,
        num_adults=entry.num_adults,
        num_children=entry.num_children,
        notes=notes or entry.notes,
    )
    try:
        reservation = create_reservation(db, payload, hotel_id=hotel_id)
    except ReservationError as exc:
        raise WaitlistError(str(exc)) from exc

    entry.status = WaitlistStatusEnum.PROMOTED
    entry.promoted_reservation_id = reservation.id
    entry.promoted_at = datetime.now(timezone.utc)
    db.flush()
    return entry, reservation


def cancel_waitlist_entry(db: Session, hotel_id: int, entry_id: int) -> WaitlistEntry:
    entry = _get_waitlist_entry(db, hotel_id, entry_id)
    if entry.status == WaitlistStatusEnum.PROMOTED:
        raise WaitlistError("Promoted waitlist entries cannot be cancelled")
    entry.status = WaitlistStatusEnum.CANCELLED
    db.flush()
    return entry


def expire_waitlist_entry(db: Session, hotel_id: int, entry_id: int) -> WaitlistEntry:
    entry = _get_waitlist_entry(db, hotel_id, entry_id)
    if entry.status == WaitlistStatusEnum.PROMOTED:
        raise WaitlistError("Promoted waitlist entries cannot be expired")
    entry.status = WaitlistStatusEnum.EXPIRED
    entry.expired_at = datetime.now(timezone.utc)
    db.flush()
    return entry


def request_payment_link_for_waitlist(*_args, **_kwargs):
    raise WaitlistError("Waitlist entries cannot request payment links until promoted to a reservation")
