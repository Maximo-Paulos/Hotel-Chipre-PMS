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
from app.models.laundry_discrepancy import LaundryDiscrepancyAction, LaundryRemitoDiscrepancy
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
from app.services.timezones import hotel_business_now, hotel_today, utc_naive

DIRECTIONS = {"outbound", "inbound"}
QUARTER_MONTHS = {1: (1, 3), 2: (4, 6), 3: (7, 9), 4: (10, 12)}


class LaundryVendorError(ValueError):
    """Raised when a laundry vendor/remito operation is invalid."""


class DuplicateLaundryRemitoError(LaundryVendorError):
    """The vendor already has a remito with this number and direction."""


class LaundryDiscrepancyNotFound(LaundryVendorError):
    """A discrepancy does not exist in the requested hotel tenant."""


class LaundryDiscrepancyConflict(LaundryVendorError):
    """A discrepancy action conflicts with its state or an idempotency key."""


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
    effective_from = effective_from or hotel_today(db, hotel_id)
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
    """Record confirmed transfers and keep remito discrepancies out of stock.

    outbound: house_location -> vendor_location (dirty linen leaves the hotel)
    inbound:  vendor_location -> house_location (clean linen comes back).

    Only the quantity that matches the vendor's recorded custody moves as an
    ordinary transfer. Any excess or declared shortage becomes a separate
    discrepancy row; it does not create or remove an owned-stock movement.
    Any failure rolls back the whole remito and its movements.
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

    item_ids = sorted({line["linen_item_id"] for line in lines})
    effective_prices = (
        db.query(LaundryVendorPrice)
        .filter(
            LaundryVendorPrice.hotel_id == hotel_id,
            LaundryVendorPrice.vendor_id == vendor_id,
            LaundryVendorPrice.linen_item_id.in_(item_ids),
            LaundryVendorPrice.effective_from <= remito_date.date(),
        )
        .order_by(
            LaundryVendorPrice.linen_item_id.asc(),
            LaundryVendorPrice.effective_from.desc(),
            LaundryVendorPrice.id.desc(),
        )
        .all()
    ) if item_ids else []
    price_by_item = {}
    for price in effective_prices:
        price_by_item.setdefault(price.linen_item_id, price)
    if direction == "outbound":
        missing_price_item_ids = [item_id for item_id in item_ids if item_id not in price_by_item]
        if missing_price_item_ids:
            missing_names = [
                linen_service.get_linen_item(db, hotel_id=hotel_id, item_id=item_id).name
                for item_id in missing_price_item_ids
            ]
            formatted_names = ", ".join(f"«{name}»" for name in missing_names)
            db.rollback()
            raise LaundryVendorError(
                "Configurá un precio vigente por unidad para cada artículo "
                f"({formatted_names}) antes de registrar el retiro al lavadero."
            )

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
            created_at=utc_naive(hotel_business_now(db, hotel_id)),
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
            ledger_available = linen_service.current_stock(
                db, hotel_id=hotel_id, item_id=linen_item_id, location_id=source_location_id
            )
            received_quantity = quantity
            excess_quantity = Decimal("0.00")
            if direction == "inbound":
                if missing_quantity > 0 and quantity > ledger_available:
                    raise LaundryVendorError(
                        "El mismo artículo no puede tener faltante y excedente en un único remito."
                    )
                if quantity > ledger_available:
                    excess_quantity = quantity - ledger_available
                    received_quantity = ledger_available
                if excess_quantity > 0 and reconciliation_warnings is not None:
                    reconciliation_warnings.append(
                        f"Excedente de {excess_quantity} de «{item.name}» pendiente de aprobación e identificación."
                    )
                if missing_quantity > 0 and reconciliation_warnings is not None:
                    reconciliation_warnings.append(
                        f"Faltante de {missing_quantity} de «{item.name}» pendiente de revisión."
                    )
            source_quantity = received_quantity if direction == "inbound" else quantity
            if source_quantity > ledger_available:
                location = linen_service.get_location(db, hotel_id=hotel_id, location_id=source_location_id)
                diagnosis = "Verificá el conteo inicial de la ubicación."
                raise LaundryVendorError(
                    f"No hay suficiente «{item.name}» en la ubicación de origen «{location.name}»: "
                    f"hay {ledger_available}, se necesitan {source_quantity}. {diagnosis}"
                )

            if source_quantity > 0:
                movement_reason = f"Laundry remito {remito_number} ({direction})"
                linen_service.register_movement(
                    db,
                    hotel_id=hotel_id,
                    item_id=linen_item_id,
                    location_id=source_location_id,
                    movement_type="out",
                    quantity=source_quantity,
                    reason=movement_reason,
                    created_by_user_id=actor_user_id,
                )
                linen_service.register_movement(
                    db,
                    hotel_id=hotel_id,
                    item_id=linen_item_id,
                    location_id=dest_location_id,
                    movement_type="in",
                    quantity=source_quantity,
                    reason=movement_reason,
                    created_by_user_id=actor_user_id,
                )

            price = price_by_item.get(linen_item_id)
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
                # Keep the existing neutral follow-up audit trail while the
                # discrepancy workflow separately governs stock/custody.
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
            if excess_quantity > 0:
                discrepancy = LaundryRemitoDiscrepancy(
                    hotel_id=hotel_id,
                    remito_id=remito.id,
                    remito_line_id=line_record.id,
                    vendor_id=vendor_id,
                    linen_item_id=linen_item_id,
                    discrepancy_type="excess_return",
                    quantity=excess_quantity,
                    remaining_quantity=excess_quantity,
                    source_location_id=house_location_id,
                    custody_location_id=house_location_id,
                    status="pending_approval",
                    created_by_user_id=actor_user_id,
                    created_at=utc_naive(hotel_business_now(db, hotel_id)),
                )
                db.add(discrepancy)
                db.flush()
                db.add(
                    SecurityAuditLog(
                        hotel_id=hotel_id,
                        user_id=actor_user_id,
                        action="laundry.discrepancy.created",
                        resource_type="laundry_remito_discrepancy",
                        resource_id=str(discrepancy.id),
                        details=json.dumps(
                            {
                                "remito_id": remito.id,
                                "remito_line_id": line_record.id,
                                "type": "excess_return",
                                "quantity": str(excess_quantity),
                                "custody_location_id": house_location_id,
                                "status": discrepancy.status,
                            },
                            sort_keys=True,
                        ),
                    )
                )
            if direction == "inbound" and source_quantity > 0:
                _match_shortage_receipt(
                    db,
                    hotel_id=hotel_id,
                    vendor_id=vendor_id,
                    item_id=linen_item_id,
                    remito=remito,
                    line=line_record,
                    quantity=source_quantity,
                    actor_user_id=actor_user_id,
                )
            if missing_quantity > 0:
                disputed_quantity = (
                    db.query(func.coalesce(func.sum(LaundryRemitoDiscrepancy.remaining_quantity), 0))
                    .filter(
                        LaundryRemitoDiscrepancy.hotel_id == hotel_id,
                        LaundryRemitoDiscrepancy.vendor_id == vendor_id,
                        LaundryRemitoDiscrepancy.linen_item_id == linen_item_id,
                        LaundryRemitoDiscrepancy.discrepancy_type == "short_return",
                        LaundryRemitoDiscrepancy.status != "resolved",
                    )
                    .scalar()
                )
                still_recorded_at_vendor = linen_service.current_stock(
                    db,
                    hotel_id=hotel_id,
                    item_id=linen_item_id,
                    location_id=vendor.linen_location_id,
                )
                unallocated_vendor_quantity = max(
                    Decimal(still_recorded_at_vendor) - Decimal(disputed_quantity or 0),
                    Decimal("0.00"),
                )
                if missing_quantity > unallocated_vendor_quantity:
                    raise LaundryVendorError(
                        "El faltante supera la cantidad disponible del lavadero no vinculada a otra discrepancia. "
                        "Registrá el remito de salida correspondiente o conciliá el faltante abierto."
                    )
                discrepancy = LaundryRemitoDiscrepancy(
                    hotel_id=hotel_id,
                    remito_id=remito.id,
                    remito_line_id=line_record.id,
                    vendor_id=vendor_id,
                    linen_item_id=linen_item_id,
                    discrepancy_type="short_return",
                    quantity=missing_quantity,
                    remaining_quantity=missing_quantity,
                    source_location_id=vendor.linen_location_id,
                    custody_location_id=None,
                    status="pending_review",
                    created_by_user_id=actor_user_id,
                    created_at=utc_naive(hotel_business_now(db, hotel_id)),
                )
                db.add(discrepancy)
                db.flush()
                db.add(
                    SecurityAuditLog(
                        hotel_id=hotel_id,
                        user_id=actor_user_id,
                        action="laundry.discrepancy.created",
                        resource_type="laundry_remito_discrepancy",
                        resource_id=str(discrepancy.id),
                        details=json.dumps(
                            {
                                "remito_id": remito.id,
                                "remito_line_id": line_record.id,
                                "type": "short_return",
                                "quantity": str(missing_quantity),
                                "custody_location_id": None,
                                "status": discrepancy.status,
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


def list_discrepancies(
    db: Session,
    *,
    hotel_id: int,
    status: str | None = None,
    discrepancy_type: str | None = None,
) -> list[LaundryRemitoDiscrepancy]:
    query = db.query(LaundryRemitoDiscrepancy).filter(LaundryRemitoDiscrepancy.hotel_id == hotel_id)
    if status is not None:
        query = query.filter(LaundryRemitoDiscrepancy.status == status)
    if discrepancy_type is not None:
        query = query.filter(LaundryRemitoDiscrepancy.discrepancy_type == discrepancy_type)
    return query.order_by(LaundryRemitoDiscrepancy.created_at.desc(), LaundryRemitoDiscrepancy.id.desc()).all()


def _get_discrepancy(db: Session, *, hotel_id: int, discrepancy_id: int) -> LaundryRemitoDiscrepancy:
    row = (
        db.query(LaundryRemitoDiscrepancy)
        .filter(
            LaundryRemitoDiscrepancy.hotel_id == hotel_id,
            LaundryRemitoDiscrepancy.id == discrepancy_id,
        )
        .with_for_update(of=LaundryRemitoDiscrepancy)
        .one_or_none()
    )
    if row is None:
        raise LaundryDiscrepancyNotFound("No se encontró la discrepancia de lavandería.")
    return row


def _validate_action_input(*, reason: str, idempotency_key: str) -> tuple[str, str]:
    normalized_reason = (reason or "").strip()
    normalized_key = (idempotency_key or "").strip()
    if not normalized_reason:
        raise LaundryVendorError("El motivo es obligatorio.")
    if len(normalized_reason) > 500:
        raise LaundryVendorError("El motivo no puede superar 500 caracteres.")
    if not normalized_key or len(normalized_key) > 128 or any(ord(char) < 33 for char in normalized_key):
        raise LaundryVendorError("El Idempotency-Key debe tener entre 1 y 128 caracteres visibles.")
    return normalized_reason, normalized_key


def _action_replay(
    db: Session,
    *,
    hotel_id: int,
    discrepancy_id: int,
    actor_user_id: int | None,
    action_type: str,
    reason: str,
    idempotency_key: str,
    resolution_code: str | None = None,
    resolution_amount: Decimal | None = None,
    resolution_currency_code: str | None = None,
    quantity: Decimal | None = None,
    remito_id: int | None = None,
    remito_line_id: int | None = None,
) -> LaundryRemitoDiscrepancy | None:
    existing = (
        db.query(LaundryDiscrepancyAction)
        .filter(
            LaundryDiscrepancyAction.hotel_id == hotel_id,
            LaundryDiscrepancyAction.idempotency_key == idempotency_key,
        )
        .one_or_none()
    )
    if existing is None:
        return None
    expected = (
        existing.discrepancy_id == discrepancy_id,
        existing.actor_user_id == actor_user_id,
        existing.action_type == action_type,
        existing.reason == reason,
        existing.resolution_code == resolution_code,
        existing.resolution_amount == resolution_amount,
        existing.resolution_currency_code == resolution_currency_code,
        existing.quantity == quantity,
        existing.remito_id == remito_id,
        existing.remito_line_id == remito_line_id,
    )
    if not all(expected):
        raise LaundryDiscrepancyConflict("El Idempotency-Key ya fue usado con otra acción o datos.")
    return _get_discrepancy(db, hotel_id=hotel_id, discrepancy_id=discrepancy_id)


def _audit_discrepancy(
    db: Session,
    *,
    hotel_id: int,
    discrepancy: LaundryRemitoDiscrepancy,
    actor_user_id: int | None,
    action: str,
    details: dict,
) -> None:
    db.add(
        SecurityAuditLog(
            hotel_id=hotel_id,
            user_id=actor_user_id,
            action=action,
            resource_type="laundry_remito_discrepancy",
            resource_id=str(discrepancy.id),
            details=json.dumps(details, sort_keys=True),
            created_at=utc_naive(hotel_business_now(db, hotel_id)),
        )
    )


def _record_discrepancy_action(
    db: Session,
    *,
    row: LaundryRemitoDiscrepancy,
    actor_user_id: int | None,
    action_type: str,
    action_name: str,
    reason: str,
    idempotency_key: str,
    resolution_code: str | None = None,
    resolution_amount: Decimal | None = None,
    resolution_currency_code: str | None = None,
    quantity: Decimal | None = None,
    remito_id: int | None = None,
    remito_line_id: int | None = None,
) -> None:
    db.add(
        LaundryDiscrepancyAction(
            hotel_id=row.hotel_id,
            discrepancy_id=row.id,
            action_type=action_type,
            idempotency_key=idempotency_key,
            reason=reason,
            quantity=quantity,
            resolution_code=resolution_code,
            resolution_amount=resolution_amount,
            resolution_currency_code=resolution_currency_code,
            remito_id=remito_id,
            remito_line_id=remito_line_id,
            actor_user_id=actor_user_id,
            created_at=utc_naive(hotel_business_now(db, row.hotel_id)),
        )
    )
    db.flush()
    _audit_discrepancy(
        db,
        hotel_id=row.hotel_id,
        discrepancy=row,
        actor_user_id=actor_user_id,
        action=action_name,
        details={
            "type": row.discrepancy_type,
            "quantity": str(quantity if quantity is not None else row.remaining_quantity),
            "status": row.status,
            "resolution": resolution_code,
            "amount": str(resolution_amount) if resolution_amount is not None else None,
            "currency": resolution_currency_code,
            "remito_id": remito_id,
            "remito_line_id": remito_line_id,
            "reason": reason,
        },
    )


def approve_discrepancy(
    db: Session,
    *,
    hotel_id: int,
    discrepancy_id: int,
    actor_user_id: int | None,
    reason: str,
    idempotency_key: str,
) -> LaundryRemitoDiscrepancy:
    """Authorize review without creating or removing linen stock."""
    normalized_reason, normalized_key = _validate_action_input(reason=reason, idempotency_key=idempotency_key)
    row = _get_discrepancy(db, hotel_id=hotel_id, discrepancy_id=discrepancy_id)
    replay = _action_replay(
        db,
        hotel_id=hotel_id,
        discrepancy_id=discrepancy_id,
        actor_user_id=actor_user_id,
        action_type="approval",
        reason=normalized_reason,
        idempotency_key=normalized_key,
    )
    if replay is not None:
        return replay

    expected_status = "pending_approval" if row.discrepancy_type == "excess_return" else "pending_review"
    next_status = "pending_identification" if row.discrepancy_type == "excess_return" else "pending_resolution"
    if row.status != expected_status:
        raise LaundryDiscrepancyConflict("La discrepancia ya fue revisada o no admite aprobación en su estado actual.")

    row.status = next_status
    row.reviewed_by_user_id = actor_user_id
    row.reviewed_at = utc_naive(hotel_business_now(db, hotel_id))
    row.review_reason = normalized_reason
    db.flush()
    _record_discrepancy_action(
        db,
        row=row,
        actor_user_id=actor_user_id,
        action_type="approval",
        action_name="laundry.discrepancy.approved",
        reason=normalized_reason,
        idempotency_key=normalized_key,
    )
    return row


def resolve_discrepancy(
    db: Session,
    *,
    hotel_id: int,
    discrepancy_id: int,
    actor_user_id: int | None,
    resolution_code: str,
    reason: str,
    idempotency_key: str,
    resolution_amount: Decimal | None = None,
    resolution_currency_code: str | None = None,
) -> LaundryRemitoDiscrepancy:
    """Apply an authorized owner-selected outcome to a remito discrepancy."""
    normalized_reason, normalized_key = _validate_action_input(reason=reason, idempotency_key=idempotency_key)
    normalized_resolution = (resolution_code or "").strip().lower()
    if not normalized_resolution or len(normalized_resolution) > 80:
        raise LaundryVendorError("La resolución es obligatoria y no puede superar 80 caracteres.")
    normalized_currency = (resolution_currency_code or "").strip().upper() or None
    if resolution_amount is not None and resolution_amount <= 0:
        raise LaundryVendorError("El importe del crédito debe ser mayor que cero.")
    if normalized_currency is not None and (len(normalized_currency) != 3 or not normalized_currency.isalpha()):
        raise LaundryVendorError("La moneda del crédito debe tener tres letras.")
    is_credit = normalized_resolution == "vendor_credit"
    if is_credit != (resolution_amount is not None and normalized_currency is not None):
        raise LaundryVendorError("El crédito requiere importe y moneda negociados; otras resoluciones no los aceptan.")

    row = _get_discrepancy(db, hotel_id=hotel_id, discrepancy_id=discrepancy_id)
    replay = _action_replay(
        db,
        hotel_id=hotel_id,
        discrepancy_id=discrepancy_id,
        actor_user_id=actor_user_id,
        action_type="resolution",
        reason=normalized_reason,
        idempotency_key=normalized_key,
        resolution_code=normalized_resolution,
        resolution_amount=resolution_amount,
        resolution_currency_code=normalized_currency,
        quantity=Decimal(row.quantity),
    )
    if replay is not None:
        return replay

    now = utc_naive(hotel_business_now(db, hotel_id))
    if row.discrepancy_type == "excess_return":
        if row.status != "pending_identification":
            raise LaundryDiscrepancyConflict("El excedente debe aprobarse antes de conciliarlo.")
        if normalized_resolution not in {"hotel_stock", "return_to_laundry"}:
            raise LaundryVendorError("El excedente debe asignarse al stock del hotel o marcarse para devolución.")
        if row.remaining_quantity <= 0:
            raise LaundryDiscrepancyConflict("El excedente ya fue conciliado.")
        remito = (
            db.query(LaundryRemito)
            .filter(LaundryRemito.hotel_id == hotel_id, LaundryRemito.id == row.remito_id)
            .one_or_none()
        )
        if remito is None or remito.house_location_id is None:
            raise LaundryVendorError("El remito no tiene una ubicación hotelera válida para conciliar el excedente.")
        if normalized_resolution == "hotel_stock":
            linen_service.register_movement(
                db,
                hotel_id=hotel_id,
                item_id=row.linen_item_id,
                location_id=remito.house_location_id,
                movement_type="in",
                quantity=row.remaining_quantity,
                reason=f"Excedente de lavandería confirmado como propio: {normalized_reason}",
                created_by_user_id=actor_user_id,
            )
            row.custody_location_id = remito.house_location_id
            row.remaining_quantity = Decimal("0.00")
            row.status = "resolved"
            row.resolved_by_user_id = actor_user_id
            row.resolved_at = now
        else:
            row.status = "return_to_laundry"
    else:
        if row.status not in {"pending_resolution", "pending_claim", "awaiting_replacement"}:
            raise LaundryDiscrepancyConflict("El faltante no admite otra resolución en su estado actual.")
        if row.remaining_quantity <= 0:
            raise LaundryDiscrepancyConflict("El faltante ya fue conciliado.")
        allowed = {"vendor_claim", "vendor_custody", "loss", "replacement", "vendor_credit"}
        if normalized_resolution not in allowed:
            raise LaundryVendorError("Elegí reclamo, custodia del lavadero, pérdida, reposición o crédito negociado.")
        vendor = _get_vendor(db, hotel_id=hotel_id, vendor_id=row.vendor_id)
        if normalized_resolution in {"loss", "vendor_credit"}:
            linen_service.register_movement(
                db,
                hotel_id=hotel_id,
                item_id=row.linen_item_id,
                location_id=row.source_location_id,
                movement_type="adjustment_out",
                quantity=row.remaining_quantity,
                reason=f"Faltante de lavandería: {normalized_resolution}: {normalized_reason}",
                created_by_user_id=actor_user_id,
            )
            row.remaining_quantity = Decimal("0.00")
            row.status = "resolved"
            row.custody_location_id = None
            row.resolved_by_user_id = actor_user_id
            row.resolved_at = now
        elif normalized_resolution == "vendor_custody":
            row.custody_location_id = vendor.linen_location_id
            row.remaining_quantity = Decimal("0.00")
            row.status = "resolved"
            row.resolved_by_user_id = actor_user_id
            row.resolved_at = now
        elif normalized_resolution == "vendor_claim":
            row.custody_location_id = vendor.linen_location_id
            row.status = "pending_claim"
            row.resolved_by_user_id = None
            row.resolved_at = None
        else:
            row.custody_location_id = None
            row.status = "awaiting_replacement"
            row.resolved_by_user_id = None
            row.resolved_at = None

    row.resolution_code = normalized_resolution
    row.resolution_reason = normalized_reason
    row.resolution_amount = resolution_amount if is_credit else None
    row.resolution_currency_code = normalized_currency if is_credit else None
    row.resolution_recorded_by_user_id = actor_user_id
    row.resolution_recorded_at = now
    db.flush()
    _record_discrepancy_action(
        db,
        row=row,
        actor_user_id=actor_user_id,
        action_type="resolution",
        action_name="laundry.discrepancy.resolved" if row.status == "resolved" else "laundry.discrepancy.resolution_selected",
        reason=normalized_reason,
        idempotency_key=normalized_key,
        resolution_code=normalized_resolution,
        resolution_amount=resolution_amount,
        resolution_currency_code=normalized_currency,
        quantity=row.quantity,
    )
    return row


def confirm_discrepancy_return_to_laundry(
    db: Session,
    *,
    hotel_id: int,
    discrepancy_id: int,
    actor_user_id: int | None,
    reason: str,
    idempotency_key: str,
) -> LaundryRemitoDiscrepancy:
    """Record physical handover of unowned excess back to its laundry vendor."""
    normalized_reason, normalized_key = _validate_action_input(reason=reason, idempotency_key=idempotency_key)
    row = _get_discrepancy(db, hotel_id=hotel_id, discrepancy_id=discrepancy_id)
    replay = _action_replay(
        db,
        hotel_id=hotel_id,
        discrepancy_id=discrepancy_id,
        actor_user_id=actor_user_id,
        action_type="return_to_laundry",
        reason=normalized_reason,
        idempotency_key=normalized_key,
        quantity=Decimal(row.quantity),
    )
    if replay is not None:
        return replay
    if row.discrepancy_type != "excess_return" or row.status != "return_to_laundry":
        raise LaundryDiscrepancyConflict("Solo un excedente marcado para devolución puede registrarse como entregado.")
    vendor = _get_vendor(db, hotel_id=hotel_id, vendor_id=row.vendor_id)
    row.custody_location_id = vendor.linen_location_id
    row.status = "returned_to_laundry"
    row.returned_by_user_id = actor_user_id
    row.returned_at = utc_naive(hotel_business_now(db, hotel_id))
    row.return_reason = normalized_reason
    row.remaining_quantity = Decimal("0.00")
    db.flush()
    _record_discrepancy_action(
        db,
        row=row,
        actor_user_id=actor_user_id,
        action_type="return_to_laundry",
        action_name="laundry.discrepancy.returned_to_laundry",
        reason=normalized_reason,
        idempotency_key=normalized_key,
        quantity=row.quantity,
    )
    return row


def _match_shortage_receipt(
    db: Session,
    *,
    hotel_id: int,
    vendor_id: int,
    item_id: int,
    remito: LaundryRemito,
    line: LaundryRemitoLine,
    quantity: Decimal,
    actor_user_id: int | None,
) -> None:
    """Match physical receipt quantities to open laundry claims/replacements."""
    remaining_receipt = quantity
    rows = (
        db.query(LaundryRemitoDiscrepancy)
        .filter(
            LaundryRemitoDiscrepancy.hotel_id == hotel_id,
            LaundryRemitoDiscrepancy.vendor_id == vendor_id,
            LaundryRemitoDiscrepancy.linen_item_id == item_id,
            LaundryRemitoDiscrepancy.discrepancy_type == "short_return",
            LaundryRemitoDiscrepancy.status.in_(
                {"pending_review", "pending_resolution", "pending_claim", "awaiting_replacement"}
            ),
            LaundryRemitoDiscrepancy.remaining_quantity > 0,
        )
        .order_by(LaundryRemitoDiscrepancy.created_at.asc(), LaundryRemitoDiscrepancy.id.asc())
        .with_for_update()
        .all()
    )
    for row in rows:
        if remaining_receipt <= 0:
            break
        received = min(remaining_receipt, Decimal(row.remaining_quantity)).quantize(Decimal("0.01"))
        row.remaining_quantity = (Decimal(row.remaining_quantity) - received).quantize(Decimal("0.01"))
        action_type = "claim_return" if row.status == "pending_claim" else "replacement_receipt"
        if row.remaining_quantity == 0:
            row.status = "resolved"
            row.custody_location_id = remito.house_location_id
            row.resolved_by_user_id = actor_user_id
            row.resolved_at = utc_naive(hotel_business_now(db, hotel_id))
        reason = f"Recepción de {received} mediante remito {remito.remito_number}."
        action_key = f"remito-{remito.id}-line-{line.id}-discrepancy-{row.id}"
        _record_discrepancy_action(
            db,
            row=row,
            actor_user_id=actor_user_id,
            action_type=action_type,
            action_name="laundry.discrepancy.claim_quantity_returned"
            if action_type == "claim_return"
            else "laundry.discrepancy.replacement_received",
            reason=reason,
            idempotency_key=action_key,
            resolution_code=row.resolution_code,
            quantity=received,
            remito_id=remito.id,
            remito_line_id=line.id,
        )
        remaining_receipt = (remaining_receipt - received).quantize(Decimal("0.01"))


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
        ledger_quantity = linen_service.current_stock(
            db, hotel_id=hotel_id, item_id=item_id, location_id=vendor.linen_location_id
        )
        quantity = linen_service.available_stock(
            db, hotel_id=hotel_id, item_id=item_id, location_id=vendor.linen_location_id
        )
        pending_quantity = (
            db.query(func.coalesce(func.sum(LaundryRemitoDiscrepancy.remaining_quantity), 0))
            .filter(
                LaundryRemitoDiscrepancy.hotel_id == hotel_id,
                LaundryRemitoDiscrepancy.vendor_id == vendor_id,
                LaundryRemitoDiscrepancy.linen_item_id == item_id,
                LaundryRemitoDiscrepancy.discrepancy_type == "short_return",
                LaundryRemitoDiscrepancy.status.in_(
                    {"pending_review", "pending_resolution", "pending_claim", "awaiting_replacement"}
                ),
            )
            .scalar()
        )
        balances.append(
            {
                "linen_item_id": item.id,
                "linen_item_name": item.name,
                "quantity": quantity,
                "ledger_quantity": ledger_quantity,
                "pending_shortage_quantity": Decimal(pending_quantity or 0).quantize(Decimal("0.01")),
            }
        )
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
    """Record the hotel's reconciliation status without moving money."""

    _get_vendor(db, hotel_id=hotel_id, vendor_id=vendor_id)
    quarter = (period_start.month - 1) // 3 + 1
    expected_start, period_end = _quarter_bounds(period_start.year, quarter)
    if period_start != expected_start:
        raise LaundryVendorError("El período debe comenzar el primer día de un trimestre calendario.")

    if paid:
        period_from = datetime.combine(period_start, time.min, tzinfo=timezone.utc)
        period_to = datetime.combine(period_end, time.max, tzinfo=timezone.utc)
        unpriced_quantity = (
            db.query(func.coalesce(func.sum(LaundryRemitoLine.quantity), 0))
            .join(LaundryRemito, LaundryRemito.id == LaundryRemitoLine.remito_id)
            .filter(
                LaundryRemito.hotel_id == hotel_id,
                LaundryRemito.vendor_id == vendor_id,
                LaundryRemito.direction == "outbound",
                LaundryRemito.remito_date >= period_from,
                LaundryRemito.remito_date <= period_to,
                LaundryRemitoLine.unit_price_snapshot.is_(None),
            )
            .scalar()
        )
        if Decimal(unpriced_quantity or 0) > 0:
            raise LaundryVendorError(
                "No se puede marcar como pagado: hay artículos sin precio en remitos del período. "
                "Revisá esos remitos manualmente antes de confirmar la liquidación."
            )

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
    settlement.paid_at = utc_naive(hotel_business_now(db, hotel_id)) if paid else None
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
