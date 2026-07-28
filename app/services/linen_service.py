"""
Hotel-scoped linen (ropa blanca) inventory service.

Mirrors app/services/stock_service.py's movement/balance primitives against
the physically separate linen_items/linen_locations/linen_movements tables
(see app/models/linen.py) -- used exclusively by the outsourced-laundry
domain (app/services/laundry_vendor_service.py). Kept as its own module
rather than a shared generic layer over stock_service.py: the owner's
explicit ask was two separate tables and two separate datasets, not a
different abstraction over one shared table.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import case, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.audit_log import AuditActionEnum
from app.models.linen import LinenItem, LinenLocation, LinenMovement
from app.services import audit_log_service


class LinenError(ValueError):
    """Raised when a linen inventory operation is invalid."""


# Same movement vocabulary as stock_service.py: "adjustment" raises the
# balance (physical count found more), "adjustment_out" lowers it (found
# less / damaged in wash).
VALID_MOVEMENT_TYPES = {"in", "out", "adjustment", "adjustment_out"}
_OUTBOUND_MOVEMENT_TYPES = {"out", "adjustment_out"}


def list_linen_items(db: Session, *, hotel_id: int) -> list[LinenItem]:
    return (
        db.query(LinenItem)
        .filter(LinenItem.hotel_id == hotel_id, LinenItem.deleted_at.is_(None))
        .order_by(LinenItem.id.asc())
        .all()
    )


def create_linen_item(
    db: Session,
    *,
    hotel_id: int,
    name: str,
    unit: str,
    min_quantity: Decimal | None = None,
    active: bool = True,
) -> LinenItem:
    item = LinenItem(hotel_id=hotel_id, name=name, unit=unit, min_quantity=min_quantity, active=active)
    try:
        # SAVEPOINT so a duplicate-name failure only undoes this insert, not
        # whatever else the caller's session/transaction is holding -- same
        # pattern as stock_service.create_stock_item.
        with db.begin_nested():
            db.add(item)
            db.flush()
    except IntegrityError as exc:
        raise LinenError(f'Ya existe un tipo de ropa blanca llamado "{name}" en este hotel') from exc
    return item


def delete_linen_item(
    db: Session,
    *,
    hotel_id: int,
    item_id: int,
    deleted_by_user_id: int | None = None,
) -> None:
    item = get_linen_item(db, hotel_id=hotel_id, item_id=item_id)
    before = audit_log_service.model_snapshot(item)
    item.deleted_at = datetime.now(timezone.utc)
    item.deleted_by_user_id = deleted_by_user_id
    db.flush()
    audit_log_service.safe_create_audit_log(
        db,
        hotel_id=hotel_id,
        table_name="linen_items",
        record_id=item.id,
        action=AuditActionEnum.DELETE,
        actor_user_id=deleted_by_user_id,
        payload_before=before,
        payload_after=audit_log_service.model_snapshot(item),
    )


def get_linen_item(db: Session, *, hotel_id: int, item_id: int) -> LinenItem:
    item = (
        db.query(LinenItem)
        .filter(LinenItem.id == item_id, LinenItem.hotel_id == hotel_id, LinenItem.deleted_at.is_(None))
        .first()
    )
    if not item:
        raise LinenError("Linen item not found")
    return item


def list_locations(db: Session, *, hotel_id: int) -> list[LinenLocation]:
    return (
        db.query(LinenLocation)
        .filter(LinenLocation.hotel_id == hotel_id, LinenLocation.deleted_at.is_(None))
        .order_by(LinenLocation.id.asc())
        .all()
    )


def create_location(db: Session, *, hotel_id: int, name: str) -> LinenLocation:
    location = LinenLocation(hotel_id=hotel_id, name=name)
    try:
        with db.begin_nested():
            db.add(location)
            db.flush()
    except IntegrityError as exc:
        raise LinenError(f'Ya existe una ubicacion de ropa blanca llamada "{name}" en este hotel') from exc
    return location


def get_location(db: Session, *, hotel_id: int, location_id: int) -> LinenLocation:
    location = (
        db.query(LinenLocation)
        .filter(
            LinenLocation.id == location_id,
            LinenLocation.hotel_id == hotel_id,
            LinenLocation.deleted_at.is_(None),
        )
        .first()
    )
    if not location:
        raise LinenError("Linen location not found")
    return location


def register_movement(
    db: Session,
    *,
    hotel_id: int,
    item_id: int,
    location_id: int | None,
    movement_type: str,
    quantity: Decimal,
    reason: str | None = None,
    reservation_id: int | None = None,
    created_by_user_id: int | None = None,
) -> LinenMovement:
    if movement_type not in VALID_MOVEMENT_TYPES:
        raise LinenError("Invalid linen movement type")
    if quantity <= 0:
        raise LinenError("Linen movement quantity must be positive")
    item = (
        db.query(LinenItem)
        .filter(LinenItem.id == item_id, LinenItem.hotel_id == hotel_id, LinenItem.deleted_at.is_(None))
        .with_for_update()
        .one_or_none()
    )
    if item is None:
        raise LinenError("Linen item not found")
    if movement_type in _OUTBOUND_MOVEMENT_TYPES and quantity > current_stock(
        db, hotel_id=hotel_id, item_id=item.id
    ):
        raise LinenError("Linen movement would make stock negative")
    if location_id is not None:
        get_location(db, hotel_id=hotel_id, location_id=location_id)
    movement = LinenMovement(
        hotel_id=hotel_id,
        item_id=item.id,
        location_id=location_id,
        movement_type=movement_type,
        quantity=quantity,
        reason=reason,
        reservation_id=reservation_id,
        created_by_user_id=created_by_user_id,
    )
    db.add(movement)
    db.flush()
    return movement


def current_stock(
    db: Session, *, hotel_id: int, item_id: int, location_id: int | None = None
) -> Decimal:
    """Balance of one linen item for a hotel, optionally narrowed to one
    location -- e.g. "clean linen at the hotel" vs "linen currently at the
    laundry vendor" are the same item with different location_id filters.
    """
    get_linen_item(db, hotel_id=hotel_id, item_id=item_id)
    signed_quantity = case(
        (LinenMovement.movement_type.in_(_OUTBOUND_MOVEMENT_TYPES), -LinenMovement.quantity),
        else_=LinenMovement.quantity,
    )
    query = db.query(func.coalesce(func.sum(signed_quantity), 0)).filter(
        LinenMovement.hotel_id == hotel_id, LinenMovement.item_id == item_id
    )
    if location_id is not None:
        query = query.filter(LinenMovement.location_id == location_id)
    total = query.scalar()
    return Decimal(total).quantize(Decimal("0.01"))
