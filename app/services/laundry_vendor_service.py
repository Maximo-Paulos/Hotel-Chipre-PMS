"""
Outsourced laundry vendors: vendor/price catalog + remito transfers.

A remito is not a new kind of business event -- it is a LinenMovement
transfer between two LinenLocations (the hotel's "clean linen" location,
chosen explicitly per remito by the caller, and the vendor's own location).
See app/services/linen_service.py for the underlying movement/balance
primitives this builds on (a table set physically separate from
app/services/stock_service.py's general-supplies inventory).
"""
from __future__ import annotations

import calendar
import json
from datetime import date, datetime, time, timezone
from decimal import Decimal

from sqlalchemy import case, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.hotel_config import HotelConfiguration
from app.models.hotel_membership import HotelMembership
from app.models.laundry_vendor import (
    LaundryRemito,
    LaundryRemitoLine,
    LaundryVendor,
    LaundryVendorPrice,
    LaundryVendorSettlement,
)
from app.models.security_audit_log import SecurityAuditLog
from app.models.user import User
from app.services import linen_service

DIRECTIONS = {"outbound", "inbound"}
QUARTER_MONTHS = {1: (1, 3), 2: (4, 6), 3: (7, 9), 4: (10, 12)}


class LaundryVendorError(ValueError):
    """Raised when a laundry vendor/remito operation is invalid."""


class DuplicateLaundryRemitoError(LaundryVendorError):
    """The vendor already has a remito with this number and direction."""


def is_duplicate_remito_integrity_error(error: IntegrityError) -> bool:
    original = getattr(error, "orig", error)
    constraint_name = getattr(getattr(original, "diag", None), "constraint_name", None)
    if constraint_name == "uq_laundry_remitos_hotel_vendor_direction_number":
        return True
    message = str(original).lower()
    return all(
        column in message
        for column in (
            "laundry_remitos.hotel_id",
            "laundry_remitos.vendor_id",
            "laundry_remitos.direction",
            "laundry_remitos.remito_number",
        )
    ) and ("unique" in message or "duplicate" in message)


def create_vendor(
    db: Session,
    *,
    hotel_id: int,
    name: str,
    contact_phone: str | None = None,
    contact_email: str | None = None,
    active: bool = True,
) -> LaundryVendor:
    """Create a vendor and its dedicated LinenLocation in one transaction."""

    location = linen_service.create_location(db, hotel_id=hotel_id, name=f"Lavadero - {name}")
    vendor = LaundryVendor(
        hotel_id=hotel_id,
        name=name,
        linen_location_id=location.id,
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
    linen_item_id: int,
    unit_price: Decimal,
    effective_from: date | None = None,
    currency_code: str | None = None,
    actor_user_id: int | None = None,
) -> LaundryVendorPrice:
    """Create or revise the price for one vendor, item and effective date."""

    if unit_price < 0:
        raise LaundryVendorError("El precio unitario no puede ser negativo.")
    effective_from = effective_from or date.today()
    _get_vendor(db, hotel_id=hotel_id, vendor_id=vendor_id)
    linen_service.get_linen_item(db, hotel_id=hotel_id, item_id=linen_item_id)

    price = (
        db.query(LaundryVendorPrice)
        .filter(
            LaundryVendorPrice.hotel_id == hotel_id,
            LaundryVendorPrice.vendor_id == vendor_id,
            LaundryVendorPrice.linen_item_id == linen_item_id,
            LaundryVendorPrice.effective_from == effective_from,
        )
        .with_for_update()
        .one_or_none()
    )
    if currency_code is None:
        currency_code = price.currency_code if price is not None else _default_currency(db, hotel_id=hotel_id)

    previous_amount = price.unit_price if price is not None else None
    if price is None:
        price = LaundryVendorPrice(
            hotel_id=hotel_id,
            vendor_id=vendor_id,
            linen_item_id=linen_item_id,
            unit_price=unit_price,
            effective_from=effective_from,
            currency_code=currency_code,
        )
        db.add(price)
    else:
        price.unit_price = unit_price
        price.currency_code = currency_code
        price.updated_at = datetime.now(timezone.utc)
    db.flush()
    db.add(
        SecurityAuditLog(
            hotel_id=hotel_id,
            user_id=actor_user_id,
            action="laundry.vendor_price.set",
            resource_type="laundry_vendor_price",
            resource_id=str(price.id),
            details=json.dumps(
                {
                    "vendor_id": vendor_id,
                    "linen_item_id": linen_item_id,
                    "effective_from": effective_from.isoformat(),
                    "previous_unit_price": str(previous_amount) if previous_amount is not None else None,
                    "unit_price": str(unit_price),
                    "currency_code": currency_code,
                },
                sort_keys=True,
            ),
        )
    )
    return price


def list_vendor_prices(db: Session, *, hotel_id: int, vendor_id: int) -> list[LaundryVendorPrice]:
    _get_vendor(db, hotel_id=hotel_id, vendor_id=vendor_id)
    return (
        db.query(LaundryVendorPrice)
        .filter(LaundryVendorPrice.hotel_id == hotel_id, LaundryVendorPrice.vendor_id == vendor_id)
        .order_by(LaundryVendorPrice.linen_item_id.asc(), LaundryVendorPrice.effective_from.asc(), LaundryVendorPrice.id.asc())
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
    reconciliation_warnings: list[str] | None = None,
) -> LaundryRemito:
    """Record a remito as LinenMovements, including any declared loss.

    outbound: house_location -> vendor_location (dirty linen leaves the hotel)
    inbound:  vendor_location -> house_location (clean linen comes back), with
              any declared missing quantity written off at the vendor location

    The hotel-wide total per item only decreases by explicitly declared
    missing_quantity. Any failure rolls back the whole remito: no partial
    remito or dangling movements are left behind.
    """

    if direction not in DIRECTIONS:
        raise LaundryVendorError("La operación debe ser un retiro o una entrega del lavadero.")
    if not lines:
        raise LaundryVendorError("El remito debe incluir al menos un artículo.")
    remito_number = remito_number.strip()
    if not remito_number:
        raise LaundryVendorError("El número de remito es obligatorio")

    vendor = _get_vendor(db, hotel_id=hotel_id, vendor_id=vendor_id)
    duplicate = (
        db.query(LaundryRemito.id)
        .filter(
            LaundryRemito.hotel_id == hotel_id,
            LaundryRemito.vendor_id == vendor_id,
            LaundryRemito.direction == direction,
            LaundryRemito.remito_number == remito_number,
        )
        .first()
    )
    if duplicate is not None:
        raise DuplicateLaundryRemitoError(
            "Ya existe un remito con ese número, lavadero y sentido. Revisá si es salida o entrada."
        )
    linen_service.get_location(db, hotel_id=hotel_id, location_id=house_location_id)

    if direction == "outbound":
        source_location_id, dest_location_id = house_location_id, vendor.linen_location_id
    else:
        source_location_id, dest_location_id = vendor.linen_location_id, house_location_id

    try:
        remito = LaundryRemito(
            hotel_id=hotel_id,
            vendor_id=vendor_id,
            direction=direction,
            house_location_id=house_location_id,
            remito_number=remito_number,
            remito_date=remito_date,
            notes=notes,
            created_by_user_id=actor_user_id,
        )
        db.add(remito)
        db.flush()

        for line in lines:
            linen_item_id = line["linen_item_id"]
            quantity = line["quantity"]
            missing_quantity = line.get("missing_quantity", Decimal("0"))
            if quantity < 0 or missing_quantity < 0 or (quantity == 0 and missing_quantity == 0):
                raise LaundryVendorError("La cantidad devuelta o faltante debe ser positiva")
            if direction == "outbound" and missing_quantity > 0:
                raise LaundryVendorError("El faltante solo se puede informar en una entrega del lavadero")

            item = linen_service.get_linen_item(db, hotel_id=hotel_id, item_id=linen_item_id)
            available = linen_service.current_stock(
                db, hotel_id=hotel_id, item_id=linen_item_id, location_id=source_location_id
            )
            source_quantity = quantity + missing_quantity if direction == "inbound" else quantity
            if direction == "inbound":
                if missing_quantity > available:
                    source_quantity = missing_quantity
                else:
                    available_for_return = available - missing_quantity
                    if quantity > available_for_return:
                        reconciliation_quantity = quantity - available_for_return
                        linen_service.register_movement(
                            db,
                            hotel_id=hotel_id,
                            item_id=linen_item_id,
                            location_id=source_location_id,
                            movement_type="adjustment",
                            quantity=reconciliation_quantity,
                            reason=(
                                f"Conciliación de entrega mayor al saldo registrado "
                                f"(remito {remito_number}, id {remito.id})"
                            ),
                            created_by_user_id=actor_user_id,
                        )
                        available += reconciliation_quantity
                        if reconciliation_warnings is not None:
                            reconciliation_warnings.append(
                                "Entrega mayor a lo registrado: "
                                f"se ajustó +{reconciliation_quantity} de «{item.name}» en el lavadero."
                            )
            if source_quantity > available:
                location = linen_service.get_location(db, hotel_id=hotel_id, location_id=source_location_id)
                diagnosis = (
                    "Verificá que el remito de retiro previo de este mismo lavadero esté registrado "
                    "y que el conteo inicial sea correcto."
                    if direction == "inbound"
                    else "Verificá el conteo inicial de la ubicación."
                )
                raise LaundryVendorError(
                    f"No hay suficiente «{item.name}» en la ubicación de origen «{location.name}»: "
                    f"hay {available}, se necesitan {source_quantity}. {diagnosis}"
                )

            if quantity > 0:
                movement_reason = f"Laundry remito {remito_number} ({direction})"
                linen_service.register_movement(
                    db,
                    hotel_id=hotel_id,
                    item_id=linen_item_id,
                    location_id=source_location_id,
                    movement_type="out",
                    quantity=quantity,
                    reason=movement_reason,
                    created_by_user_id=actor_user_id,
                )
                linen_service.register_movement(
                    db,
                    hotel_id=hotel_id,
                    item_id=linen_item_id,
                    location_id=dest_location_id,
                    movement_type="in",
                    quantity=quantity,
                    reason=movement_reason,
                    created_by_user_id=actor_user_id,
                )

            if missing_quantity > 0:
                linen_service.register_movement(
                    db,
                    hotel_id=hotel_id,
                    item_id=linen_item_id,
                    location_id=source_location_id,
                    movement_type="adjustment_out",
                    quantity=missing_quantity,
                    reason=(
                        f"Faltante declarado en remito interno {remito.id} "
                        f"(número de proveedor {remito_number})"
                    ),
                    created_by_user_id=actor_user_id,
                )

            price = (
                db.query(LaundryVendorPrice)
                .filter(
                    LaundryVendorPrice.hotel_id == hotel_id,
                    LaundryVendorPrice.vendor_id == vendor_id,
                    LaundryVendorPrice.linen_item_id == linen_item_id,
                    LaundryVendorPrice.effective_from <= remito_date.date(),
                )
                .order_by(LaundryVendorPrice.effective_from.desc(), LaundryVendorPrice.id.desc())
                .first()
            )
            line_record = LaundryRemitoLine(
                hotel_id=hotel_id,
                remito_id=remito.id,
                linen_item_id=linen_item_id,
                quantity=quantity,
                missing_quantity=missing_quantity,
                unit_price_snapshot=price.unit_price if price is not None else None,
                follow_up_status="open" if missing_quantity > 0 else None,
            )
            db.add(line_record)
            db.flush()
            if missing_quantity > 0:
                db.add(
                    SecurityAuditLog(
                        hotel_id=hotel_id,
                        user_id=actor_user_id,
                        action="laundry.missing_follow_up.opened",
                        resource_type="laundry_remito_line",
                        resource_id=str(line_record.id),
                        details=json.dumps(
                            {
                                "remito_id": remito.id,
                                "missing_quantity": str(missing_quantity),
                                "status": "open",
                            },
                            sort_keys=True,
                        ),
                    )
                )
    except IntegrityError as exc:
        db.rollback()
        if is_duplicate_remito_integrity_error(exc):
            raise DuplicateLaundryRemitoError(
                "Ya existe un remito con ese número, lavadero y sentido. Revisá si es salida o entrada."
            ) from exc
        raise
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


def remito_creator_labels(db: Session, *, hotel_id: int, remitos: list[LaundryRemito]) -> dict[int, str]:
    """Resolve hotel aliases for history without returning email addresses."""
    creator_ids = {remito.created_by_user_id for remito in remitos if remito.created_by_user_id is not None}
    if not creator_ids:
        return {}
    rows = (
        db.query(HotelMembership.user_id, HotelMembership.alias, User.display_name)
        .outerjoin(User, User.id == HotelMembership.user_id)
        .filter(HotelMembership.hotel_id == hotel_id, HotelMembership.user_id.in_(creator_ids))
        .all()
    )
    labels: dict[int, str] = {}
    for user_id, alias, display_name in rows:
        label = (alias or "").strip() or (display_name or "").strip()
        if label:
            labels[user_id] = label
    return labels


def vendor_balance(db: Session, *, hotel_id: int, vendor_id: int) -> list[dict]:
    """What is physically at the vendor's laundry right now, per item."""

    vendor = _get_vendor(db, hotel_id=hotel_id, vendor_id=vendor_id)
    item_ids = (
        db.query(LaundryRemitoLine.linen_item_id)
        .join(LaundryRemito, LaundryRemito.id == LaundryRemitoLine.remito_id)
        .filter(LaundryRemito.hotel_id == hotel_id, LaundryRemito.vendor_id == vendor_id)
        .distinct()
        .all()
    )
    balances = []
    for (item_id,) in item_ids:
        item = linen_service.get_linen_item(db, hotel_id=hotel_id, item_id=item_id)
        quantity = linen_service.current_stock(
            db, hotel_id=hotel_id, item_id=item_id, location_id=vendor.linen_location_id
        )
        balances.append({"linen_item_id": item.id, "linen_item_name": item.name, "quantity": quantity})
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
            LaundryRemitoLine.linen_item_id,
            func.coalesce(
                func.sum(
                    case(
                        (LaundryRemitoLine.unit_price_snapshot.is_not(None), LaundryRemitoLine.quantity * LaundryRemitoLine.unit_price_snapshot),
                        else_=0,
                    )
                ),
                0,
            ),
            func.coalesce(func.sum(LaundryRemitoLine.quantity), 0),
            func.coalesce(
                func.sum(
                    case(
                        (LaundryRemitoLine.unit_price_snapshot.is_(None), LaundryRemitoLine.quantity),
                        else_=0,
                    )
                ),
                0,
            ),
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
    unpriced_quantity_total = Decimal("0.00")
    for linen_item_id, subtotal, quantity, unpriced_quantity in query.group_by(LaundryRemitoLine.linen_item_id).all():
        item = linen_service.get_linen_item(db, hotel_id=hotel_id, item_id=linen_item_id)
        subtotal = Decimal(subtotal).quantize(Decimal("0.01"))
        unpriced_quantity = Decimal(unpriced_quantity).quantize(Decimal("0.01"))
        total += subtotal
        unpriced_quantity_total += unpriced_quantity
        by_item.append(
            {
                "linen_item_id": item.id,
                "linen_item_name": item.name,
                "quantity": Decimal(quantity).quantize(Decimal("0.01")),
                "subtotal": subtotal,
                "unpriced_quantity": unpriced_quantity,
            }
        )
    return {"total": total, "unpriced_quantity": unpriced_quantity_total, "by_item": by_item}


def _quarter_bounds(year: int, quarter: int) -> tuple[date, date]:
    start_month, end_month = QUARTER_MONTHS[quarter]
    period_start = date(year, start_month, 1)
    period_end = date(year, end_month, calendar.monthrange(year, end_month)[1])
    return period_start, period_end


def vendor_settlements(db: Session, *, hotel_id: int, vendor_id: int, year: int) -> list[dict]:
    """The 4 calendar quarters of a year for one vendor, cost computed live.

    Reuses vendor_spend (which already sums unit_price_snapshot, never the
    live vendor price) per quarter instead of storing a total, so a remito
    loaded late with a retroactive date never leaves a stale number behind.
    """

    _get_vendor(db, hotel_id=hotel_id, vendor_id=vendor_id)
    existing_by_start = {
        settlement.period_start: settlement
        for settlement in db.query(LaundryVendorSettlement)
        .filter(LaundryVendorSettlement.hotel_id == hotel_id, LaundryVendorSettlement.vendor_id == vendor_id)
        .all()
    }

    results = []
    for quarter in (1, 2, 3, 4):
        period_start, period_end = _quarter_bounds(year, quarter)
        spend = vendor_spend(
            db,
            hotel_id=hotel_id,
            vendor_id=vendor_id,
            date_from=datetime.combine(period_start, time.min, tzinfo=timezone.utc),
            date_to=datetime.combine(period_end, time.max, tzinfo=timezone.utc),
        )
        settlement = existing_by_start.get(period_start)
        results.append(
            {
                "period_start": period_start,
                "period_end": period_end,
                "total_amount": spend["total"],
                "unpriced_quantity": spend["unpriced_quantity"],
                "by_item": spend["by_item"],
                "paid": settlement.paid if settlement is not None else False,
                "paid_at": settlement.paid_at if settlement is not None else None,
                "notes": settlement.notes if settlement is not None else None,
            }
        )
    return results


def mark_vendor_settlement_paid(
    db: Session,
    *,
    hotel_id: int,
    vendor_id: int,
    period_start: date,
    paid: bool,
    notes: str | None = None,
    actor_user_id: int | None = None,
) -> LaundryVendorSettlement:
    """Upsert the paid/not-paid mark for one quarter. Visual alert only -- never blocks anything."""

    _get_vendor(db, hotel_id=hotel_id, vendor_id=vendor_id)
    quarter = (period_start.month - 1) // 3 + 1
    expected_start, period_end = _quarter_bounds(period_start.year, quarter)
    if period_start != expected_start:
        raise LaundryVendorError("El período debe comenzar el primer día de un trimestre calendario.")

    settlement = (
        db.query(LaundryVendorSettlement)
        .filter(
            LaundryVendorSettlement.hotel_id == hotel_id,
            LaundryVendorSettlement.vendor_id == vendor_id,
            LaundryVendorSettlement.period_start == period_start,
        )
        .one_or_none()
    )
    if settlement is None:
        settlement = LaundryVendorSettlement(
            hotel_id=hotel_id, vendor_id=vendor_id, period_start=period_start, period_end=period_end
        )
        db.add(settlement)

    settlement.paid = paid
    settlement.paid_at = datetime.now(timezone.utc) if paid else None
    settlement.paid_by_user_id = actor_user_id if paid else None
    if notes is not None:
        settlement.notes = notes
    db.flush()
    return settlement


def _get_vendor(db: Session, *, hotel_id: int, vendor_id: int) -> LaundryVendor:
    vendor = (
        db.query(LaundryVendor)
        .filter(LaundryVendor.id == vendor_id, LaundryVendor.hotel_id == hotel_id, LaundryVendor.deleted_at.is_(None))
        .one_or_none()
    )
    if vendor is None:
        raise LaundryVendorError("No se encontró el proveedor de lavandería.")
    return vendor


def _default_currency(db: Session, *, hotel_id: int) -> str:
    hotel = db.query(HotelConfiguration).filter(HotelConfiguration.id == hotel_id).one_or_none()
    return hotel.default_currency if hotel is not None and hotel.default_currency else "ARS"
