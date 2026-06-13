"""
Hotel-scoped stock and inventory movement service.
"""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.models.stock import StockItem, StockLocation, StockMovement


class StockError(ValueError):
    """Raised when a stock operation is invalid."""


VALID_MOVEMENT_TYPES = {"in", "out", "adjustment"}


def list_stock_items(db: Session, *, hotel_id: int) -> list[StockItem]:
    return db.query(StockItem).filter(StockItem.hotel_id == hotel_id).order_by(StockItem.id.asc()).all()


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


def delete_stock_item(db: Session, *, hotel_id: int, item_id: int) -> None:
    item = _get_item(db, hotel_id=hotel_id, item_id=item_id)
    db.delete(item)
    db.flush()


def list_locations(db: Session, *, hotel_id: int) -> list[StockLocation]:
    return db.query(StockLocation).filter(StockLocation.hotel_id == hotel_id).order_by(StockLocation.id.asc()).all()


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


def delete_location(db: Session, *, hotel_id: int, location_id: int) -> None:
    location = _get_location(db, hotel_id=hotel_id, location_id=location_id)
    db.delete(location)
    db.flush()


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
    item = _get_item(db, hotel_id=hotel_id, item_id=item_id)
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


def current_stock(db: Session, *, hotel_id: int, item_id: int) -> Decimal:
    _get_item(db, hotel_id=hotel_id, item_id=item_id)
    signed_quantity = case(
        (StockMovement.movement_type == "out", -StockMovement.quantity),
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
    item = db.query(StockItem).filter(StockItem.id == item_id, StockItem.hotel_id == hotel_id).first()
    if not item:
        raise StockError("Stock item not found")
    return item


def _get_location(db: Session, *, hotel_id: int, location_id: int) -> StockLocation:
    location = (
        db.query(StockLocation)
        .filter(StockLocation.id == location_id, StockLocation.hotel_id == hotel_id)
        .first()
    )
    if not location:
        raise StockError("Stock location not found")
    return location
