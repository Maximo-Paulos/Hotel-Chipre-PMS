"""
Hotel-scoped stock and inventory movement service.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from uuid import NAMESPACE_URL, uuid5
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import case, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models.audit_log import AuditActionEnum
from app.models.hotel_config import HotelConfiguration
from app.models.stock import (
    StockCountLine,
    StockCountSession,
    StockItem,
    StockLocation,
    StockMovement,
)
from app.services import audit_log_service
from app.services.timezones import (
    hotel_business_now,
    hotel_today,
    normalize_timezone,
    utc_naive,
)

logger = logging.getLogger(__name__)


class StockError(ValueError):
    """Raised when a stock operation is invalid."""


class StockIdempotencyConflict(StockError):
    """Raised when a retry key is reused with a different stock payload."""


class StockCountRecountRequired(StockError):
    """Raised when ledger movements make one or more observed counts stale."""

    def __init__(self, items: list[dict[str, int | None]]) -> None:
        super().__init__(
            "Stock changed after it was counted; recount the affected items before confirmation"
        )
        self.items = items


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
        raise StockError(
            f'Ya existe un item de stock llamado "{name}" en este hotel'
        ) from exc
    return item


def update_stock_item(
    db: Session, *, hotel_id: int, item_id: int, **changes
) -> StockItem:
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


def update_location(
    db: Session, *, hotel_id: int, location_id: int, name: str
) -> StockLocation:
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

        severity = (
            NotificationSeverityEnum.CRITICAL
            if balance <= 0
            else NotificationSeverityEnum.WARNING
        )
        event_type = "stock.out_of_stock" if balance <= 0 else "stock.low"
        today = hotel_today(db, hotel_id).isoformat()
        enqueue_notifications_for_event(
            db,
            hotel_id=hotel_id,
            event_type=event_type,
            dedupe_key=f"{event_type}:{item.id}:{today}",
            title=f"Low stock: {item.name}"
            if balance > 0
            else f"Out of stock: {item.name}",
            severity=severity,
            entity_type="stock_item",
            entity_id=item.id,
            payload={"item_id": item.id, "status": "low" if balance > 0 else "out"},
            recipient_roles=list(ROLE_CODES),
        )
    except Exception as exc:
        logger.error(
            "stock.low_stock_notify_failed",
            extra={
                "hotel_id": hotel_id,
                "item_id": item.id,
                "error_type": type(exc).__name__,
            },
        )


def _return_matching_idempotent_movement(
    existing: StockMovement,
    *,
    item_id: int,
    location_id: int | None,
    movement_type: str,
    quantity: Decimal,
    reason: str | None,
    reservation_id: int | None,
    transfer_reference: str | None,
) -> StockMovement:
    """Return a replay only when it describes the same stock operation."""
    existing_payload = (
        existing.item_id,
        existing.location_id,
        existing.movement_type,
        existing.quantity,
        existing.reason,
        existing.reservation_id,
        existing.transfer_reference,
    )
    requested_payload = (
        item_id,
        location_id,
        movement_type,
        quantity,
        reason,
        reservation_id,
        transfer_reference,
    )
    if existing_payload != requested_payload:
        raise StockIdempotencyConflict(
            "Idempotency key was already used for a different stock movement"
        )
    return existing


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
    transfer_reference: str | None = None,
) -> StockMovement:
    # Resolve a retry before validating the new payload or looking up its item.
    # Once a key has been used, changing any operational field is a conflict,
    # including values that would otherwise fail normal movement validation.
    if idempotency_key is not None:
        existing = (
            db.query(StockMovement)
            .filter(
                StockMovement.hotel_id == hotel_id,
                StockMovement.idempotency_key == idempotency_key,
            )
            .one_or_none()
        )
        if existing is not None:
            return _return_matching_idempotent_movement(
                existing,
                item_id=item_id,
                location_id=location_id,
                movement_type=movement_type,
                quantity=quantity,
                reason=reason,
                reservation_id=reservation_id,
                transfer_reference=transfer_reference,
            )

    if movement_type not in VALID_MOVEMENT_TYPES:
        raise StockError("Invalid stock movement type")
    if not quantity.is_finite() or quantity <= 0:
        raise StockError("Stock movement quantity must be positive")
    if quantity > Decimal("9999999999.99"):
        raise StockError("Stock movement quantity exceeds Numeric(12, 2) capacity")
    if quantity % Decimal("0.01") != 0:
        raise StockError("Stock movement quantity supports at most two decimal places")
    if transfer_reference is not None and movement_type not in {"in", "out"}:
        raise StockError("Stock transfers only support inbound and outbound movements")
    item = (
        db.query(StockItem)
        .filter(
            StockItem.id == item_id,
            StockItem.hotel_id == hotel_id,
            StockItem.deleted_at.is_(None),
        )
        .with_for_update()
        .one_or_none()
    )
    if item is None:
        raise StockError("Stock item not found")
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
        created_at=utc_naive(hotel_business_now(db, hotel_id)),
        idempotency_key=idempotency_key,
        transfer_reference=transfer_reference,
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
        # session is still usable. A concurrent request may have won the key;
        # compare its payload before returning it. Re-raise unrelated integrity
        # errors (or keyless failures) instead of masking them as retries.
        if idempotency_key is None:
            raise
        existing = (
            db.query(StockMovement)
            .filter(
                StockMovement.hotel_id == hotel_id,
                StockMovement.idempotency_key == idempotency_key,
            )
            .one_or_none()
        )
        if existing is None:
            raise
        return _return_matching_idempotent_movement(
            existing,
            item_id=item_id,
            location_id=location_id,
            movement_type=movement_type,
            quantity=quantity,
            reason=reason,
            reservation_id=reservation_id,
            transfer_reference=transfer_reference,
        )
    # The item lock serializes this version change with both count capture and
    # count confirmation. Replayed idempotency keys return before this point.
    item.movement_version = (item.movement_version or 0) + 1
    db.flush()
    if movement_type in _OUTBOUND_MOVEMENT_TYPES:
        _notify_if_low_stock(db, hotel_id=hotel_id, item=item)
    return movement


def _normalize_stock_count_quantity(quantity: Decimal) -> Decimal:
    if not isinstance(quantity, Decimal) or not quantity.is_finite() or quantity < 0:
        raise StockError("Counted stock quantity must be a finite, non-negative number")
    if quantity > Decimal("9999999999.99"):
        raise StockError("Counted stock quantity exceeds Numeric(12, 2) capacity")
    if quantity % Decimal("0.01") != 0:
        raise StockError("Counted stock quantity supports at most two decimal places")
    return quantity.quantize(Decimal("0.01"))


def _required_reason(reason: str, *, field: str) -> str:
    normalized = (reason or "").strip()
    if not normalized:
        raise StockError(f"{field} is required")
    if len(normalized) > 1000:
        raise StockError(f"{field} must contain at most 1000 characters")
    return normalized


def create_stock_count_session(
    db: Session,
    *,
    hotel_id: int,
    created_by_user_id: int,
    reason: str,
) -> StockCountSession:
    normalized_reason = _required_reason(reason, field="Stock count reason")
    session = StockCountSession(
        hotel_id=hotel_id,
        status="open",
        reason=normalized_reason,
        created_by_user_id=created_by_user_id,
        created_at=utc_naive(hotel_business_now(db, hotel_id)),
    )
    db.add(session)
    db.flush()
    audit_log_service.create_audit_log(
        db,
        hotel_id=hotel_id,
        table_name="stock_count_sessions",
        record_id=session.id,
        action=AuditActionEnum.CREATE,
        actor_user_id=created_by_user_id,
        payload_after={
            "status": session.status,
            "reason": normalized_reason,
            "created_by_user_id": created_by_user_id,
        },
    )
    return session


def _get_open_stock_count_session(
    db: Session, *, hotel_id: int, session_id: int
) -> StockCountSession:
    session = (
        db.query(StockCountSession)
        .filter(
            StockCountSession.id == session_id, StockCountSession.hotel_id == hotel_id
        )
        .with_for_update()
        .one_or_none()
    )
    if session is None:
        raise StockError("Stock count session not found")
    if session.status != "open":
        raise StockError("Only an open stock count session can be changed")
    return session


def record_stock_count(
    db: Session,
    *,
    hotel_id: int,
    session_id: int,
    item_id: int,
    location_id: int | None,
    counted_quantity: Decimal,
    counted_by_user_id: int,
) -> StockCountLine:
    quantity = _normalize_stock_count_quantity(counted_quantity)
    session = _get_open_stock_count_session(
        db, hotel_id=hotel_id, session_id=session_id
    )

    if (
        session.counter_user_id is not None
        and session.counter_user_id != counted_by_user_id
    ):
        raise StockError("Only the session's original counter may record counts")

    item = (
        db.query(StockItem)
        .filter(
            StockItem.id == item_id,
            StockItem.hotel_id == hotel_id,
            StockItem.deleted_at.is_(None),
        )
        .with_for_update()
        .one_or_none()
    )
    if item is None:
        raise StockError("Stock item not found")
    if location_id is not None:
        _get_location(db, hotel_id=hotel_id, location_id=location_id)

    existing_item_lines = (
        db.query(StockCountLine)
        .filter(
            StockCountLine.hotel_id == hotel_id,
            StockCountLine.session_id == session.id,
            StockCountLine.item_id == item_id,
        )
        .with_for_update(of=StockCountLine)
        .all()
    )
    if location_id is None and any(
        line.location_id is not None for line in existing_item_lines
    ):
        raise StockError(
            "Count the item either hotel-wide or by location, not both in one session"
        )
    if location_id is not None and any(
        line.location_id is None for line in existing_item_lines
    ):
        raise StockError(
            "Count the item either hotel-wide or by location, not both in one session"
        )

    if session.counter_user_id is None:
        before_session = audit_log_service.model_snapshot(session)
        session.counter_user_id = counted_by_user_id
        db.flush()
        audit_log_service.create_audit_log(
            db,
            hotel_id=hotel_id,
            table_name="stock_count_sessions",
            record_id=session.id,
            action=AuditActionEnum.UPDATE,
            actor_user_id=counted_by_user_id,
            payload_before=before_session,
            payload_after={"counter_user_id": counted_by_user_id},
        )

    line = next(
        (entry for entry in existing_item_lines if entry.location_id == location_id),
        None,
    )
    before = None
    if line is None:
        line = StockCountLine(
            hotel_id=hotel_id,
            session_id=session.id,
            item_id=item_id,
            location_id=location_id,
        )
        db.add(line)
        action = AuditActionEnum.CREATE
    else:
        before = audit_log_service.model_snapshot(line)
        action = AuditActionEnum.UPDATE

    # A newly added count line is intentionally incomplete until all observed
    # values are assigned. Keep the balance query from autoflushing that row;
    # production sessions disable autoflush today, but service correctness
    # should not depend on that session-factory detail.
    with db.no_autoflush:
        system_quantity_at_count = current_stock(
            db,
            hotel_id=hotel_id,
            item_id=item_id,
            location_id=location_id,
        )
    line.system_quantity_at_count = system_quantity_at_count
    line.counted_quantity = quantity
    line.movement_version = item.movement_version or 0
    line.counted_by_user_id = counted_by_user_id
    line.counted_at = utc_naive(hotel_business_now(db, hotel_id))
    line.applied_adjustment = None
    line.adjusted_at = None
    db.flush()
    audit_log_service.create_audit_log(
        db,
        hotel_id=hotel_id,
        table_name="stock_count_lines",
        record_id=line.id,
        action=action,
        actor_user_id=counted_by_user_id,
        payload_before=before,
        payload_after={
            "session_id": session_id,
            "item_id": item_id,
            "location_id": location_id,
            "system_quantity_at_count": line.system_quantity_at_count,
            "counted_quantity": line.counted_quantity,
            "movement_version": line.movement_version,
            "counted_by_user_id": counted_by_user_id,
        },
    )
    return line


def _stock_count_session_query(db: Session):
    return db.query(StockCountSession).options(
        selectinload(StockCountSession.counts).joinedload(StockCountLine.item),
        selectinload(StockCountSession.counts).joinedload(StockCountLine.location),
    )


def get_stock_count_session(
    db: Session, *, hotel_id: int, session_id: int
) -> StockCountSession:
    session = (
        _stock_count_session_query(db)
        .filter(
            StockCountSession.id == session_id, StockCountSession.hotel_id == hotel_id
        )
        .one_or_none()
    )
    if session is None:
        raise StockError("Stock count session not found")
    return session


def list_stock_count_sessions(
    db: Session,
    *,
    hotel_id: int,
    limit: int = 100,
    offset: int = 0,
) -> list[StockCountSession]:
    if not 1 <= limit <= 200 or offset < 0:
        raise StockError("Stock count session pagination is invalid")
    return (
        db.query(StockCountSession)
        .filter(StockCountSession.hotel_id == hotel_id)
        .order_by(StockCountSession.created_at.desc(), StockCountSession.id.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )


def _stock_count_stale_items(
    lines: list[StockCountLine],
    items_by_id: dict[int, StockItem],
) -> list[dict[str, int | None]]:
    stale: list[dict[str, int | None]] = []
    for line in lines:
        item = items_by_id.get(line.item_id)
        if item is None or (item.movement_version or 0) != line.movement_version:
            stale.append({"item_id": line.item_id, "location_id": line.location_id})
    return stale


def confirm_stock_count_session(
    db: Session,
    *,
    hotel_id: int,
    session_id: int,
    confirmed_by_user_id: int,
    reason: str,
) -> StockCountSession:
    normalized_reason = _required_reason(
        reason, field="Stock count confirmation reason"
    )
    session = (
        _stock_count_session_query(db)
        .filter(
            StockCountSession.id == session_id, StockCountSession.hotel_id == hotel_id
        )
        .with_for_update(of=StockCountSession)
        .one_or_none()
    )
    if session is None:
        raise StockError("Stock count session not found")
    if session.status == "confirmed":
        # A retried request after a lost response must never apply adjustments
        # a second time. Return the committed result as the idempotent outcome.
        return session
    if session.status != "open":
        raise StockError("Only an open stock count session can be confirmed")
    lines = list(session.counts)
    if not lines:
        raise StockError("A stock count session needs at least one counted item")

    item_ids = sorted({line.item_id for line in lines})
    locked_items = (
        db.query(StockItem)
        .filter(
            StockItem.hotel_id == hotel_id,
            StockItem.id.in_(item_ids),
            StockItem.deleted_at.is_(None),
        )
        .order_by(StockItem.id.asc())
        # Count lines eagerly load their StockItem relationship before this
        # query. If a concurrent movement held the row lock, PostgreSQL returns
        # the latest tuple after waiting; refresh the ORM identity-map object
        # as well or stale validation would compare against its pre-wait value.
        .populate_existing()
        .with_for_update(of=StockItem)
        .all()
    )
    items_by_id = {item.id: item for item in locked_items}
    stale = _stock_count_stale_items(lines, items_by_id)
    if stale:
        raise StockCountRecountRequired(stale)

    hotel_config = db.get(HotelConfiguration, hotel_id)
    if hotel_config is None:
        raise StockError("Hotel configuration not found")
    self_approved = session.counter_user_id == confirmed_by_user_id
    if self_approved and not hotel_config.allow_stock_count_self_approval:
        raise StockError("A different user must confirm this stock count")

    signed_quantity = case(
        (
            StockMovement.movement_type.in_(_OUTBOUND_MOVEMENT_TYPES),
            -StockMovement.quantity,
        ),
        else_=StockMovement.quantity,
    )
    balances: dict[tuple[int, int | None], Decimal] = {}
    for item_id, location_id, total in (
        db.query(
            StockMovement.item_id,
            StockMovement.location_id,
            func.coalesce(func.sum(signed_quantity), 0),
        )
        .filter(StockMovement.hotel_id == hotel_id, StockMovement.item_id.in_(item_ids))
        .group_by(StockMovement.item_id, StockMovement.location_id)
        .all()
    ):
        balances[(item_id, location_id)] = Decimal(total).quantize(Decimal("0.01"))

    before = audit_log_service.model_snapshot(session)
    now = utc_naive(hotel_business_now(db, hotel_id))
    applied: list[dict[str, object]] = []
    for line in lines:
        if line.location_id is None:
            current = sum(
                (
                    value
                    for (candidate_id, _location_id), value in balances.items()
                    if candidate_id == line.item_id
                ),
                Decimal("0.00"),
            )
        else:
            current = balances.get((line.item_id, line.location_id), Decimal("0.00"))
        delta = (line.counted_quantity - current).quantize(Decimal("0.01"))
        if delta:
            movement = register_movement(
                db,
                hotel_id=hotel_id,
                item_id=line.item_id,
                location_id=line.location_id,
                movement_type="adjustment" if delta > 0 else "adjustment_out",
                quantity=abs(delta),
                reason=f"Stock count session {session.id}: {normalized_reason}",
                created_by_user_id=confirmed_by_user_id,
            )
        else:
            movement = None
        line.applied_adjustment = delta
        line.adjusted_at = now
        applied.append(
            {
                "item_id": line.item_id,
                "location_id": line.location_id,
                "system_quantity_at_count": line.system_quantity_at_count,
                "counted_quantity": line.counted_quantity,
                "applied_adjustment": delta,
                "movement_id": movement.id if movement is not None else None,
            }
        )

    session.status = "confirmed"
    session.confirmed_by_user_id = confirmed_by_user_id
    session.confirmation_reason = normalized_reason
    session.confirmed_at = now
    session.self_approved = self_approved
    db.flush()
    audit_log_service.create_audit_log(
        db,
        hotel_id=hotel_id,
        table_name="stock_count_sessions",
        record_id=session.id,
        action=AuditActionEnum.STATUS_CHANGE,
        actor_user_id=confirmed_by_user_id,
        payload_before=before,
        payload_after={
            "status": session.status,
            "confirmed_by_user_id": confirmed_by_user_id,
            "counter_user_id": session.counter_user_id,
            "self_approved": self_approved,
            "confirmation_reason": normalized_reason,
            "items": applied,
        },
    )
    return session


def cancel_stock_count_session(
    db: Session,
    *,
    hotel_id: int,
    session_id: int,
    cancelled_by_user_id: int,
    reason: str,
) -> StockCountSession:
    normalized_reason = _required_reason(
        reason, field="Stock count cancellation reason"
    )
    session = _get_open_stock_count_session(
        db, hotel_id=hotel_id, session_id=session_id
    )
    before = audit_log_service.model_snapshot(session)
    session.status = "cancelled"
    session.cancelled_by_user_id = cancelled_by_user_id
    session.cancellation_reason = normalized_reason
    session.cancelled_at = utc_naive(hotel_business_now(db, hotel_id))
    db.flush()
    audit_log_service.create_audit_log(
        db,
        hotel_id=hotel_id,
        table_name="stock_count_sessions",
        record_id=session.id,
        action=AuditActionEnum.STATUS_CHANGE,
        actor_user_id=cancelled_by_user_id,
        payload_before=before,
        payload_after=audit_log_service.model_snapshot(session),
    )
    return session


def register_opening_count(
    db: Session,
    *,
    hotel_id: int,
    item_id: int,
    location_id: int,
    quantity: Decimal,
    reason: str,
    created_by_user_id: int | None,
    idempotency_key: str,
) -> StockMovement:
    """Record an initial location count once, without overwriting history."""
    if quantity <= 0:
        raise StockError("Opening stock count must be positive")
    normalized_reason = reason.strip()
    if not normalized_reason:
        raise StockError("Opening stock count reason is required")

    movement_idempotency_key = str(
        uuid5(NAMESPACE_URL, f"stock-opening-count:{hotel_id}:{idempotency_key}")
    )

    item = (
        db.query(StockItem)
        .filter(
            StockItem.id == item_id,
            StockItem.hotel_id == hotel_id,
            StockItem.deleted_at.is_(None),
        )
        .with_for_update()
        .one_or_none()
    )
    if item is None:
        raise StockError("Stock item not found")

    existing = (
        db.query(StockMovement)
        .filter(
            StockMovement.hotel_id == hotel_id,
            StockMovement.idempotency_key == movement_idempotency_key,
        )
        .one_or_none()
    )
    if existing is not None:
        if (
            existing.item_id != item_id
            or existing.location_id != location_id
            or existing.movement_type != "in"
            or existing.quantity != quantity
            or existing.reason != normalized_reason
        ):
            raise StockIdempotencyConflict(
                "Idempotency key was already used for a different opening count"
            )
        return existing

    _get_location(db, hotel_id=hotel_id, location_id=location_id)
    prior_movement = (
        db.query(StockMovement.id)
        .filter(
            StockMovement.hotel_id == hotel_id,
            StockMovement.item_id == item_id,
            StockMovement.location_id == location_id,
        )
        .first()
    )
    if prior_movement is not None:
        raise StockError(
            "Opening count is only available before the item has movements at this location"
        )

    return register_movement(
        db,
        hotel_id=hotel_id,
        item_id=item_id,
        location_id=location_id,
        movement_type="in",
        quantity=quantity,
        reason=normalized_reason,
        created_by_user_id=created_by_user_id,
        idempotency_key=movement_idempotency_key,
    )


def transfer_stock(
    db: Session,
    *,
    hotel_id: int,
    item_id: int,
    source_location_id: int,
    destination_location_id: int,
    quantity: Decimal,
    reason: str,
    created_by_user_id: int | None,
    idempotency_key: str,
) -> tuple[str, StockMovement, StockMovement]:
    """Move stock between two locations with one durable, retry-safe ledger pair.

    The outer savepoint makes both movement inserts atomic even if a caller
    handles the resulting StockError without closing its whole transaction.
    """
    if quantity <= 0:
        raise StockError("Stock transfer quantity must be positive")
    if source_location_id == destination_location_id:
        raise StockError("Source and destination locations must be different")
    normalized_reason = reason.strip()
    if not normalized_reason:
        raise StockError("Stock transfer reason is required")

    transfer_reference = str(
        uuid5(NAMESPACE_URL, f"stock-transfer:{hotel_id}:{idempotency_key}")
    )
    item = (
        db.query(StockItem)
        .filter(
            StockItem.id == item_id,
            StockItem.hotel_id == hotel_id,
            StockItem.deleted_at.is_(None),
        )
        .with_for_update()
        .one_or_none()
    )
    if item is None:
        raise StockError("Stock item not found")

    # Locking the item serializes retries and competing transfers before this
    # lookup, so a second concurrent request sees the committed pair.
    existing_rows = (
        db.query(StockMovement)
        .filter(
            StockMovement.hotel_id == hotel_id,
            StockMovement.transfer_reference == transfer_reference,
        )
        .all()
    )
    if existing_rows:
        by_direction = {row.movement_type: row for row in existing_rows}
        outbound = by_direction.get("out")
        inbound = by_direction.get("in")
        if (
            len(existing_rows) != 2
            or outbound is None
            or inbound is None
            or outbound.item_id != item_id
            or inbound.item_id != item_id
            or outbound.location_id != source_location_id
            or inbound.location_id != destination_location_id
            or outbound.quantity != quantity
            or inbound.quantity != quantity
            or outbound.reason != normalized_reason
            or inbound.reason != normalized_reason
        ):
            raise StockIdempotencyConflict(
                "Idempotency key was already used for a different stock transfer"
            )
        return transfer_reference, outbound, inbound

    _get_location(db, hotel_id=hotel_id, location_id=source_location_id)
    _get_location(db, hotel_id=hotel_id, location_id=destination_location_id)
    with db.begin_nested():
        outbound = register_movement(
            db,
            hotel_id=hotel_id,
            item_id=item_id,
            location_id=source_location_id,
            movement_type="out",
            quantity=quantity,
            reason=normalized_reason,
            created_by_user_id=created_by_user_id,
            transfer_reference=transfer_reference,
        )
        inbound = register_movement(
            db,
            hotel_id=hotel_id,
            item_id=item_id,
            location_id=destination_location_id,
            movement_type="in",
            quantity=quantity,
            reason=normalized_reason,
            created_by_user_id=created_by_user_id,
            transfer_reference=transfer_reference,
        )
    return transfer_reference, outbound, inbound


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
    return (
        query.order_by(StockMovement.created_at.desc(), StockMovement.id.desc())
        .limit(limit)
        .all()
    )


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
        (
            StockMovement.movement_type.in_(_OUTBOUND_MOVEMENT_TYPES),
            -StockMovement.quantity,
        ),
        else_=StockMovement.quantity,
    )
    query = db.query(func.coalesce(func.sum(signed_quantity), 0)).filter(
        StockMovement.hotel_id == hotel_id, StockMovement.item_id == item_id
    )
    if location_id is not None:
        query = query.filter(StockMovement.location_id == location_id)
    total = query.scalar()
    return Decimal(total).quantize(Decimal("0.01"))


def stock_summary(
    db: Session, *, hotel_id: int, location_id: int | None = None
) -> list[dict]:
    """Every active item's hotel total and per-location balances in a small,
    fixed number of queries instead of the N+1 per-item balance lookups.
    """
    items = list_stock_items(db, hotel_id=hotel_id)
    if not items:
        return []
    if location_id is not None:
        active_locations = [
            _get_location(db, hotel_id=hotel_id, location_id=location_id)
        ]
    else:
        active_locations = list_locations(db, hotel_id=hotel_id)
    signed_quantity = case(
        (
            StockMovement.movement_type.in_(_OUTBOUND_MOVEMENT_TYPES),
            -StockMovement.quantity,
        ),
        else_=StockMovement.quantity,
    )
    query = db.query(
        StockMovement.item_id, func.coalesce(func.sum(signed_quantity), 0)
    ).filter(
        StockMovement.hotel_id == hotel_id,
        StockMovement.item_id.in_([item.id for item in items]),
    )
    if location_id is not None:
        query = query.filter(StockMovement.location_id == location_id)
    totals = {
        item_id: Decimal(total).quantize(Decimal("0.01"))
        for item_id, total in query.group_by(StockMovement.item_id).all()
    }
    location_totals: dict[tuple[int, int], tuple[Decimal, bool]] = {}
    if active_locations:
        location_query = (
            db.query(
                StockMovement.item_id,
                StockMovement.location_id,
                func.coalesce(func.sum(signed_quantity), 0),
                func.count(StockMovement.id),
            )
            .filter(
                StockMovement.hotel_id == hotel_id,
                StockMovement.item_id.in_([item.id for item in items]),
                StockMovement.location_id.in_(
                    [location.id for location in active_locations]
                ),
            )
            .group_by(StockMovement.item_id, StockMovement.location_id)
        )
        location_totals = {
            (item_id, current_location_id): (
                Decimal(total).quantize(Decimal("0.01")),
                movement_count > 0,
            )
            for item_id, current_location_id, total, movement_count in location_query.all()
        }
    return [
        {
            "item": item,
            "current_quantity": totals.get(item.id, Decimal("0.00")),
            "location_balances": [
                {
                    "location_id": location.id,
                    "location_name": location.name,
                    "current_quantity": location_totals.get(
                        (item.id, location.id), (Decimal("0.00"), False)
                    )[0],
                    "has_movements": location_totals.get(
                        (item.id, location.id), (Decimal("0.00"), False)
                    )[1],
                }
                for location in active_locations
            ],
        }
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
    return [
        item
        for item in items
        if current_stock(db, hotel_id=hotel_id, item_id=item.id) < item.min_quantity
    ]


def consumption_report(
    db: Session,
    *,
    hotel_id: int,
    date_from: date,
    date_to: date,
    group_by: str,
) -> dict:
    """Ordinary outbound stock (``out`` only) per item in the inclusive
    hotel-local calendar range [date_from, date_to], plus the same-length
    period immediately before it so the caller can show a variation % (D5 --
    see plan Via D: detect anomalous consumption, e.g. usage doubling with
    flat occupancy).
    """
    if group_by not in CONSUMPTION_GROUP_BY_VALUES:
        raise StockError("group_by must be 'week' or 'month'")
    if date_to < date_from:
        raise StockError("date_to must be on or after date_from")

    period_days = (date_to - date_from).days + 1
    previous_date_to = date_from - timedelta(days=1)
    previous_date_from = previous_date_to - timedelta(days=period_days - 1)

    hotel_timezone = _hotel_timezone(db, hotel_id=hotel_id)
    current_totals = _consumption_totals_by_item(
        db,
        hotel_id=hotel_id,
        date_from=date_from,
        date_to=date_to,
        hotel_timezone=hotel_timezone,
    )
    previous_totals = _consumption_totals_by_item(
        db,
        hotel_id=hotel_id,
        date_from=previous_date_from,
        date_to=previous_date_to,
        hotel_timezone=hotel_timezone,
    )

    item_ids = set(current_totals) | set(previous_totals)
    stock_items = (
        db.query(StockItem)
        .filter(StockItem.hotel_id == hotel_id, StockItem.id.in_(item_ids))
        .all()
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
            ((current - previous) / previous * 100).quantize(Decimal("0.1"))
            if previous > 0
            else None
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
    db: Session,
    *,
    hotel_id: int,
    date_from: date,
    date_to: date,
    hotel_timezone: ZoneInfo,
) -> dict[int, Decimal]:
    # Request dates are hotel-local calendar dates. Resolve both local
    # midnights independently so DST days can be 23 or 25 hours long.
    start = datetime.combine(date_from, time.min, tzinfo=hotel_timezone).astimezone(
        timezone.utc
    )
    end = datetime.combine(
        date_to + timedelta(days=1), time.min, tzinfo=hotel_timezone
    ).astimezone(timezone.utc)
    # StockMovement.created_at is a timezone-naive DateTime column whose
    # persisted values follow the app's UTC convention; compare naive UTC
    # bounds so PostgreSQL does not reinterpret a timestamptz parameter.
    start = start.replace(tzinfo=None)
    end = end.replace(tzinfo=None)
    rows = (
        db.query(
            StockMovement.item_id, func.coalesce(func.sum(StockMovement.quantity), 0)
        )
        .filter(
            StockMovement.hotel_id == hotel_id,
            StockMovement.movement_type == "out",
            StockMovement.transfer_reference.is_(None),
            StockMovement.created_at >= start,
            StockMovement.created_at < end,
        )
        .group_by(StockMovement.item_id)
        .all()
    )
    return {
        item_id: Decimal(total).quantize(Decimal("0.01")) for item_id, total in rows
    }


def _hotel_timezone(db: Session, *, hotel_id: int) -> ZoneInfo:
    hotel = db.get(HotelConfiguration, hotel_id)
    timezone_name = (hotel.hotel_timezone if hotel else None) or "UTC"
    try:
        return ZoneInfo(normalize_timezone(timezone_name))
    except (AttributeError, ValueError, ZoneInfoNotFoundError):
        # A missing or legacy-invalid setting must not make stock reports
        # unavailable. UTC is the established fallback for hotel calendars.
        logger.warning(
            "stock.invalid_hotel_timezone",
            extra={"hotel_id": hotel_id},
        )
        return ZoneInfo("UTC")


def get_stock_item(db: Session, *, hotel_id: int, item_id: int) -> StockItem:
    return _get_item(db, hotel_id=hotel_id, item_id=item_id)


def get_location(db: Session, *, hotel_id: int, location_id: int) -> StockLocation:
    return _get_location(db, hotel_id=hotel_id, location_id=location_id)


def _get_item(db: Session, *, hotel_id: int, item_id: int) -> StockItem:
    item = (
        db.query(StockItem)
        .filter(
            StockItem.id == item_id,
            StockItem.hotel_id == hotel_id,
            StockItem.deleted_at.is_(None),
        )
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
