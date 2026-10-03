"""Atomic idempotent collection and explicit allocations for reservation groups."""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.cash_register import CashMovement, CashMovementTypeEnum
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.reservation_group import ReservationGroup
from app.models.reservation_group_payment import (
    ReservationGroupPaymentAllocation,
    ReservationGroupPaymentBatch,
)
from app.models.transaction import PaymentMethodEnum, TransactionTypeEnum
from app.schemas.reservation_group_payment import (
    ReservationGroupPaymentCreate,
    ReservationGroupPaymentRead,
)
from app.schemas.transaction import PaymentRequest
from app.services.payment_service import (
    MANUAL_REFERENCE_METHODS,
    PaymentError,
    PaymentNotFoundError,
    calculate_payment_surcharge,
    process_payment,
)

CENT = Decimal("0.01")


def _canonical_hash(group_id: int, payload: ReservationGroupPaymentCreate, currency: str) -> str:
    normalized = {
        "group_id": group_id,
        "received_amount": str(payload.received_amount.quantize(CENT)),
        "currency": currency,
        "payment_method": payload.payment_method.value,
        "manual_reference": payload.manual_reference,
        "description": payload.description,
        "allocations": [
            {
                "reservation_id": item.reservation_id,
                "received_amount": str(item.received_amount.quantize(CENT)),
                "company_night_charge_ids": sorted(item.company_night_charge_ids),
            }
            for item in sorted(payload.allocations, key=lambda item: item.reservation_id)
        ],
    }
    serialized = json.dumps(normalized, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _read_batch(db: Session, batch: ReservationGroupPaymentBatch) -> dict:
    allocations = (
        db.query(ReservationGroupPaymentAllocation)
        .filter(
            ReservationGroupPaymentAllocation.hotel_id == batch.hotel_id,
            ReservationGroupPaymentAllocation.batch_id == batch.id,
        )
        .order_by(ReservationGroupPaymentAllocation.reservation_id.asc())
        .all()
    )
    return {
        "id": batch.id,
        "group_id": batch.group_id,
        "received_amount": batch.received_amount,
        "currency": batch.currency,
        "payment_method": batch.payment_method,
        "manual_reference": batch.manual_reference,
        "description": batch.description,
        "created_by_user_id": batch.created_by_user_id,
        "created_at": batch.created_at,
        "allocations": [
            {
                "reservation_id": item.reservation_id,
                "transaction_id": item.transaction_id,
                "received_amount": item.received_amount,
            }
            for item in allocations
        ],
    }


def get_group_payment_batch(
    db: Session,
    *,
    hotel_id: int,
    batch_id: int,
) -> dict | None:
    batch = (
        db.query(ReservationGroupPaymentBatch)
        .filter(
            ReservationGroupPaymentBatch.hotel_id == hotel_id,
            ReservationGroupPaymentBatch.id == batch_id,
        )
        .one_or_none()
    )
    return _read_batch(db, batch) if batch else None


def create_reservation_group_payment(
    db: Session,
    *,
    hotel_id: int,
    group_id: int,
    payload: ReservationGroupPaymentCreate,
    idempotency_key: str,
    actor_user_id: int,
) -> tuple[dict, bool]:
    """Create one batch and its child payment transactions as one DB operation.

    Returns ``(batch, replayed)``. The transaction ledger and cash register keep
    one row per child reservation, while the batch id gives reports a stable way
    to present the operator-entered collection once.
    """
    group = (
        db.query(ReservationGroup)
        .filter(ReservationGroup.hotel_id == hotel_id, ReservationGroup.id == group_id)
        .populate_existing()
        .with_for_update(of=ReservationGroup)
        .one_or_none()
    )
    if group is None:
        raise PaymentNotFoundError("No se encontró el grupo de reservas.")

    child_rows = (
        db.query(Reservation)
        .filter(
            Reservation.hotel_id == hotel_id,
            Reservation.group_id == group.id,
            Reservation.deleted_at.is_(None),
        )
        .order_by(Reservation.id.asc())
        .all()
    )
    children_by_id = {item.id: item for item in child_rows}
    allocation_ids = {item.reservation_id for item in payload.allocations}
    if not allocation_ids.issubset(children_by_id):
        raise PaymentError("Todas las asignaciones deben corresponder a reservas de este grupo y hotel.")

    child_currencies = {str(item.currency_code or "ARS").strip().upper() for item in child_rows if item.id in allocation_ids}
    if len(child_currencies) != 1:
        raise PaymentError("Las reservas seleccionadas deben usar la misma moneda para un cobro grupal.")
    reservation_currency = next(iter(child_currencies))
    payment_currency = (payload.currency or reservation_currency).strip().upper()
    digest = _canonical_hash(group.id, payload, payment_currency)

    existing = (
        db.query(ReservationGroupPaymentBatch)
        .filter(
            ReservationGroupPaymentBatch.hotel_id == hotel_id,
            ReservationGroupPaymentBatch.idempotency_key == idempotency_key,
        )
        .one_or_none()
    )
    if existing is not None:
        if existing.request_hash != digest:
            raise PaymentError("La clave de idempotencia ya fue usada para otro cobro grupal.")
        return _read_batch(db, existing), True

    if any(
        item.status in {ReservationStatusEnum.CANCELLED, ReservationStatusEnum.CHECKED_OUT}
        for item in child_rows
        if item.id in allocation_ids
    ):
        raise PaymentError("No se puede cobrar una reserva cancelada o finalizada.")

    if payload.payment_method in MANUAL_REFERENCE_METHODS and not payload.manual_reference:
        label = "número de operación bancaria" if payload.payment_method == PaymentMethodEnum.BANK_TRANSFER else "cupón verificado del posnet"
        raise PaymentError(f"Ingresá el {label} antes de registrar el pago.")
    if payload.payment_method not in MANUAL_REFERENCE_METHODS and payload.manual_reference:
        raise PaymentError("El comprobante solo se acepta para cobros presenciales con verificación manual.")

    batch = ReservationGroupPaymentBatch(
        hotel_id=hotel_id,
        group_id=group.id,
        idempotency_key=idempotency_key,
        request_hash=digest,
        received_amount=payload.received_amount.quantize(CENT),
        currency=payment_currency,
        payment_method=payload.payment_method,
        manual_reference=payload.manual_reference,
        description=payload.description,
        created_by_user_id=actor_user_id,
    )
    try:
        with db.begin_nested():
            db.add(batch)
            db.flush()
    except IntegrityError:
        existing = (
            db.query(ReservationGroupPaymentBatch)
            .filter(
                ReservationGroupPaymentBatch.hotel_id == hotel_id,
                ReservationGroupPaymentBatch.idempotency_key == idempotency_key,
            )
            .one_or_none()
        )
        if existing is not None and existing.request_hash == digest:
            return _read_batch(db, existing), True
        if existing is not None:
            raise PaymentError("La clave de idempotencia ya fue usada para otro cobro grupal.")
        raise

    surcharge_info = calculate_payment_surcharge(
        db,
        hotel_id=hotel_id,
        payment_method=payload.payment_method,
        base_amount=payload.received_amount,
    )
    total_surcharge = Decimal(str(surcharge_info["surcharge_amount"])).quantize(CENT)
    total_cents = int((payload.received_amount * 100).to_integral_value())
    surcharge_cents = int((total_surcharge * 100).to_integral_value())
    allocations = list(payload.allocations)
    allocated_fee_cents = 0
    created_transactions = []
    for index, allocation in enumerate(allocations):
        tx_description = (
            f"Cobro grupal #{batch.id} · reserva #{allocation.reservation_id}"
            + (f" · {payload.description}" if payload.description else "")
        )
        payment = PaymentRequest(
            reservation_id=allocation.reservation_id,
            amount=float(allocation.received_amount),
            payment_method=payload.payment_method,
            transaction_type=TransactionTypeEnum.PARTIAL_PAYMENT,
            currency=payment_currency,
            description=tx_description[:1000],
            manual_reference=payload.manual_reference if index == 0 else None,
            company_night_charge_ids=allocation.company_night_charge_ids,
        )
        transaction = process_payment(
            db,
            payment,
            hotel_id=hotel_id,
            actor_user_id=actor_user_id,
            idempotency_key=f"group-payment-{batch.id}-{allocation.reservation_id}",
            manual_confirmation=payload.payment_method in MANUAL_REFERENCE_METHODS,
            apply_surcharge=False,
        )
        if index == len(allocations) - 1:
            fee_cents = surcharge_cents - allocated_fee_cents
        else:
            amount_cents = int((allocation.received_amount * 100).to_integral_value())
            fee_cents = int(
                (Decimal(surcharge_cents * amount_cents) / Decimal(total_cents)).quantize(
                    Decimal("1"), rounding=ROUND_HALF_UP
                )
            )
            allocated_fee_cents += fee_cents
        fee_amount = Decimal(fee_cents) / Decimal(100)
        transaction.group_payment_batch_id = batch.id
        transaction.fee_amount = fee_amount
        transaction.gross_amount = (Decimal(str(transaction.tender_amount or allocation.received_amount)) + fee_amount).quantize(CENT)
        db.add(transaction)
        db.flush()

        if payload.payment_method == PaymentMethodEnum.CASH and transaction.status.value == "completed":
            movement = (
                db.query(CashMovement)
                .filter(
                    CashMovement.hotel_id == hotel_id,
                    CashMovement.transaction_id == transaction.id,
                    CashMovement.movement_type == CashMovementTypeEnum.INCOME,
                )
                .one_or_none()
            )
            if movement is None:
                raise PaymentError("No se pudo conciliar una asignación del cobro grupal en caja.")
            movement.amount = transaction.gross_amount
            movement.description = f"Cobro grupal #{batch.id} ({len(allocations)} reservas)"
            db.add(movement)

        db.add(
            ReservationGroupPaymentAllocation(
                hotel_id=hotel_id,
                batch_id=batch.id,
                reservation_id=allocation.reservation_id,
                transaction_id=transaction.id,
                received_amount=allocation.received_amount.quantize(CENT),
            )
        )
        created_transactions.append(transaction)

    db.flush()
    return _read_batch(db, batch), False
