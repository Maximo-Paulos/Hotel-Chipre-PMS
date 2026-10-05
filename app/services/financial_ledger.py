"""Canonical read helpers for reservation financial state.

``Reservation.amount_paid`` remains a materialized compatibility/cache column for
legacy consumers. Confirmed transactions are the financial source of truth for
new reads and validations.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Iterable

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.models.operations import BillingAdjustment
from app.models.reservation import Reservation
from app.models.transaction import Transaction, TransactionStatusEnum, TransactionTypeEnum


def signed_transaction_amount(transaction: Transaction) -> Decimal:
    """Return a completed-ledger transaction with refunds represented as negative."""
    amount = Decimal(str(transaction.amount or 0))
    if transaction.transaction_type == TransactionTypeEnum.REFUND:
        return -amount
    return amount


def completed_paid_amounts_by_reservation(
    db: Session,
    hotel_id: int,
    reservation_ids: Iterable[int] | None = None,
) -> dict[int, Decimal]:
    """Aggregate confirmed payments once, optionally for a bounded reservation set."""
    signed_amount = case(
        (Transaction.transaction_type == TransactionTypeEnum.REFUND, -Transaction.amount),
        else_=Transaction.amount,
    )
    query = db.query(
        Transaction.reservation_id,
        func.sum(signed_amount),
    ).filter(
        Transaction.hotel_id == hotel_id,
        Transaction.status == TransactionStatusEnum.COMPLETED,
    )
    if reservation_ids is not None:
        ids = tuple(reservation_ids)
        if not ids:
            return {}
        query = query.filter(Transaction.reservation_id.in_(ids))

    rows = query.group_by(Transaction.reservation_id).all()
    return {
        reservation_id: Decimal(str(amount or 0)).quantize(Decimal("0.01"))
        for reservation_id, amount in rows
    }


def completed_paid_amount(db: Session, hotel_id: int, reservation_id: int) -> Decimal:
    """Return confirmed net payments for one reservation."""
    return completed_paid_amounts_by_reservation(db, hotel_id, [reservation_id]).get(
        reservation_id,
        Decimal("0.00"),
    )


def external_paid_balance_credit(reservation) -> Decimal:
    """Return an external OTA amount only when its unit matches the booking.

    Historical rows without an explicit external currency are interpreted in
    their reservation currency; the migration also backfills confirmed legacy
    credits so report queries have a stable source value.
    """
    if not bool(getattr(reservation, "external_paid_confirmed", False)):
        return Decimal("0.00")
    amount = Decimal(str(getattr(reservation, "external_paid_amount", 0) or 0))
    if amount <= 0:
        return Decimal("0.00")
    reservation_currency = str(getattr(reservation, "currency_code", None) or "ARS").strip().upper()
    paid_currency = str(
        getattr(reservation, "external_paid_currency", None) or reservation_currency
    ).strip().upper()
    if paid_currency != reservation_currency:
        return Decimal("0.00")
    return amount.quantize(Decimal("0.01"))


def paid_amounts_by_reservation(
    db: Session,
    hotel_id: int,
    reservation_ids: Iterable[int] | None = None,
) -> dict[int, Decimal]:
    """Bulk guest-balance credits: confirmed OTA amounts plus local payments.

    Legacy non-OTA caches are retained only when there is no transaction
    history. External OTA credits are deliberately excluded from the cash and
    hotel-receipt reports, which use ``completed_paid_amounts_by_reservation``.
    """
    ids = tuple(reservation_ids) if reservation_ids is not None else None
    if ids == ():
        return {}
    completed = completed_paid_amounts_by_reservation(db, hotel_id, ids)
    reservations_query = db.query(
        Reservation.id,
        Reservation.source_provider_code,
        Reservation.external_id,
        Reservation.amount_paid,
        Reservation.external_paid_amount,
        Reservation.external_paid_currency,
        Reservation.external_paid_confirmed,
        Reservation.currency_code,
    ).filter(Reservation.hotel_id == hotel_id)
    transactions_query = db.query(Transaction.reservation_id).filter(
        Transaction.hotel_id == hotel_id
    )
    if ids is not None:
        reservations_query = reservations_query.filter(Reservation.id.in_(ids))
        transactions_query = transactions_query.filter(Transaction.reservation_id.in_(ids))
    rows = reservations_query.all()
    has_transactions = {reservation_id for (reservation_id,) in transactions_query.distinct().all()}

    result: dict[int, Decimal] = {}
    for row in rows:
        ledger_paid = completed.get(row.id, Decimal("0.00"))
        is_ota_reservation = bool(row.source_provider_code or row.external_id)
        if is_ota_reservation:
            external_paid = external_paid_balance_credit(row)
            result[row.id] = (ledger_paid + external_paid).quantize(Decimal("0.01"))
        elif row.id in has_transactions:
            result[row.id] = ledger_paid
        else:
            result[row.id] = Decimal(str(row.amount_paid or 0)).quantize(Decimal("0.01"))
    return result


def reconciled_paid_amounts_by_reservation(
    db: Session,
    hotel_id: int,
    reservation_ids: Iterable[int] | None = None,
) -> dict[int, Decimal]:
    """Return evidenced paid totals without legacy-cache fallback.

    Completed local ledger transactions are authoritative. For OTA reservations,
    explicitly confirmed external credits are added; inferred/unconfirmed
    historical amounts and ``amount_paid`` compatibility caches are excluded so
    reconciliation can surface records that need operator review.
    """
    ids = tuple(reservation_ids) if reservation_ids is not None else None
    totals = completed_paid_amounts_by_reservation(db, hotel_id, ids)
    query = db.query(
        Reservation.id,
        Reservation.source_provider_code,
        Reservation.external_id,
        Reservation.external_paid_amount,
        Reservation.external_paid_currency,
        Reservation.external_paid_confirmed,
        Reservation.currency_code,
    ).filter(Reservation.hotel_id == hotel_id)
    if ids is not None:
        if not ids:
            return {}
        query = query.filter(Reservation.id.in_(ids))
    for row in query.all():
        if (
            (row.source_provider_code or row.external_id)
            and row.external_paid_confirmed
        ):
            totals[row.id] = (
                totals.get(row.id, Decimal("0.00")) + external_paid_balance_credit(row)
            ).quantize(Decimal("0.01"))
    return totals


def paid_amount_with_legacy_fallback(db: Session, hotel_id: int, reservation) -> Decimal:
    """Return confirmed OTA credits plus the net completed in-house ledger.

    OTA payments are a reservation-level external credit rather than hotel cash
    transactions. Legacy non-OTA rows still use ``amount_paid`` only when no
    transaction history exists.
    """
    completed_ledger = completed_paid_amount(db, hotel_id, reservation.id)
    is_ota_reservation = bool(
        getattr(reservation, "source_provider_code", None)
        or getattr(reservation, "external_id", None)
    )
    if is_ota_reservation:
        external_paid = external_paid_balance_credit(reservation)
        return (completed_ledger + external_paid).quantize(Decimal("0.01"))

    has_transactions = db.query(Transaction.id).filter(
        Transaction.hotel_id == hotel_id,
        Transaction.reservation_id == reservation.id,
    ).first()
    if has_transactions is None:
        return Decimal(str(reservation.amount_paid or 0)).quantize(Decimal("0.01"))
    return completed_ledger


def has_payment_history_for_cancellation(db: Session, hotel_id: int, reservation) -> bool:
    """Whether cancellation needs the paid-reservation control.

    Completed ledger rows include fully refunded reservations, which still
    need an accountable cancellation. Imported legacy reservations may have a
    materialized ``amount_paid`` but no transaction rows, so retain the
    compatibility fallback for those records.
    """
    if bool(getattr(reservation, "external_paid_ever_confirmed", False)) or Decimal(
        str(getattr(reservation, "external_paid_amount", 0) or 0)
    ) > Decimal("0.00"):
        return True

    completed_payment = db.query(Transaction.id).filter(
        Transaction.hotel_id == hotel_id,
        Transaction.reservation_id == reservation.id,
        Transaction.status == TransactionStatusEnum.COMPLETED,
    ).first()
    if completed_payment is not None:
        return True
    return paid_amount_with_legacy_fallback(db, hotel_id, reservation) > Decimal("0.00")


def billing_adjustment_totals_by_reservation(
    db: Session,
    hotel_id: int,
    reservation_ids: Iterable[int] | None = None,
) -> dict[int, Decimal]:
    """Aggregate billing adjustments (consumption/extra charges) once per reservation."""
    query = db.query(BillingAdjustment).filter(BillingAdjustment.hotel_id == hotel_id)
    if reservation_ids is not None:
        ids = tuple(reservation_ids)
        if not ids:
            return {}
        query = query.filter(BillingAdjustment.reservation_id.in_(ids))

    totals: dict[int, Decimal] = {}
    for row in query.all():
        totals[row.reservation_id] = totals.get(row.reservation_id, Decimal("0.00")) + Decimal(
            str(row.total_amount or 0)
        )
    return {reservation_id: amount.quantize(Decimal("0.01")) for reservation_id, amount in totals.items()}


def operational_balance_due(
    db: Session,
    *,
    hotel_id: int,
    reservation,
    paid_amount: Decimal | None = None,
) -> Decimal:
    """Compute the collectible balance from confirmed transactions and adjustments."""
    adjustment_total = billing_adjustment_totals_by_reservation(
        db, hotel_id, [reservation.id]
    ).get(reservation.id, Decimal("0.00"))
    paid = paid_amount if paid_amount is not None else paid_amount_with_legacy_fallback(db, hotel_id, reservation)
    return max(
        Decimal("0.00"),
        Decimal(str(reservation.total_amount or 0)) + adjustment_total - paid,
    ).quantize(Decimal("0.01"))
