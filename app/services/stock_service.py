"""
Hotel-scoped stock and inventory movement service.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.models.audit_log import AuditActionEnum
from app.models.stock import StockItem, StockLocation, StockMovement
from app.services import audit_log_service


class StockError(ValueError):
    """Raised when a stock operation is invalid."""


# "adjustment" raises stock (physical count found more than expected);
# "adjustment_out" lowers it (found less / breakage). Both require the
# stock:adjust permission, unlike plain "in"/"out" (see app/api/stock.py).
VALID_MOVEMENT_TYPES = {"in", "out", "adjustment", "adjustment_out"}
_OUTBOUND_MOVEMENT_TYPES = {"out", "adjustment_out"}


def list_stock_items(db: Session, *, hotel_id: int) -> list[StockItem]:
    return (
        db.query(StockItem)
        .filter(StockItem.hotel_id == hotel_id, StockItem.deleted_at.is_(None))
        .order_by(StockItem.id.asc())
        .all()
    )


def create_stock_item(
    db: Session,
    *,
    hotel_id: int,
    name: str,
    sku: str | None = None,
    unit: str,
    min_quantity: Decimal | None = None,
    active: bool = True,
) -> StockItem:
    item = StockItem(
        hotel_id=hotel_id,
        name=name,
        sku=sku,
        unit=unit,
        min_quantity=min_quantity,
        active=active,
    )
    db.add(item)
    db.flush()
    return item


def update_stock_item(db: Session, *, hotel_id: int, item_id: int, **changes) -> StockItem:
    item = _get_item(db, hotel_id=hotel_id, item_id=item_id)
    for field in ("name", "sku", "unit", "min_quantity", "active"):
        if field in changes:
            setattr(item, field, changes[field])
    db.flush()
    return item


def delete_stock_item(
    db: Session,
    *,
    hotel_id: int,
    item_id: int,
    deleted_by_user_id: int | None = None,
) -> None:
    item = _get_item(db, hotel_id=hotel_id, item_id=item_id)
    before = audit_log_service.model_snapshot(item)
    item.deleted_at = datetime.now(timezone.utc)
    item.deleted_by_user_id = deleted_by_user_id
    db.flush()
    audit_log_service.safe_create_audit_log(
        db,
        hotel_id=hotel_id,
        table_name="stock_items",
        record_id=item.id,
        action=AuditActionEnum.DELETE,
        actor_user_id=deleted_by_user_id,
        payload_before=before,
        payload_after=audit_log_service.model_snapshot(item),
    )


def list_locations(db: Session, *, hotel_id: int) -> list[StockLocation]:
    return (
        db.query(StockLocation)
        .filter(StockLocation.hotel_id == hotel_id, StockLocation.deleted_at.is_(None))
        .order_by(StockLocation.id.asc())
        .all()
    )


def create_location(db: Session, *, hotel_id: int, name: str) -> StockLocation:
    location = StockLocation(hotel_id=hotel_id, name=name)
    db.add(location)
    db.flush()
    return location


def update_location(db: Session, *, hotel_id: int, location_id: int, name: str) -> StockLocation:
    location = _get_location(db, hotel_id=hotel_id, location_id=location_id)
    location.name = name
    db.flush()
    return location


def delete_location(
    db: Session,
    *,
    hotel_id: int,
    location_id: int,
    deleted_by_user_id: int | None = None,
) -> None:
    location = _get_location(db, hotel_id=hotel_id, location_id=location_id)
    before = audit_log_service.model_snapshot(location)
    location.deleted_at = datetime.now(timezone.utc)
    location.deleted_by_user_id = deleted_by_user_id
    db.flush()
    audit_log_service.safe_create_audit_log(
        db,
        hotel_id=hotel_id,
        table_name="stock_locations",
        record_id=location.id,
        action=AuditActionEnum.DELETE,
        actor_user_id=deleted_by_user_id,
        payload_before=before,
        payload_after=audit_log_service.model_snapshot(location),
    )


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
) -> StockMovement:
    if movement_type not in VALID_MOVEMENT_TYPES:
        raise StockError("Invalid stock movement type")
    if quantity <= 0:
        raise StockError("Stock movement quantity must be positive")
    item = (
        db.query(StockItem)
        .filter(StockItem.id == item_id, StockItem.hotel_id == hotel_id, StockItem.deleted_at.is_(None))
        .with_for_update()
        .one_or_none()
    )
    if item is None:
        raise StockError("Stock item not found")
    if movement_type in _OUTBOUND_MOVEMENT_TYPES and quantity > current_stock(
        db, hotel_id=hotel_id, item_id=item.id
    ):
        raise StockError("Stock movement would make stock negative")
    if location_id is not None:
        _get_location(db, hotel_id=hotel_id, location_id=location_id)
    movement = StockMovement(
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


def list_stock_movements(
    db: Session,
    *,
    hotel_id: int,
    item_id: int | None = None,
    limit: int = 50,
) -> list[StockMovement]:
    """Return the newest auditable inventory movements for one hotel."""

    if limit < 1:
        raise StockError("Stock movement history limit must be positive")
    query = db.query(StockMovement).filter(StockMovement.hotel_id == hotel_id)
    if item_id is not None:
        query = query.filter(StockMovement.item_id == item_id)
    return query.order_by(StockMovement.created_at.desc(), StockMovement.id.desc()).limit(limit).all()


def current_stock(db: Session, *, hotel_id: int, item_id: int) -> Decimal:
    _get_item(db, hotel_id=hotel_id, item_id=item_id)
    signed_quantity = case(
        (StockMovement.movement_type.in_(_OUTBOUND_MOVEMENT_TYPES), -StockMovement.quantity),
        else_=StockMovement.quantity,
    )
    total = (
        db.query(func.coalesce(func.sum(signed_quantity), 0))
        .filter(StockMovement.hotel_id == hotel_id, StockMovement.item_id == item_id)
        .scalar()
    )
    return Decimal(total).quantize(Decimal("0.01"))


def low_stock_items(db: Session, *, hotel_id: int) -> list[StockItem]:
    items = (
        db.query(StockItem)
        .filter(
            StockItem.hotel_id == hotel_id,
            StockItem.deleted_at.is_(None),
            StockItem.active.is_(True),
            StockItem.min_quantity.isnot(None),
        )
        .order_by(StockItem.id.asc())
        .all()
    )
    return [item for item in items if current_stock(db, hotel_id=hotel_id, item_id=item.id) < item.min_quantity]


def get_stock_item(db: Session, *, hotel_id: int, item_id: int) -> StockItem:
    return _get_item(db, hotel_id=hotel_id, item_id=item_id)


def get_location(db: Session, *, hotel_id: int, location_id: int) -> StockLocation:
    return _get_location(db, hotel_id=hotel_id, location_id=location_id)


def _get_item(db: Session, *, hotel_id: int, item_id: int) -> StockItem:
    item = (
        db.query(StockItem)
        .filter(StockItem.id == item_id, StockItem.hotel_id == hotel_id, StockItem.deleted_at.is_(None))
        .first()
    )
    if not item:
        raise StockError("Stock item not found")
    return item


def _get_location(db: Session, *, hotel_id: int, location_id: int) -> StockLocation:
    location = (
        db.query(StockLocation)
        .filter(
            StockLocation.id == location_id,
            StockLocation.hotel_id == hotel_id,
            StockLocation.deleted_at.is_(None),
        )
        .first()
    )
    if not location:
        raise StockError("Stock location not found")
    return location
