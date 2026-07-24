"""Canonical read helpers for reservation financial state.

``Reservation.amount_paid`` remains a materialized compatibility/cache column for
legacy consumers. Confirmed transactions are the financial source of truth for
new reads and validations.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Iterable

from sqlalchemy.orm import Session

from app.models.operations import BillingAdjustment
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
    query = db.query(Transaction).filter(
        Transaction.hotel_id == hotel_id,
        Transaction.status == TransactionStatusEnum.COMPLETED,
    )
    if reservation_ids is not None:
        ids = tuple(reservation_ids)
        if not ids:
            return {}
        query = query.filter(Transaction.reservation_id.in_(ids))

    totals: dict[int, Decimal] = {}
    for transaction in query.all():
        totals[transaction.reservation_id] = (
            totals.get(transaction.reservation_id, Decimal("0.00"))
            + signed_transaction_amount(transaction)
        )
    return {reservation_id: amount.quantize(Decimal("0.01")) for reservation_id, amount in totals.items()}


def completed_paid_amount(db: Session, hotel_id: int, reservation_id: int) -> Decimal:
    """Return confirmed net payments for one reservation."""
    return completed_paid_amounts_by_reservation(db, hotel_id, [reservation_id]).get(
        reservation_id,
        Decimal("0.00"),
    )


def paid_amount_with_legacy_fallback(db: Session, hotel_id: int, reservation) -> Decimal:
    """Read the ledger, falling back only for imported rows with no transactions."""
    has_transactions = db.query(Transaction.id).filter(
        Transaction.hotel_id == hotel_id,
        Transaction.reservation_id == reservation.id,
    ).first()
    if has_transactions is None:
        return Decimal(str(reservation.amount_paid or 0)).quantize(Decimal("0.01"))
    return completed_paid_amount(db, hotel_id, reservation.id)


def operational_balance_due(
    db: Session,
    *,
    hotel_id: int,
    reservation,
    paid_amount: Decimal | None = None,
) -> Decimal:
    """Compute the collectible balance from confirmed transactions and adjustments."""
    adjustment_total = sum(
        (Decimal(str(row.total_amount or 0)) for row in db.query(BillingAdjustment).filter(
            BillingAdjustment.hotel_id == hotel_id,
            BillingAdjustment.reservation_id == reservation.id,
        ).all()),
        Decimal("0.00"),
    )
    paid = paid_amount if paid_amount is not None else paid_amount_with_legacy_fallback(db, hotel_id, reservation)
    return max(
        Decimal("0.00"),
        Decimal(str(reservation.total_amount or 0)) + adjustment_total - paid,
    ).quantize(Decimal("0.01"))
