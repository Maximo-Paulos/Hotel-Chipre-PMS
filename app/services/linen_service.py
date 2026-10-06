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
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import case, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.audit_log import AuditActionEnum
from app.models.linen import LinenItem, LinenLocation, LinenMovement, LinenParLevel
from app.models.laundry_vendor import LaundryVendor
from app.services import audit_log_service


class LinenError(ValueError):
    """Raised when a linen inventory operation is invalid."""


class LinenNotFoundError(LinenError):
    """Raised when a hotel-scoped linen resource does not exist."""


class LinenOpeningCountConflict(LinenError):
    """Raised when an opening count cannot replace existing inventory history."""


class LinenIdempotencyConflict(LinenError):
    """Raised when a transfer retry key is reused for another payload."""


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
        raise LinenNotFoundError("No se encontró el artículo de ropa blanca.")
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
        raise LinenError(f'Ya existe una ubicación de ropa blanca llamada "{name}" en este hotel') from exc
    return location


def set_location_minimum(
    db: Session,
    *,
    hotel_id: int,
    item_id: int,
    location_id: int,
    min_quantity: Decimal,
    actor_user_id: int | None = None,
) -> LinenParLevel:
    if min_quantity < 0:
        raise LinenError("El mínimo no puede ser negativo")
    get_linen_item(db, hotel_id=hotel_id, item_id=item_id)
    get_location(db, hotel_id=hotel_id, location_id=location_id)
    par_level = (
        db.query(LinenParLevel)
        .filter_by(hotel_id=hotel_id, item_id=item_id, location_id=location_id)
        .with_for_update()
        .one_or_none()
    )
    before = None
    if par_level is None:
        par_level = LinenParLevel(
            hotel_id=hotel_id,
            item_id=item_id,
            location_id=location_id,
            min_quantity=min_quantity,
            created_by_user_id=actor_user_id,
            updated_by_user_id=actor_user_id,
        )
        db.add(par_level)
    else:
        before = audit_log_service.model_snapshot(par_level)
        par_level.min_quantity = min_quantity
        par_level.updated_by_user_id = actor_user_id
    db.flush()
    audit_log_service.safe_create_audit_log(
        db,
        hotel_id=hotel_id,
        table_name="linen_par_levels",
        record_id=par_level.id,
        action=AuditActionEnum.CREATE if before is None else AuditActionEnum.UPDATE,
        actor_user_id=actor_user_id,
        payload_before=before,
        payload_after=audit_log_service.model_snapshot(par_level),
    )
    return par_level


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
        raise LinenNotFoundError("No se encontró la ubicación de ropa blanca.")
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
    transfer_reference: str | None = None,
) -> LinenMovement:
    if movement_type not in VALID_MOVEMENT_TYPES:
        raise LinenError("El tipo de movimiento de ropa blanca no es válido.")
    if quantity <= 0:
        raise LinenError("La cantidad del movimiento de ropa blanca debe ser positiva.")
    item = (
        db.query(LinenItem)
        .filter(LinenItem.id == item_id, LinenItem.hotel_id == hotel_id, LinenItem.deleted_at.is_(None))
        .with_for_update()
        .one_or_none()
    )
    if item is None:
        raise LinenNotFoundError("No se encontró el artículo de ropa blanca.")
    # Same per-location bug as stock_service.register_movement: an outbound
    # movement scoped to one location must only be checked against THAT
    # location's balance, not the hotel-wide total across every location.
    if movement_type in _OUTBOUND_MOVEMENT_TYPES and quantity > current_stock(
        db, hotel_id=hotel_id, item_id=item.id, location_id=location_id
    ):
        raise LinenError("El movimiento dejaría negativo el stock de ropa blanca.")
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
        transfer_reference=transfer_reference,
    )
    db.add(movement)
    db.flush()
    return movement


def transfer_linen_stock(
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
) -> tuple[str, LinenMovement, LinenMovement]:
    """Move linen between hotel locations as one linked, retry-safe ledger pair."""
    normalized_reason = reason.strip()
    if quantity <= 0:
        raise LinenError("La cantidad de la transferencia debe ser positiva.")
    if source_location_id == destination_location_id:
        raise LinenError("Las ubicaciones de origen y destino deben ser distintas.")
    if not normalized_reason:
        raise LinenError("El motivo de la transferencia es obligatorio.")

    transfer_reference = str(uuid5(NAMESPACE_URL, f"linen-transfer:{hotel_id}:{idempotency_key}"))
    item = (
        db.query(LinenItem)
        .filter(LinenItem.id == item_id, LinenItem.hotel_id == hotel_id, LinenItem.deleted_at.is_(None))
        .with_for_update(of=LinenItem)
        .one_or_none()
    )
    if item is None:
        raise LinenNotFoundError("No se encontró el artículo de ropa blanca.")

    existing_rows = (
        db.query(LinenMovement)
        .filter(LinenMovement.hotel_id == hotel_id, LinenMovement.transfer_reference == transfer_reference)
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
            or outbound.created_by_user_id != created_by_user_id
            or inbound.created_by_user_id != created_by_user_id
        ):
            raise LinenIdempotencyConflict("Idempotency key was already used for a different linen transfer")
        return transfer_reference, outbound, inbound

    get_location(db, hotel_id=hotel_id, location_id=source_location_id)
    get_location(db, hotel_id=hotel_id, location_id=destination_location_id)
    vendor_location_ids = {
        location_id
        for (location_id,) in db.query(LaundryVendor.linen_location_id)
        .filter(
            LaundryVendor.hotel_id == hotel_id,
            LaundryVendor.linen_location_id.in_([source_location_id, destination_location_id]),
        )
        .all()
    }
    if vendor_location_ids:
        raise LinenError("Usá un remito de lavandería para transferir ropa hacia o desde un lavadero.")

    if quantity > current_stock(db, hotel_id=hotel_id, item_id=item_id, location_id=source_location_id):
        raise LinenError("La transferencia dejaría negativo el stock en la ubicación de origen.")

    try:
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
    except IntegrityError:
        existing_rows = (
            db.query(LinenMovement)
            .filter(LinenMovement.hotel_id == hotel_id, LinenMovement.transfer_reference == transfer_reference)
            .all()
        )
        if existing_rows:
            by_direction = {row.movement_type: row for row in existing_rows}
            outbound = by_direction.get("out")
            inbound = by_direction.get("in")
            if (
                len(existing_rows) == 2
                and outbound is not None
                and inbound is not None
                and outbound.item_id == item_id
                and inbound.item_id == item_id
                and outbound.location_id == source_location_id
                and inbound.location_id == destination_location_id
                and outbound.quantity == quantity
                and inbound.quantity == quantity
                and outbound.reason == normalized_reason
                and inbound.reason == normalized_reason
                and outbound.created_by_user_id == created_by_user_id
                and inbound.created_by_user_id == created_by_user_id
            ):
                return transfer_reference, outbound, inbound
            raise LinenIdempotencyConflict("Idempotency key was already used for a different linen transfer")
        raise
    return transfer_reference, outbound, inbound


def register_opening_counts(
    db: Session,
    *,
    hotel_id: int,
    counts: list[dict],
    reason: str,
    created_by_user_id: int | None,
) -> list[LinenMovement]:
    """Record a location-by-item opening count as one all-or-nothing batch."""
    normalized_reason = reason.strip()
    if not normalized_reason:
        raise LinenError("El motivo del conteo inicial es obligatorio.")
    if not counts:
        raise LinenError("El conteo inicial necesita al menos un artículo y una ubicación.")

    count_by_pair: dict[tuple[int, int], Decimal] = {}
    for row in counts:
        item_id = int(row["linen_item_id"])
        location_id = int(row["location_id"])
        quantity = Decimal(row["quantity"])
        if quantity <= 0:
            raise LinenError("Las cantidades del conteo inicial deben ser positivas.")
        pair = (item_id, location_id)
        if pair in count_by_pair:
            raise LinenError("Un artículo y una ubicación solo pueden aparecer una vez en el conteo inicial.")
        count_by_pair[pair] = quantity

    item_ids = sorted({item_id for item_id, _ in count_by_pair})
    location_ids = sorted({location_id for _, location_id in count_by_pair})
    items = (
        db.query(LinenItem)
        .filter(
            LinenItem.hotel_id == hotel_id,
            LinenItem.id.in_(item_ids),
            LinenItem.deleted_at.is_(None),
        )
        .order_by(LinenItem.id.asc())
        .with_for_update(of=LinenItem)
        .all()
    )
    item_by_id = {item.id: item for item in items}
    if len(item_by_id) != len(item_ids):
        raise LinenNotFoundError("No se encontró el artículo de ropa blanca.")

    locations = (
        db.query(LinenLocation)
        .filter(
            LinenLocation.hotel_id == hotel_id,
            LinenLocation.id.in_(location_ids),
            LinenLocation.deleted_at.is_(None),
        )
        .all()
    )
    location_by_id = {location.id: location for location in locations}
    if len(location_by_id) != len(location_ids):
        raise LinenNotFoundError("No se encontró la ubicación de ropa blanca.")

    prior_pairs = {
        (item_id, location_id)
        for item_id, location_id in db.query(LinenMovement.item_id, LinenMovement.location_id)
        .filter(
            LinenMovement.hotel_id == hotel_id,
            LinenMovement.item_id.in_(item_ids),
            LinenMovement.location_id.in_(location_ids),
        )
        .distinct()
        .all()
    }
    conflicts = sorted(set(count_by_pair).intersection(prior_pairs))
    if conflicts:
        item_id, location_id = conflicts[0]
        raise LinenOpeningCountConflict(
            "El conteo inicial solo está disponible antes de que existan movimientos previos en esta ubicación: "
            f"{item_by_id[item_id].name} — {location_by_id[location_id].name}"
        )

    movements = [
        LinenMovement(
            hotel_id=hotel_id,
            item_id=item_id,
            location_id=location_id,
            movement_type="in",
            quantity=quantity,
            reason=normalized_reason,
            created_by_user_id=created_by_user_id,
        )
        for (item_id, location_id), quantity in sorted(count_by_pair.items())
    ]
    with db.begin_nested():
        db.add_all(movements)
        db.flush()
    return movements


def linen_summary(db: Session, *, hotel_id: int, location_id: int | None = None) -> list[dict]:
    """Every active linen item's current balance in one query pair, instead
    of the N+1 pattern of calling current_stock() once per item (see
    LaundryPage.tsx's houseStockQueries useQueries loop -- this is its
    backend counterpart, mirroring stock_service.stock_summary).
    """
    if location_id is not None:
        get_location(db, hotel_id=hotel_id, location_id=location_id)
    items = list_linen_items(db, hotel_id=hotel_id)
    if not items:
        return []
    signed_quantity = case(
        (LinenMovement.movement_type.in_(_OUTBOUND_MOVEMENT_TYPES), -LinenMovement.quantity),
        else_=LinenMovement.quantity,
    )
    query = (
        db.query(
            LinenMovement.item_id,
            LinenMovement.location_id,
            func.coalesce(func.sum(signed_quantity), 0),
            func.count(LinenMovement.id),
        )
        .filter(LinenMovement.hotel_id == hotel_id, LinenMovement.item_id.in_([item.id for item in items]))
    )
    if location_id is not None:
        query = query.filter(LinenMovement.location_id == location_id)
    movement_rows = query.group_by(LinenMovement.item_id, LinenMovement.location_id).all()
    totals: dict[int, Decimal] = {}
    location_balances: dict[int, dict[int, Decimal]] = {}
    location_movement_counts: dict[int, dict[int, int]] = {}
    for item_id, movement_location_id, total, movement_count in movement_rows:
        quantity = Decimal(total).quantize(Decimal("0.01"))
        totals[item_id] = totals.get(item_id, Decimal("0.00")) + quantity
        if movement_location_id is not None:
            location_balances.setdefault(item_id, {})[movement_location_id] = quantity
            location_movement_counts.setdefault(item_id, {})[movement_location_id] = movement_count
    minimums: dict[int, Decimal] = {}
    if location_id is not None:
        minimums = {
            item_id: Decimal(quantity).quantize(Decimal("0.01"))
            for item_id, quantity in db.query(LinenParLevel.item_id, LinenParLevel.min_quantity)
            .filter(
                LinenParLevel.hotel_id == hotel_id,
                LinenParLevel.location_id == location_id,
                LinenParLevel.item_id.in_([item.id for item in items]),
            )
            .all()
        }
    return [
        {
            "item": item,
            "current_quantity": totals.get(item.id, Decimal("0.00")),
            "min_quantity": minimums.get(item.id),
            "location_balances": [
                {
                    "location_id": current_location_id,
                    "current_quantity": quantity,
                    "has_movements": location_movement_counts[item.id][current_location_id] > 0,
                }
                for current_location_id, quantity in sorted(location_balances.get(item.id, {}).items())
            ],
        }
        for item in items
    ]


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
