"""Hotel-scoped waitlist lifecycle service."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.guest import Guest
from app.models.reservation import Reservation
from app.models.room import RoomCategory
from app.models.waitlist import WaitlistEntry, WaitlistStatusEnum
from app.schemas.reservation import ReservationCreate
from app.schemas.waitlist import WaitlistEntryCreate, WaitlistEntryUpdate
from app.services.allocation_engine import (
    ReservationSlot,
    build_slots_from_db,
    run_allocation,
)
from app.services.allocation_policy_service import get_active_policy_settings
from app.services.reservation_service import (
    ReservationError,
    create_reservation,
    find_available_rooms,
)
from app.services.row_locks import lock_query


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


def _lock_waitlist_entry(db: Session, hotel_id: int, entry_id: int) -> WaitlistEntry | None:
    query = (
        db.query(WaitlistEntry)
        .filter(WaitlistEntry.id == entry_id, WaitlistEntry.hotel_id == hotel_id)
        .populate_existing()
    )
    return lock_query(query, WaitlistEntry).one_or_none()


def _waitlist_entry_fingerprint(entry: WaitlistEntry) -> str:
    """Fingerprint the details that determine a reviewed promotion suggestion."""
    snapshot = {
        "hotel_id": entry.hotel_id,
        "entry_id": entry.id,
        "guest_id": entry.guest_id,
        "category_id": entry.category_id,
        "check_in_date": entry.check_in_date.isoformat(),
        "check_out_date": entry.check_out_date.isoformat(),
        "num_adults": entry.num_adults,
        "num_children": entry.num_children,
        "priority": entry.priority,
        "status": entry.status.value,
    }
    canonical = json.dumps(snapshot, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


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
    entry = _lock_waitlist_entry(db, hotel_id, entry_id)
    if entry is None:
        raise WaitlistError("Waitlist entry not found for this hotel")
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
    room_id: int,
    expected_entry_fingerprint: str,
    notes: str | None = None,
):
    entry = _lock_waitlist_entry(db, hotel_id, entry_id)
    if entry is None:
        raise WaitlistError("Waitlist entry not found for this hotel")
    if entry.status == WaitlistStatusEnum.PROMOTED and entry.promoted_reservation_id is not None:
        reservation = (
            db.query(Reservation)
            .filter(
                Reservation.id == entry.promoted_reservation_id,
                Reservation.hotel_id == hotel_id,
                Reservation.deleted_at.is_(None),
            )
            .one_or_none()
        )
        if reservation is not None:
            return entry, reservation
    if entry.status != WaitlistStatusEnum.WAITING:
        raise WaitlistError("Only waiting entries can be promoted")

    if _waitlist_entry_fingerprint(entry) != expected_entry_fingerprint:
        raise WaitlistError("Waitlist entry changed; request a new suggestion")

    current_suggestion = suggest_waitlist_promotion(db, hotel_id=hotel_id, entry_id=entry.id)
    if current_suggestion is None:
        raise WaitlistError("No compatible room is currently available; request a new suggestion")

    chosen_room_id = room_id

    available_rooms = find_available_rooms(
        db,
        entry.category_id,
        entry.check_in_date,
        entry.check_out_date,
        hotel_id=hotel_id,
        lock_for_update=True,
    )
    if chosen_room_id not in {room.id for room in available_rooms}:
        raise WaitlistError("The selected room is no longer available; request a new suggestion")

    payload = ReservationCreate(
        guest_id=entry.guest_id,
        category_id=entry.category_id,
        room_id=chosen_room_id,
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

    # Sync the denormalized waitlist flags (v72 §9): a promoted entry yields a
    # real, room-assigned reservation, so it must not be flagged as wait-listed.
    if reservation.room_id is not None:
        reservation.is_wait_listed = False
        reservation.wait_list_reason = None

    entry.status = WaitlistStatusEnum.PROMOTED
    entry.promoted_reservation_id = reservation.id
    entry.promoted_at = datetime.now(timezone.utc)
    db.flush()
    return entry, reservation


def suggest_waitlist_promotions(
    db: Session,
    *,
    hotel_id: int,
    limit: int = 50,
) -> list[dict]:
    """Return motor-backed room suggestions while leaving the queue unchanged.

    The receptionist chooses which waiting guest to promote. Existing assigned
    reservations are fixed in each candidate solve, so a suggestion never hides
    or applies a move to an already-confirmed guest.
    """
    entries = list_waitlist_entries(db, hotel_id, status_filter=WaitlistStatusEnum.WAITING)[:limit]
    suggestions: list[dict] = []
    for entry in entries:
        suggestion = suggest_waitlist_promotion(db, hotel_id=hotel_id, entry_id=entry.id)
        if suggestion is not None:
            suggestions.append(suggestion)
    return suggestions


def suggest_waitlist_promotion(
    db: Session,
    *,
    hotel_id: int,
    entry_id: int,
) -> dict | None:
    """Run the deterministic room solver for one waiting entry without writes."""
    entry = _get_waitlist_entry(db, hotel_id, entry_id)
    if entry.status != WaitlistStatusEnum.WAITING:
        raise WaitlistError("Only waiting entries can receive a promotion suggestion")
    category = (
        db.query(RoomCategory)
        .filter(RoomCategory.id == entry.category_id, RoomCategory.hotel_id == hotel_id)
        .one_or_none()
    )
    if category is None:
        raise WaitlistError("Waitlist category not found for this hotel")
    if entry.num_adults + entry.num_children > category.max_occupancy:
        return None

    policy = get_active_policy_settings(db, hotel_id)
    reservation_slots, room_slots = build_slots_from_db(
        db,
        hotel_id=hotel_id,
        start_date=entry.check_in_date,
        end_date=entry.check_out_date,
        policy_constraints=policy.constraints,
    )
    # Freeze every current assignment while evaluating this waitlisted guest.
    # Unassigned active reservations remain part of the solve and compete for
    # real capacity, but are not mutated by the suggestion endpoint.
    for slot in reservation_slots:
        if slot.current_room_id is not None:
            slot.is_locked = True
    synthetic_reservation_id = -entry.id
    reservation_slots.append(
        ReservationSlot(
            reservation_id=synthetic_reservation_id,
            category_id=entry.category_id,
            check_in=entry.check_in_date,
            check_out=entry.check_out_date,
            current_room_id=None,
            is_locked=False,
            guest_id=entry.guest_id,
            num_guests=max(1, entry.num_adults + entry.num_children),
        )
    )
    # A waitlist entry has no saved quote or channel commission snapshot yet.
    # Use the motor for feasibility and room fit only; applying the hotel's
    # revenue objective here would invent a zero price and could suppress a
    # valid reception suggestion.
    feasibility_constraints = dict(policy.constraints)
    feasibility_constraints["optimization_objective"] = "occupied_nights"
    result = run_allocation(
        reservation_slots,
        room_slots,
        optimization_horizon=(entry.check_in_date, entry.check_out_date),
        policy_constraints=feasibility_constraints,
        policy_weights=policy.weights,
    )
    room_id = result.assignments.get(synthetic_reservation_id)
    if not result.success or room_id is None:
        return None
    room = next((item for item in room_slots if item.room_id == room_id), None)
    if room is None:
        return None
    return {
        "entry_id": entry.id,
        "expected_entry_fingerprint": _waitlist_entry_fingerprint(entry),
        "guest_id": entry.guest_id,
        "guest_name": f"{entry.guest.first_name} {entry.guest.last_name}".strip(),
        "category_id": entry.category_id,
        "check_in_date": entry.check_in_date,
        "check_out_date": entry.check_out_date,
        "priority": entry.priority,
        "suggested_room_id": room_id,
        "suggested_room_number": room.room_number,
        "reason": "Feasible room suggested by allocation motor; reception confirms promotion",
        "allocation_basis": "feasibility_only_no_price_snapshot",
    }


def cancel_waitlist_entry(db: Session, hotel_id: int, entry_id: int) -> WaitlistEntry:
    entry = _lock_waitlist_entry(db, hotel_id, entry_id)
    if entry is None:
        raise WaitlistError("Waitlist entry not found for this hotel")
    if entry.status == WaitlistStatusEnum.PROMOTED:
        raise WaitlistError("Promoted waitlist entries cannot be cancelled")
    entry.status = WaitlistStatusEnum.CANCELLED
    db.flush()
    return entry


def expire_waitlist_entry(db: Session, hotel_id: int, entry_id: int) -> WaitlistEntry:
    entry = _lock_waitlist_entry(db, hotel_id, entry_id)
    if entry is None:
        raise WaitlistError("Waitlist entry not found for this hotel")
    if entry.status == WaitlistStatusEnum.PROMOTED:
        raise WaitlistError("Promoted waitlist entries cannot be expired")
    entry.status = WaitlistStatusEnum.EXPIRED
    entry.expired_at = datetime.now(timezone.utc)
    db.flush()
    return entry


def request_payment_link_for_waitlist(*_args, **_kwargs):
    raise WaitlistError("Waitlist entries cannot request payment links until promoted to a reservation")
