"""
Hotel-scoped laundry service.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session, selectinload

from app.models.laundry import LaundryBatch, LaundryItem


class LaundryError(ValueError):
    """Raised when a laundry operation is invalid."""


VALID_STATUSES = {"collected", "sent", "received", "closed"}
VALID_TRANSITIONS = {
    "collected": {"sent"},
    "sent": {"received"},
    "received": {"closed"},
    "closed": set(),
}


def create_batch(
    db: Session,
    *,
    hotel_id: int,
    notes: str | None = None,
    created_by_user_id: int | None = None,
) -> LaundryBatch:
    batch = LaundryBatch(
        hotel_id=hotel_id,
        batch_code=_next_batch_code(db, hotel_id),
        notes=notes,
        created_by_user_id=created_by_user_id,
    )
    db.add(batch)
    db.flush()
    return batch


def add_item(
    db: Session,
    *,
    hotel_id: int,
    batch_id: int,
    item_type: str,
    quantity: int,
    room_id: int | None = None,
) -> LaundryItem:
    if quantity <= 0:
        raise LaundryError("Laundry item quantity must be positive")
    batch = _get_batch(db, hotel_id=hotel_id, batch_id=batch_id)
    item = LaundryItem(
        hotel_id=hotel_id,
        batch_id=batch.id,
        item_type=item_type,
        quantity=quantity,
        room_id=room_id,
    )
    db.add(item)
    db.flush()
    return item


def transition_status(db: Session, *, hotel_id: int, batch_id: int, new_status: str) -> LaundryBatch:
    if new_status not in VALID_STATUSES:
        raise LaundryError("Invalid laundry status")
    batch = _get_batch(db, hotel_id=hotel_id, batch_id=batch_id)
    current_status = batch.status or "collected"
    if new_status not in VALID_TRANSITIONS[current_status]:
        raise LaundryError(f"Invalid laundry status transition: {current_status} -> {new_status}")

    batch.status = new_status
    now = datetime.now(timezone.utc)
    if new_status == "sent":
        batch.sent_at = now
    elif new_status == "received":
        batch.received_at = now
    db.flush()
    return batch


def list_batches(db: Session, *, hotel_id: int, filters: dict | None = None) -> list[LaundryBatch]:
    filters = filters or {}
    query = (
        db.query(LaundryBatch)
        .options(selectinload(LaundryBatch.items))
        .filter(LaundryBatch.hotel_id == hotel_id)
    )
    if filters.get("status"):
        query = query.filter(LaundryBatch.status == filters["status"])
    if filters.get("batch_code"):
        query = query.filter(LaundryBatch.batch_code == filters["batch_code"])
    return query.order_by(LaundryBatch.id.asc()).all()


def get_batch(db: Session, *, hotel_id: int, batch_id: int) -> LaundryBatch:
    return _get_batch(db, hotel_id=hotel_id, batch_id=batch_id)


def _get_batch(db: Session, *, hotel_id: int, batch_id: int) -> LaundryBatch:
    batch = (
        db.query(LaundryBatch)
        .options(selectinload(LaundryBatch.items))
        .filter(LaundryBatch.id == batch_id, LaundryBatch.hotel_id == hotel_id)
        .first()
    )
    if not batch:
        raise LaundryError("Laundry batch not found")
    return batch


def _next_batch_code(db: Session, hotel_id: int) -> str:
    prefix = datetime.now(timezone.utc).strftime("L%Y%m%d")
    existing = (
        db.query(LaundryBatch.batch_code)
        .filter(LaundryBatch.hotel_id == hotel_id, LaundryBatch.batch_code.like(f"{prefix}-%"))
        .order_by(LaundryBatch.batch_code.desc())
        .first()
    )
    next_number = 1
    if existing:
        try:
            next_number = int(existing[0].rsplit("-", 1)[1]) + 1
        except (IndexError, ValueError):
            next_number = 1
    return f"{prefix}-{next_number:04d}"
