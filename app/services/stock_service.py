"""
Hotel-scoped stock and inventory movement service.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from sqlalchemy import case, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.audit_log import AuditActionEnum
from app.models.stock import StockItem, StockLocation, StockMovement
from app.services import audit_log_service


logger = logging.getLogger(__name__)


class StockError(ValueError):
    """Raised when a stock operation is invalid."""


# "adjustment" raises stock (physical count found more than expected);
# "adjustment_out" lowers it (found less / breakage). Both require the
# stock:adjust permission, unlike plain "in"/"out" (see app/api/stock.py).
VALID_MOVEMENT_TYPES = {"in", "out", "adjustment", "adjustment_out"}
_OUTBOUND_MOVEMENT_TYPES = {"out", "adjustment_out"}

# D5 (Via D): "week"/"month" is presentation metadata the frontend uses to
# label its range presets -- the previous-period math below is always "same
# number of days, immediately before" (plan D5 wording), which is correct
# regardless of calendar boundaries, so group_by never changes the query.
CONSUMPTION_GROUP_BY_VALUES = {"week", "month"}


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
    unit_cost: Decimal | None = None,
) -> StockItem:
    item = StockItem(
        hotel_id=hotel_id,
        name=name,
        sku=sku,
        unit=unit,
        min_quantity=min_quantity,
        active=active,
        unit_cost=unit_cost,
    )
    try:
        # SAVEPOINT so a duplicate-name failure only undoes this insert, not
        # whatever else the caller's session/transaction is holding.
        with db.begin_nested():
            db.add(item)
            db.flush()
    except IntegrityError as exc:
        raise StockError(f'Ya existe un item de stock llamado "{name}" en este hotel') from exc
    return item


def update_stock_item(db: Session, *, hotel_id: int, item_id: int, **changes) -> StockItem:
    item = _get_item(db, hotel_id=hotel_id, item_id=item_id)
    for field in ("name", "sku", "unit", "min_quantity", "active", "unit_cost"):
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


def _notify_if_low_stock(db: Session, *, hotel_id: int, item: StockItem) -> None:
    """Best-effort threshold check after a movement: fires at most once per
    hotel-local calendar day per item (dedupe_key), so a busy day of outbound
    movements while already below the threshold doesn't spam the outbox."""
    if item.min_quantity is None:
        return
    try:
        balance = current_stock(db, hotel_id=hotel_id, item_id=item.id)
        if balance >= item.min_quantity:
            return
        from app.models.notification import NotificationSeverityEnum
        from app.services.notification_service import enqueue_notifications_for_event
        from app.services.permission_service import ROLE_CODES

        severity = NotificationSeverityEnum.CRITICAL if balance <= 0 else NotificationSeverityEnum.WARNING
        event_type = "stock.out_of_stock" if balance <= 0 else "stock.low"
        today = datetime.now(timezone.utc).date().isoformat()
        enqueue_notifications_for_event(
            db,
            hotel_id=hotel_id,
            event_type=event_type,
            dedupe_key=f"{event_type}:{item.id}:{today}",
            title=f"Low stock: {item.name}" if balance > 0 else f"Out of stock: {item.name}",
            severity=severity,
            entity_type="stock_item",
            entity_id=item.id,
            payload={"item_id": item.id, "status": "low" if balance > 0 else "out"},
            recipient_roles=list(ROLE_CODES),
        )
    except Exception as exc:
        logger.error(
            "stock.low_stock_notify_failed",
            extra={"hotel_id": hotel_id, "item_id": item.id, "error_type": type(exc).__name__},
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
    idempotency_key: str | None = None,
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
    if idempotency_key:
        existing = (
            db.query(StockMovement)
            .filter(StockMovement.hotel_id == hotel_id, StockMovement.idempotency_key == idempotency_key)
            .one_or_none()
        )
        if existing is not None:
            return existing
    # Bug fix: an outbound movement scoped to one location must only be
    # checked against THAT location's balance, not the hotel-wide total
    # across every location -- otherwise "out" at location B could draw down
    # a balance that actually lives at location A (never validated against
    # location B at all). Movements with no location_id keep checking the
    # hotel-wide total, unchanged.
    if movement_type in _OUTBOUND_MOVEMENT_TYPES and quantity > current_stock(
        db, hotel_id=hotel_id, item_id=item.id, location_id=location_id
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
        idempotency_key=idempotency_key,
    )
    try:
        # SAVEPOINT: a retried request racing its own first attempt (both
        # already past the existing-row check above) collapses into the
        # unique (hotel_id, idempotency_key) index instead of inserting a
        # duplicate movement -- return the winner's row either way.
        with db.begin_nested():
            db.add(movement)
            db.flush()
    except IntegrityError:
        # Only the SAVEPOINT rolled back (see create_stock_item above) -- the
        # session is still usable. A concurrent retry of the same request won.
        existing = (
            db.query(StockMovement)
            .filter(StockMovement.hotel_id == hotel_id, StockMovement.idempotency_key == idempotency_key)
            .one()
        )
        return existing
    if movement_type in _OUTBOUND_MOVEMENT_TYPES:
        _notify_if_low_stock(db, hotel_id=hotel_id, item=item)
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


def current_stock(
    db: Session, *, hotel_id: int, item_id: int, location_id: int | None = None
) -> Decimal:
    """Balance of one item for a hotel, optionally narrowed to one location.

    Without ``location_id`` this is the hotel-wide total (unchanged behavior
    for every existing caller). With it, only movements recorded against that
    location are summed -- e.g. "clean linen at the hotel" vs "linen
    currently at the laundry vendor" are the same item with different
    location_id filters.
    """
    _get_item(db, hotel_id=hotel_id, item_id=item_id)
    signed_quantity = case(
        (StockMovement.movement_type.in_(_OUTBOUND_MOVEMENT_TYPES), -StockMovement.quantity),
        else_=StockMovement.quantity,
    )
    query = db.query(func.coalesce(func.sum(signed_quantity), 0)).filter(
        StockMovement.hotel_id == hotel_id, StockMovement.item_id == item_id
    )
    if location_id is not None:
        query = query.filter(StockMovement.location_id == location_id)
    total = query.scalar()
    return Decimal(total).quantize(Decimal("0.01"))


def stock_summary(db: Session, *, hotel_id: int, location_id: int | None = None) -> list[dict]:
    """Every active item's current balance in one query pair, instead of the
    N+1 pattern of calling current_stock() once per item (see StockPage.tsx's
    stockQueries useQueries loop -- this is its backend counterpart).
    """
    items = list_stock_items(db, hotel_id=hotel_id)
    if not items:
        return []
    signed_quantity = case(
        (StockMovement.movement_type.in_(_OUTBOUND_MOVEMENT_TYPES), -StockMovement.quantity),
        else_=StockMovement.quantity,
    )
    query = (
        db.query(StockMovement.item_id, func.coalesce(func.sum(signed_quantity), 0))
        .filter(StockMovement.hotel_id == hotel_id, StockMovement.item_id.in_([item.id for item in items]))
    )
    if location_id is not None:
        query = query.filter(StockMovement.location_id == location_id)
    totals = {item_id: Decimal(total).quantize(Decimal("0.01")) for item_id, total in query.group_by(StockMovement.item_id).all()}
    return [
        {"item": item, "current_quantity": totals.get(item.id, Decimal("0.00"))}
        for item in items
    ]


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


def consumption_report(
    db: Session,
    *,
    hotel_id: int,
    date_from: date,
    date_to: date,
    group_by: str,
) -> dict:
    """Stock consumed (``out``/``adjustment_out``) per item in [date_from,
    date_to], plus the same-length period immediately before it so the
    caller can show a variation % (D5 -- see plan Via D: detect anomalous
    consumption, e.g. usage doubling with flat occupancy).
    """
    if group_by not in CONSUMPTION_GROUP_BY_VALUES:
        raise StockError("group_by must be 'week' or 'month'")
    if date_to < date_from:
        raise StockError("date_to must be on or after date_from")

    period_days = (date_to - date_from).days + 1
    previous_date_to = date_from - timedelta(days=1)
    previous_date_from = previous_date_to - timedelta(days=period_days - 1)

    current_totals = _consumption_totals_by_item(db, hotel_id=hotel_id, date_from=date_from, date_to=date_to)
    previous_totals = _consumption_totals_by_item(
        db, hotel_id=hotel_id, date_from=previous_date_from, date_to=previous_date_to
    )

    item_ids = set(current_totals) | set(previous_totals)
    stock_items = (
        db.query(StockItem).filter(StockItem.hotel_id == hotel_id, StockItem.id.in_(item_ids)).all()
        if item_ids
        else []
    )
    items_by_id = {item.id: item for item in stock_items}

    items = []
    for item_id in item_ids:
        item = items_by_id.get(item_id)
        current = current_totals.get(item_id, Decimal("0.00"))
        previous = previous_totals.get(item_id, Decimal("0.00"))
        variation_pct = (
            ((current - previous) / previous * 100).quantize(Decimal("0.1")) if previous > 0 else None
        )
        items.append(
            {
                "stock_item_id": item_id,
                "stock_item_name": item.name if item else f"Item #{item_id}",
                "unit": item.unit if item else "",
                "current_quantity": current,
                "previous_quantity": previous,
                "variation_pct": variation_pct,
            }
        )
    items.sort(key=lambda entry: entry["stock_item_name"])

    return {
        "hotel_id": hotel_id,
        "group_by": group_by,
        "date_from": date_from,
        "date_to": date_to,
        "previous_date_from": previous_date_from,
        "previous_date_to": previous_date_to,
        "items": items,
    }


def _consumption_totals_by_item(
    db: Session, *, hotel_id: int, date_from: date, date_to: date
) -> dict[int, Decimal]:
    start = datetime.combine(date_from, time.min, tzinfo=timezone.utc)
    end = datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=timezone.utc)
    rows = (
        db.query(StockMovement.item_id, func.coalesce(func.sum(StockMovement.quantity), 0))
        .filter(
            StockMovement.hotel_id == hotel_id,
            StockMovement.movement_type.in_(_OUTBOUND_MOVEMENT_TYPES),
            StockMovement.created_at >= start,
            StockMovement.created_at < end,
        )
        .group_by(StockMovement.item_id)
        .all()
    )
    return {item_id: Decimal(total).quantize(Decimal("0.01")) for item_id, total in rows}


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
