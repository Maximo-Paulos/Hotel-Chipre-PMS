"""
Outsourced laundry vendors: vendor/price catalog + remito transfers.

A remito is not a new kind of business event -- it is a StockMovement
transfer between two StockLocations (the hotel's "clean linen" location,
chosen explicitly per remito by the caller, and the vendor's own location).
See app/services/stock_service.py for the underlying movement/balance
primitives this builds on.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.hotel_config import HotelConfiguration
from app.models.laundry_vendor import LaundryRemito, LaundryRemitoLine, LaundryVendor, LaundryVendorPrice
from app.services import stock_service

DIRECTIONS = {"outbound", "inbound"}


class LaundryVendorError(ValueError):
    """Raised when a laundry vendor/remito operation is invalid."""


def create_vendor(
    db: Session,
    *,
    hotel_id: int,
    name: str,
    contact_phone: str | None = None,
    contact_email: str | None = None,
    active: bool = True,
) -> LaundryVendor:
    """Create a vendor and its dedicated StockLocation in one transaction."""

    location = stock_service.create_location(db, hotel_id=hotel_id, name=f"Lavadero - {name}")
    vendor = LaundryVendor(
        hotel_id=hotel_id,
        name=name,
        stock_location_id=location.id,
        contact_phone=contact_phone,
        contact_email=contact_email,
        active=active,
    )
    db.add(vendor)
    db.flush()
    return vendor


def update_vendor(db: Session, *, hotel_id: int, vendor_id: int, **changes) -> LaundryVendor:
    vendor = _get_vendor(db, hotel_id=hotel_id, vendor_id=vendor_id)
    for field in ("name", "contact_phone", "contact_email", "active"):
        if field in changes:
            setattr(vendor, field, changes[field])
    db.flush()
    return vendor


def list_vendors(db: Session, *, hotel_id: int) -> list[LaundryVendor]:
    return (
        db.query(LaundryVendor)
        .filter(LaundryVendor.hotel_id == hotel_id, LaundryVendor.deleted_at.is_(None))
        .order_by(LaundryVendor.id.asc())
        .all()
    )


def get_vendor(db: Session, *, hotel_id: int, vendor_id: int) -> LaundryVendor:
    return _get_vendor(db, hotel_id=hotel_id, vendor_id=vendor_id)


def set_vendor_price(
    db: Session,
    *,
    hotel_id: int,
    vendor_id: int,
    stock_item_id: int,
    unit_price: Decimal,
    currency_code: str | None = None,
) -> LaundryVendorPrice:
    """Upsert the single current price for a (vendor, item) pair."""

    if unit_price < 0:
        raise LaundryVendorError("Unit price cannot be negative")
    _get_vendor(db, hotel_id=hotel_id, vendor_id=vendor_id)
    stock_service.get_stock_item(db, hotel_id=hotel_id, item_id=stock_item_id)

    price = (
        db.query(LaundryVendorPrice)
        .filter(LaundryVendorPrice.vendor_id == vendor_id, LaundryVendorPrice.stock_item_id == stock_item_id)
        .one_or_none()
    )
    if currency_code is None:
        currency_code = price.currency_code if price is not None else _default_currency(db, hotel_id=hotel_id)

    if price is None:
        price = LaundryVendorPrice(
            hotel_id=hotel_id,
            vendor_id=vendor_id,
            stock_item_id=stock_item_id,
            unit_price=unit_price,
            currency_code=currency_code,
        )
        db.add(price)
    else:
        price.unit_price = unit_price
        price.currency_code = currency_code
        price.updated_at = datetime.now(timezone.utc)
    db.flush()
    return price


def list_vendor_prices(db: Session, *, hotel_id: int, vendor_id: int) -> list[LaundryVendorPrice]:
    _get_vendor(db, hotel_id=hotel_id, vendor_id=vendor_id)
    return (
        db.query(LaundryVendorPrice)
        .filter(LaundryVendorPrice.hotel_id == hotel_id, LaundryVendorPrice.vendor_id == vendor_id)
        .order_by(LaundryVendorPrice.id.asc())
        .all()
    )


def create_remito(
    db: Session,
    *,
    hotel_id: int,
    vendor_id: int,
    direction: str,
    remito_number: str,
    remito_date: datetime,
    house_location_id: int,
    lines: list[dict],
    notes: str | None = None,
    actor_user_id: int | None = None,
) -> LaundryRemito:
    """Record a remito as a pair of StockMovements per line.

    outbound: house_location -> vendor_location (dirty linen leaves the hotel)
    inbound:  vendor_location -> house_location (clean linen comes back)

    The hotel-wide total per item never changes -- this is a transfer, not a
    consumption event. Any failure (bad direction, no lines, insufficient
    stock at the source location) rolls back the whole remito: no partial
    remito or dangling movements are left behind.
    """

    if direction not in DIRECTIONS:
        raise LaundryVendorError("direction must be 'outbound' or 'inbound'")
    if not lines:
        raise LaundryVendorError("A remito needs at least one line")

    vendor = _get_vendor(db, hotel_id=hotel_id, vendor_id=vendor_id)
    stock_service.get_location(db, hotel_id=hotel_id, location_id=house_location_id)

    if direction == "outbound":
        source_location_id, dest_location_id = house_location_id, vendor.stock_location_id
    else:
        source_location_id, dest_location_id = vendor.stock_location_id, house_location_id

    try:
        remito = LaundryRemito(
            hotel_id=hotel_id,
            vendor_id=vendor_id,
            direction=direction,
            remito_number=remito_number,
            remito_date=remito_date,
            notes=notes,
            created_by_user_id=actor_user_id,
        )
        db.add(remito)
        db.flush()

        for line in lines:
            stock_item_id = line["stock_item_id"]
            quantity = line["quantity"]
            if quantity <= 0:
                raise LaundryVendorError("Remito line quantity must be positive")

            item = stock_service.get_stock_item(db, hotel_id=hotel_id, item_id=stock_item_id)
            available = stock_service.current_stock(
                db, hotel_id=hotel_id, item_id=stock_item_id, location_id=source_location_id
            )
            if quantity > available:
                raise LaundryVendorError(
                    f"Not enough '{item.name}' at the source location: have {available}, need {quantity}"
                )

            movement_reason = f"Laundry remito {remito_number} ({direction})"
            stock_service.register_movement(
                db,
                hotel_id=hotel_id,
                item_id=stock_item_id,
                location_id=source_location_id,
                movement_type="out",
                quantity=quantity,
                reason=movement_reason,
                created_by_user_id=actor_user_id,
            )
            stock_service.register_movement(
                db,
                hotel_id=hotel_id,
                item_id=stock_item_id,
                location_id=dest_location_id,
                movement_type="in",
                quantity=quantity,
                reason=movement_reason,
                created_by_user_id=actor_user_id,
            )

            price = (
                db.query(LaundryVendorPrice)
                .filter(
                    LaundryVendorPrice.vendor_id == vendor_id,
                    LaundryVendorPrice.stock_item_id == stock_item_id,
                )
                .one_or_none()
            )
            db.add(
                LaundryRemitoLine(
                    hotel_id=hotel_id,
                    remito_id=remito.id,
                    stock_item_id=stock_item_id,
                    quantity=quantity,
                    unit_price_snapshot=price.unit_price if price is not None else None,
                )
            )
            db.flush()
    except Exception:
        db.rollback()
        raise

    return remito


def list_remitos(
    db: Session,
    *,
    hotel_id: int,
    vendor_id: int | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> list[LaundryRemito]:
    query = db.query(LaundryRemito).filter(LaundryRemito.hotel_id == hotel_id)
    if vendor_id is not None:
        query = query.filter(LaundryRemito.vendor_id == vendor_id)
    if date_from is not None:
        query = query.filter(LaundryRemito.remito_date >= date_from)
    if date_to is not None:
        query = query.filter(LaundryRemito.remito_date <= date_to)
    return query.order_by(LaundryRemito.remito_date.desc(), LaundryRemito.id.desc()).all()


def vendor_balance(db: Session, *, hotel_id: int, vendor_id: int) -> list[dict]:
    """What is physically at the vendor's laundry right now, per item."""

    vendor = _get_vendor(db, hotel_id=hotel_id, vendor_id=vendor_id)
    item_ids = (
        db.query(LaundryRemitoLine.stock_item_id)
        .join(LaundryRemito, LaundryRemito.id == LaundryRemitoLine.remito_id)
        .filter(LaundryRemito.hotel_id == hotel_id, LaundryRemito.vendor_id == vendor_id)
        .distinct()
        .all()
    )
    balances = []
    for (item_id,) in item_ids:
        item = stock_service.get_stock_item(db, hotel_id=hotel_id, item_id=item_id)
        quantity = stock_service.current_stock(
            db, hotel_id=hotel_id, item_id=item_id, location_id=vendor.stock_location_id
        )
        balances.append({"stock_item_id": item.id, "stock_item_name": item.name, "quantity": quantity})
    return balances


def vendor_spend(
    db: Session,
    *,
    hotel_id: int,
    vendor_id: int,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> dict:
    """Total charged by the vendor in a period.

    Assumption (see plan D1/D3, flagged there as adjustable with real
    evidence): the vendor bills for what was *sent* (outbound), not what
    comes back. Swapping to inbound is a one-line filter change if that
    assumption turns out wrong.
    """

    _get_vendor(db, hotel_id=hotel_id, vendor_id=vendor_id)
    query = (
        db.query(
            LaundryRemitoLine.stock_item_id,
            func.coalesce(func.sum(LaundryRemitoLine.quantity * LaundryRemitoLine.unit_price_snapshot), 0),
            func.coalesce(func.sum(LaundryRemitoLine.quantity), 0),
        )
        .join(LaundryRemito, LaundryRemito.id == LaundryRemitoLine.remito_id)
        .filter(
            LaundryRemito.hotel_id == hotel_id,
            LaundryRemito.vendor_id == vendor_id,
            LaundryRemito.direction == "outbound",
        )
    )
    if date_from is not None:
        query = query.filter(LaundryRemito.remito_date >= date_from)
    if date_to is not None:
        query = query.filter(LaundryRemito.remito_date <= date_to)

    by_item = []
    total = Decimal("0.00")
    for stock_item_id, subtotal, quantity in query.group_by(LaundryRemitoLine.stock_item_id).all():
        item = stock_service.get_stock_item(db, hotel_id=hotel_id, item_id=stock_item_id)
        subtotal = Decimal(subtotal).quantize(Decimal("0.01"))
        total += subtotal
        by_item.append(
            {
                "stock_item_id": item.id,
                "stock_item_name": item.name,
                "quantity": Decimal(quantity).quantize(Decimal("0.01")),
                "subtotal": subtotal,
            }
        )
    return {"total": total, "by_item": by_item}


def _get_vendor(db: Session, *, hotel_id: int, vendor_id: int) -> LaundryVendor:
    vendor = (
        db.query(LaundryVendor)
        .filter(LaundryVendor.id == vendor_id, LaundryVendor.hotel_id == hotel_id, LaundryVendor.deleted_at.is_(None))
        .one_or_none()
    )
    if vendor is None:
        raise LaundryVendorError("Laundry vendor not found")
    return vendor


def _default_currency(db: Session, *, hotel_id: int) -> str:
    hotel = db.query(HotelConfiguration).filter(HotelConfiguration.id == hotel_id).one_or_none()
    return hotel.default_currency if hotel is not None and hotel.default_currency else "ARS"
