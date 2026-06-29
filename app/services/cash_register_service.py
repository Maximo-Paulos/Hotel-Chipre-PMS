"""Cash register service for hotel-scoped caja sessions and arqueo."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.cash_register import (
    CashCloseReport,
    CashMovement,
    CashMovementTypeEnum,
    CashSession,
    CashSessionStatusEnum,
)
from app.models.transaction import PaymentMethodEnum, Transaction, TransactionStatusEnum


class CashRegisterError(Exception):
    """Raised when a cash-register operation violates business rules."""


TWOPLACES = Decimal("0.01")


def _money(value: Decimal | int | float | str) -> Decimal:
    return Decimal(str(value)).quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def _require_open_session(db: Session, hotel_id: int, session_id: int) -> CashSession:
    session = (
        db.query(CashSession)
        .filter(
            CashSession.id == session_id,
            CashSession.hotel_id == hotel_id,
            CashSession.status == CashSessionStatusEnum.OPEN,
        )
        .one_or_none()
    )
    if session is None:
        raise CashRegisterError("Cash session is not open for this hotel")
    return session


def open_session(
    db: Session,
    *,
    hotel_id: int,
    opened_by_user_id: int | None,
    opening_balance: Decimal,
    currency_code: str = "ARS",
    notes: str | None = None,
) -> CashSession:
    """Open one hotel-scoped cash session, enforcing at most one open session."""

    existing = (
        db.query(CashSession)
        .filter(
            CashSession.hotel_id == hotel_id,
            CashSession.status == CashSessionStatusEnum.OPEN,
        )
        .one_or_none()
    )
    if existing is not None:
        raise CashRegisterError("Hotel already has an open cash session")

    session = CashSession(
        hotel_id=hotel_id,
        opened_by_user_id=opened_by_user_id,
        opening_balance=_money(opening_balance),
        currency_code=currency_code.strip().upper()[:3],
        notes=notes,
    )
    db.add(session)
    try:
        db.flush()
    except IntegrityError as exc:
        raise CashRegisterError("Hotel already has an open cash session") from exc
    return session


def add_movement(
    db: Session,
    *,
    hotel_id: int,
    session_id: int,
    recorded_by_user_id: int | None,
    movement_type: CashMovementTypeEnum,
    amount: Decimal,
    description: str | None = None,
    reservation_id: int | None = None,
    transaction_id: int | None = None,
) -> CashMovement:
    """Add an income, expense, or adjustment into an open hotel cash session."""

    session = _require_open_session(db, hotel_id, session_id)
    if _money(amount) <= 0:
        raise CashRegisterError("Cash movement amount must be positive")

    if transaction_id is not None:
        transaction = (
            db.query(Transaction)
            .filter(Transaction.id == transaction_id, Transaction.hotel_id == hotel_id)
            .one_or_none()
        )
        if transaction is None:
            raise CashRegisterError("Transaction does not belong to this hotel")
        if reservation_id is not None and transaction.reservation_id != reservation_id:
            raise CashRegisterError("Transaction does not belong to the selected reservation")

    movement = CashMovement(
        hotel_id=hotel_id,
        session_id=session.id,
        reservation_id=reservation_id,
        transaction_id=transaction_id,
        recorded_by_user_id=recorded_by_user_id,
        movement_type=movement_type,
        amount=_money(amount),
        description=description,
    )
    db.add(movement)
    db.flush()
    return movement


def get_open_session(db: Session, hotel_id: int) -> CashSession | None:
    """Return the single open cash session for a hotel, or None if none is open."""
    return (
        db.query(CashSession)
        .filter(
            CashSession.hotel_id == hotel_id,
            CashSession.status == CashSessionStatusEnum.OPEN,
        )
        .one_or_none()
    )


def record_cash_payment_movement(
    db: Session,
    *,
    transaction: Transaction,
    recorded_by_user_id: int | None = None,
) -> CashMovement | None:
    """Post a completed CASH transaction into the hotel's open cash session.

    A real payment of physical cash must land in the caja so the arqueo matches.
    A deposit/full payment becomes an INCOME movement; a cash refund becomes an
    EXPENSE movement. Non-cash methods (gateway/card) never touch the physical
    caja. Returns the created movement, or ``None`` when no session is open
    (the payment itself still succeeds; the cash simply isn't tracked yet).
    """
    if transaction.payment_method != PaymentMethodEnum.CASH:
        return None
    if transaction.status != TransactionStatusEnum.COMPLETED:
        return None

    session = get_open_session(db, transaction.hotel_id)
    if session is None:
        return None

    from app.models.transaction import TransactionTypeEnum

    is_refund = transaction.transaction_type == TransactionTypeEnum.REFUND
    movement_type = CashMovementTypeEnum.EXPENSE if is_refund else CashMovementTypeEnum.INCOME
    label = "Devolución" if is_refund else "Cobro"
    # The caja must hold the cash physically moved, i.e. the gross amount that
    # includes any payment surcharge (gross_amount). Fall back to the base amount
    # when no surcharge was recorded.
    cash_amount = transaction.gross_amount if transaction.gross_amount is not None else transaction.amount
    surcharge = _money(transaction.fee_amount or 0)
    description = f"{label} reserva #{transaction.reservation_id} (tx #{transaction.id})"
    if surcharge > 0:
        description += f" · incl. recargo ${surcharge}"

    return add_movement(
        db,
        hotel_id=transaction.hotel_id,
        session_id=session.id,
        recorded_by_user_id=recorded_by_user_id,
        movement_type=movement_type,
        amount=_money(cash_amount),
        description=description,
        reservation_id=transaction.reservation_id,
        transaction_id=transaction.id,
    )


def _movement_sign(movement_type: CashMovementTypeEnum) -> Decimal:
    if movement_type == CashMovementTypeEnum.EXPENSE:
        return Decimal("-1")
    return Decimal("1")


def _confirmed_cash_movements_total(db: Session, session: CashSession, closed_at: datetime) -> Decimal:
    movements: Iterable[CashMovement] = (
        db.query(CashMovement)
        .filter(
            CashMovement.hotel_id == session.hotel_id,
            CashMovement.session_id == session.id,
            CashMovement.recorded_at >= session.opened_at,
            CashMovement.recorded_at <= closed_at,
        )
        .all()
    )

    total = Decimal("0.00")
    transaction_ids = [movement.transaction_id for movement in movements if movement.transaction_id is not None]
    transactions_by_id: dict[int, Transaction] = {}
    if transaction_ids:
        transactions_by_id = {
            tx.id: tx
            for tx in db.query(Transaction)
            .filter(Transaction.hotel_id == session.hotel_id, Transaction.id.in_(transaction_ids))
            .all()
        }

    for movement in movements:
        if movement.transaction_id is not None:
            tx = transactions_by_id.get(movement.transaction_id)
            if (
                tx is None
                or tx.payment_method != PaymentMethodEnum.CASH
                or tx.status != TransactionStatusEnum.COMPLETED
            ):
                continue
        total += _movement_sign(movement.movement_type) * _money(movement.amount)
    return _money(total)


def get_session_summary(db: Session, *, hotel_id: int, session_id: int) -> dict:
    """Authoritative live summary for a cash session.

    ``expected_balance`` reuses the SAME confirmed-cash logic as the arqueo
    (:func:`close_session`) so the number the UI shows always matches what the
    close will compute — single source of truth. Raw income/expense/adjustment
    totals are returned for display.
    """
    session = (
        db.query(CashSession)
        .filter(CashSession.id == session_id, CashSession.hotel_id == hotel_id)
        .one_or_none()
    )
    if session is None:
        raise CashRegisterError("Cash session not found for this hotel")

    as_of = datetime.now(timezone.utc)
    movements = list_movements(db, hotel_id=hotel_id, session_id=session_id)
    income = sum((_money(m.amount) for m in movements if m.movement_type == CashMovementTypeEnum.INCOME), Decimal("0.00"))
    expense = sum((_money(m.amount) for m in movements if m.movement_type == CashMovementTypeEnum.EXPENSE), Decimal("0.00"))
    adjustment = sum((_money(m.amount) for m in movements if m.movement_type == CashMovementTypeEnum.ADJUSTMENT), Decimal("0.00"))
    confirmed_total = _confirmed_cash_movements_total(db, session, as_of)
    expected_balance = _money(session.opening_balance) + confirmed_total

    return {
        "session_id": session.id,
        "status": session.status.value if hasattr(session.status, "value") else str(session.status),
        "currency_code": session.currency_code,
        "opening_balance": _money(session.opening_balance),
        "income_total": _money(income),
        "expense_total": _money(expense),
        "adjustment_total": _money(adjustment),
        "confirmed_cash_total": confirmed_total,
        "expected_balance": expected_balance,
        "movements_count": len(movements),
    }


def close_session(
    db: Session,
    *,
    hotel_id: int,
    session_id: int,
    closed_by_user_id: int | None,
    counted_balance: Decimal,
    notes: str | None = None,
    approved_by_user_id: int | None = None,
) -> CashCloseReport:
    """
    Close a cash session and create its close report.

    The session row is selected with FOR UPDATE where supported so concurrent
    closes cannot both create an arqueo for the same session.
    """

    stmt = (
        select(CashSession)
        .where(CashSession.id == session_id, CashSession.hotel_id == hotel_id)
        .with_for_update()
    )
    session = db.execute(stmt).scalar_one_or_none()
    if session is None:
        raise CashRegisterError("Cash session not found for this hotel")
    if session.status != CashSessionStatusEnum.OPEN:
        raise CashRegisterError("Cash session is not open")
    if session.close_report is not None:
        raise CashRegisterError("Cash session already has a close report")

    closed_at = datetime.now(timezone.utc)
    expected_balance = _money(session.opening_balance) + _confirmed_cash_movements_total(db, session, closed_at)
    declared_balance = _money(counted_balance)
    difference = _money(declared_balance - expected_balance)
    has_difference = difference != Decimal("0.00")
    difference_approved = bool(has_difference and approved_by_user_id is not None)

    session.closed_at = closed_at
    session.closed_by_user_id = closed_by_user_id
    session.status = (
        CashSessionStatusEnum.CLOSED
        if not has_difference or difference_approved
        else CashSessionStatusEnum.PENDING_APPROVAL
    )

    report = CashCloseReport(
        hotel_id=hotel_id,
        session_id=session.id,
        closed_by_user_id=closed_by_user_id,
        expected_balance=expected_balance,
        declared_balance=declared_balance,
        difference=difference,
        difference_approved=difference_approved,
        approved_by_user_id=approved_by_user_id if difference_approved else None,
        notes=notes,
        closed_at=closed_at,
    )
    db.add(report)
    db.flush()
    return report


def approve_close_difference(
    db: Session,
    *,
    hotel_id: int,
    report_id: int,
    approved_by_user_id: int | None,
) -> CashCloseReport:
    report = (
        db.query(CashCloseReport)
        .filter(CashCloseReport.id == report_id, CashCloseReport.hotel_id == hotel_id)
        .one_or_none()
    )
    if report is None:
        raise CashRegisterError("Cash close report not found for this hotel")
    if report.difference == Decimal("0.00"):
        raise CashRegisterError("Cash close report has no difference to approve")

    session = (
        db.query(CashSession)
        .filter(CashSession.id == report.session_id, CashSession.hotel_id == hotel_id)
        .with_for_update()
        .one_or_none()
    )
    if session is None:
        raise CashRegisterError("Cash session not found for this hotel")

    report.difference_approved = True
    report.approved_by_user_id = approved_by_user_id
    session.status = CashSessionStatusEnum.CLOSED
    db.flush()
    return report


def list_sessions(db: Session, *, hotel_id: int) -> list[CashSession]:
    return (
        db.query(CashSession)
        .filter(CashSession.hotel_id == hotel_id)
        .order_by(CashSession.opened_at.desc(), CashSession.id.desc())
        .all()
    )


def list_movements(db: Session, *, hotel_id: int, session_id: int) -> list[CashMovement]:
    return (
        db.query(CashMovement)
        .join(CashSession, CashSession.id == CashMovement.session_id)
        .filter(
            CashMovement.hotel_id == hotel_id,
            CashMovement.session_id == session_id,
            CashSession.hotel_id == hotel_id,
        )
        .order_by(CashMovement.recorded_at.asc(), CashMovement.id.asc())
        .all()
    )
