"""Hotel-local daily cash and payment read model.

This module only projects the existing transaction and cash-register ledgers;
it never creates a second financial source of truth.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import and_, func
from sqlalchemy.orm import Session, joinedload

from app.models.cash_register import (
    CashCloseReport,
    CashCustodyHandoff,
    CashCustodyStatusEnum,
    CashMovement,
    CashMovementTypeEnum,
    CashSession,
)
from app.models.hotel_config import HotelConfiguration
from app.models.reservation import Reservation
from app.models.transaction import PaymentMethodEnum, Transaction, TransactionStatusEnum, TransactionTypeEnum
from app.services.actor_label_service import resolve_hotel_actor_labels
from app.services.timezones import normalize_timezone


ZERO = Decimal("0.00")
ENTRY_LIMIT = 500


def _decimal(value: object) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("0.01"))


def _value(value: object) -> str:
    return value.value if hasattr(value, "value") else str(value)


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _utc_bounds(report_date: date, timezone_name: str) -> tuple[datetime, datetime]:
    zone = ZoneInfo(timezone_name)
    start = datetime.combine(report_date, time.min, tzinfo=zone).astimezone(timezone.utc)
    end = datetime.combine(report_date + timedelta(days=1), time.min, tzinfo=zone).astimezone(timezone.utc)
    return start, end


def _db_utc_bounds(report_date: date, timezone_name: str) -> tuple[datetime, datetime]:
    """Return UTC bounds in the representation used by the ledger columns.

    The legacy cash/transaction tables use ``DateTime`` without timezone.
    Binding an aware value to PostgreSQL can fail when a historic session is
    queried, even though the same query appears to work against SQLite. Keep
    comparisons naive at the database boundary and attach UTC only when
    serializing values back to the API.
    """
    start, end = _utc_bounds(report_date, timezone_name)
    return start.replace(tzinfo=None), end.replace(tzinfo=None)


def _actor_name(
    user_id: int | None,
    actor_labels: dict[int, str],
    *,
    provider_code: str | None = None,
) -> str:
    if user_id is not None:
        return actor_labels.get(user_id, "Usuario")
    return "Sistema/Proveedor" if provider_code else "Sistema"


def get_daily_summary(
    db: Session,
    *,
    hotel_id: int,
    report_date: date,
    currency_code: str | None = None,
) -> dict:
    hotel = db.get(HotelConfiguration, hotel_id)
    timezone_name = normalize_timezone((hotel.hotel_timezone if hotel else None) or "UTC")
    start, end = _utc_bounds(report_date, timezone_name)
    db_start, db_end = _db_utc_bounds(report_date, timezone_name)
    selected_currency = (currency_code or "").strip().upper() or None
    if selected_currency and len(selected_currency) != 3:
        raise ValueError("La moneda debe usar un código de tres letras")

    transactions = (
        db.query(Transaction)
        .filter(
            Transaction.hotel_id == hotel_id,
            Transaction.status == TransactionStatusEnum.COMPLETED,
            Transaction.collected_before.is_(False),
            Transaction.processed_at >= db_start,
            Transaction.processed_at < db_end,
        )
        .order_by(Transaction.processed_at.asc(), Transaction.id.asc())
        .all()
    )
    prior_receipt_rows = (
        db.query(Transaction, Reservation.confirmation_code)
        .join(
            Reservation,
            and_(
                Reservation.hotel_id == Transaction.hotel_id,
                Reservation.id == Transaction.reservation_id,
            ),
        )
        .filter(
            Transaction.hotel_id == hotel_id,
            Transaction.status == TransactionStatusEnum.COMPLETED,
            Transaction.payment_method == PaymentMethodEnum.CASH,
            Transaction.collected_before.is_(True),
        )
        .order_by(Transaction.collected_on.asc(), Transaction.id.asc())
        .limit(ENTRY_LIMIT + 1)
        .all()
    )
    prior_receipt_totals = (
        db.query(
            func.coalesce(Transaction.tender_currency, Transaction.currency),
            func.sum(func.coalesce(Transaction.tender_amount, Transaction.amount)),
            func.count(Transaction.id),
        )
        .filter(
            Transaction.hotel_id == hotel_id,
            Transaction.status == TransactionStatusEnum.COMPLETED,
            Transaction.payment_method == PaymentMethodEnum.CASH,
            Transaction.collected_before.is_(True),
        )
        .group_by(func.coalesce(Transaction.tender_currency, Transaction.currency))
        .order_by(func.coalesce(Transaction.tender_currency, Transaction.currency).asc())
        .all()
    )
    movements = (
        db.query(CashMovement)
        .filter(
            CashMovement.hotel_id == hotel_id,
            CashMovement.recorded_at >= db_start,
            CashMovement.recorded_at < db_end,
        )
        .order_by(CashMovement.recorded_at.asc(), CashMovement.id.asc())
        .all()
    )
    sessions = (
        db.query(CashSession)
        .filter(
            CashSession.hotel_id == hotel_id,
            CashSession.opened_at < db_end,
            (CashSession.closed_at.is_(None) | (CashSession.closed_at > db_start)),
        )
        .order_by(CashSession.opened_at.asc(), CashSession.id.asc())
        .all()
    )
    session_ids = [session.id for session in sessions]
    prior_movements = (
        db.query(CashMovement)
        .filter(
            CashMovement.hotel_id == hotel_id,
            CashMovement.session_id.in_(session_ids),
            CashMovement.recorded_at < db_start,
        )
        .order_by(CashMovement.recorded_at.asc(), CashMovement.id.asc())
        .all()
        if session_ids
        else []
    )
    movement_transaction_ids = {
        movement.transaction_id
        for movement in [*movements, *prior_movements]
        if movement.transaction_id is not None
    }
    movement_transactions = {
        transaction.id: transaction
        for transaction in (
            db.query(Transaction)
            .filter(
                Transaction.hotel_id == hotel_id,
                Transaction.id.in_(movement_transaction_ids),
            )
            .all()
            if movement_transaction_ids
            else []
        )
    }
    session_currencies = {
        session.id: str(session.currency_code or (hotel.default_currency if hotel else "ARS")).upper()
        for session in sessions
    }
    # `confirm_cash_custody` writes the declared change float to the successor
    # CashSession.opening_balance. The handoff's delivered_amount is the full
    # prior drawer count, not extra cash in the successor; adding it here would
    # count the same physical money twice (and could include money withdrawn by
    # the owner). Keep the persisted successor opening as the single source.
    observed_currencies = {
        str(transaction.tender_currency or transaction.currency or (hotel.default_currency if hotel else "ARS")).upper()
        for transaction in transactions
    }
    observed_currencies.update(session_currencies.values())
    if selected_currency:
        report_currency = selected_currency
    elif len(observed_currencies) > 1:
        raise ValueError("Elegí una moneda: el resumen no convierte monedas automáticamente")
    else:
        report_currency = next(iter(observed_currencies), str(hotel.default_currency if hotel else "ARS").upper())

    actor_ids = {
        transaction.created_by_user_id
        for transaction in transactions
        if transaction.created_by_user_id is not None
    }
    actor_ids.update(
        transaction.created_by_user_id
        for transaction, _confirmation_code in prior_receipt_rows[:ENTRY_LIMIT]
        if transaction.created_by_user_id is not None
    )
    actor_ids.update(
        movement.recorded_by_user_id
        for movement in movements
        if movement.recorded_by_user_id is not None
    )
    actor_ids.update(
        user_id
        for session in sessions
        for user_id in (session.opened_by_user_id, session.closed_by_user_id)
        if user_id is not None
    )
    actor_labels = resolve_hotel_actor_labels(
        db,
        hotel_id=hotel_id,
        user_ids=actor_ids,
    )

    methods: dict[str, dict[str, Decimal | int]] = defaultdict(
        lambda: {"gross_collected": ZERO, "refunds": ZERO, "net_collected": ZERO, "transaction_count": 0}
    )
    collectors: dict[tuple[int | None, str], dict[str, Decimal | int]] = defaultdict(
        lambda: {"gross_collected": ZERO, "refunds": ZERO, "net_collected": ZERO, "transaction_count": 0}
    )
    entries: list[dict] = []
    gross_total = ZERO
    refunds_total = ZERO
    physical_net = ZERO
    digital_net = ZERO

    for transaction in transactions:
        transaction_currency = str(transaction.tender_currency or transaction.currency or (hotel.default_currency if hotel else "ARS")).upper()
        if transaction_currency != report_currency:
            continue
        method = _value(transaction.payment_method)
        transaction_type = _value(transaction.transaction_type)
        amount = _decimal(transaction.gross_amount if transaction.gross_amount is not None else transaction.amount)
        base_amount = _decimal(transaction.tender_amount if transaction.tender_amount is not None else transaction.amount)
        is_refund = transaction_type == TransactionTypeEnum.REFUND.value
        positive_amount = abs(amount)
        signed_amount = -positive_amount if is_refund else positive_amount
        method_row = methods[method]
        collector_key = transaction.created_by_user_id
        collector_name = _actor_name(
            collector_key,
            actor_labels,
            provider_code=transaction.provider_code,
        )
        collector_row = collectors[(collector_key, collector_name)]
        if is_refund:
            refunds_total += positive_amount
            method_row["refunds"] += positive_amount
            collector_row["refunds"] += positive_amount
        else:
            gross_total += positive_amount
            method_row["gross_collected"] += positive_amount
            collector_row["gross_collected"] += positive_amount
        method_row["net_collected"] += signed_amount
        collector_row["net_collected"] += signed_amount
        method_row["transaction_count"] += 1
        collector_row["transaction_count"] += 1
        if method == PaymentMethodEnum.CASH.value:
            physical_net += signed_amount
        else:
            digital_net += signed_amount
        entries.append(
            {
                "entry_type": "payment",
                "actor_user_id": collector_key,
                "actor_name": collector_name,
                "transaction_id": transaction.id,
                "group_payment_batch_id": getattr(transaction, "group_payment_batch_id", None),
                "reservation_id": transaction.reservation_id,
                "amount": positive_amount,
                "signed_amount": signed_amount,
                "currency_code": transaction_currency,
                "payment_method": method,
                "transaction_type": transaction_type,
                "transaction_status": _value(transaction.status),
                "occurred_at": _utc(transaction.processed_at),
                "description": transaction.description,
                "provider_code": transaction.provider_code,
            }
        )

    manual_income = ZERO
    manual_expense = ZERO
    cash_income = ZERO
    cash_expense = ZERO
    cash_adjustment = ZERO
    physical_movement_net_by_session: dict[int, Decimal] = defaultdict(lambda: ZERO)
    for movement in movements:
        movement_currency = session_currencies.get(
            movement.session_id,
            str(hotel.default_currency if hotel else "ARS").upper(),
        )
        if movement_currency != report_currency:
            continue
        # Payment movements already appear in the transaction section. Keep
        # them in the physical cash calculation but not as duplicate dashboard
        # entries; manual movements are the operator's additional detail.
        linked_transaction = movement_transactions.get(movement.transaction_id) if movement.transaction_id else None
        if movement.transaction_id is not None and (
            linked_transaction is None
            or linked_transaction.status != TransactionStatusEnum.COMPLETED
            or linked_transaction.payment_method != PaymentMethodEnum.CASH
        ):
            # A failed/pending/digital transaction cannot alter physical cash,
            # even if a stale or manually imported movement points at it.
            continue
        signed_amount = _decimal(movement.amount)
        movement_type = _value(movement.movement_type)
        if movement_type == CashMovementTypeEnum.EXPENSE.value:
            signed_amount = -signed_amount
            cash_expense += abs(signed_amount)
            if movement.transaction_id is None:
                manual_expense += abs(signed_amount)
        elif movement_type == CashMovementTypeEnum.ADJUSTMENT.value:
            cash_adjustment += signed_amount
        else:
            cash_income += signed_amount
            if movement.transaction_id is None:
                manual_income += signed_amount
        physical_movement_net_by_session[movement.session_id] += signed_amount
        if movement.transaction_id is None:
            entries.append(
                {
                    "entry_type": "manual_movement",
                    "actor_user_id": movement.recorded_by_user_id,
                    "actor_name": _actor_name(movement.recorded_by_user_id, actor_labels),
                    "cash_movement_id": movement.id,
                    "reservation_id": movement.reservation_id,
                    "amount": _decimal(movement.amount),
                    "signed_amount": signed_amount,
                    "currency_code": movement_currency,
                    "movement_type": movement_type,
                    "occurred_at": _utc(movement.recorded_at),
                    "description": movement.description,
                }
            )

    entries.sort(
        key=lambda item: (
            _utc(item["occurred_at"]) or datetime.min.replace(tzinfo=timezone.utc),
            item.get("transaction_id") or item.get("cash_movement_id") or 0,
        )
    )

    # The opening balance is the balance carried by the session active at the
    # local-day boundary. New sessions opened during the day add their own
    # opening balance, while a close report supplies the declared/difference
    # evidence for each session.
    session_reads: list[dict] = []
    opening_balance = ZERO
    declared_values: list[Decimal] = []
    difference_values: list[Decimal] = []
    custody_delivered_total = ZERO
    custody_difference_total = ZERO
    prior_net_by_session: dict[int, Decimal] = defaultdict(lambda: ZERO)
    report_currency_session_ids = [
        session.id for session in sessions if session_currencies.get(session.id) == report_currency
    ]
    close_reports_by_session = {
        report.session_id: report
        for report in (
            db.query(CashCloseReport)
            .options(joinedload(CashCloseReport.custody_handoff))
            .filter(
                CashCloseReport.hotel_id == hotel_id,
                CashCloseReport.session_id.in_(report_currency_session_ids),
            )
            .all()
            if report_currency_session_ids
            else []
        )
    }
    boundary_session_ids = [
        session.id
        for session in sessions
        if session_currencies.get(session.id) == report_currency
        and _utc(session.opened_at) is not None
        and _utc(session.opened_at) <= start
        and (_utc(session.closed_at) is None or _utc(session.closed_at) > start)
    ]
    legacy_carry_by_successor = {
        successor_session_id: handoff
        for successor_session_id, handoff in (
            db.query(CashCloseReport.successor_session_id, CashCustodyHandoff)
            .join(
                CashCustodyHandoff,
                and_(
                    CashCustodyHandoff.close_report_id == CashCloseReport.id,
                    CashCustodyHandoff.hotel_id == CashCloseReport.hotel_id,
                ),
            )
            .filter(
                CashCloseReport.hotel_id == hotel_id,
                CashCloseReport.successor_session_id.in_(boundary_session_ids),
                CashCloseReport.successor_float_declared_amount.is_(None),
                CashCustodyHandoff.status == CashCustodyStatusEnum.CONFIRMED,
            )
            .all()
            if boundary_session_ids
            else []
        )
    }
    for movement in prior_movements:
        linked_transaction = movement_transactions.get(movement.transaction_id) if movement.transaction_id else None
        if movement.transaction_id is not None and (
            linked_transaction is None
            or linked_transaction.status != TransactionStatusEnum.COMPLETED
            or linked_transaction.payment_method != PaymentMethodEnum.CASH
        ):
            continue
        movement_currency = session_currencies.get(
            movement.session_id,
            str(hotel.default_currency if hotel else "ARS").upper(),
        )
        if movement_currency != report_currency:
            continue
        signed_amount = _decimal(movement.amount)
        movement_type = _value(movement.movement_type)
        if movement_type == CashMovementTypeEnum.EXPENSE.value:
            signed_amount = -signed_amount
        prior_net_by_session[movement.session_id] += signed_amount
    for session in sessions:
        if session_currencies.get(session.id) != report_currency:
            continue
        close_report = close_reports_by_session.get(session.id)
        opened_at = _utc(session.opened_at)
        closed_at = _utc(session.closed_at)
        session_opening_balance = _decimal(session.opening_balance)
        if opened_at is not None and opened_at <= start and (closed_at is None or closed_at > start):
            # Include prior movements on a session that was already open at
            # the hotel-local day boundary. Any declared successor float is
            # already represented by session.opening_balance.
            prior_handoff = legacy_carry_by_successor.get(session.id)
            if prior_handoff is not None:
                acknowledged_at = _utc(prior_handoff.received_at or prior_handoff.delivered_at)
                if acknowledged_at is not None and acknowledged_at <= start:
                    # Rows predating explicit float declarations used the
                    # confirmed full handoff as the successor opening. Keep
                    # that historical behavior, while new confirmations use
                    # the declared float stored directly on the session.
                    session_opening_balance += _decimal(prior_handoff.delivered_amount)
            session_opening_balance += prior_net_by_session.get(session.id, ZERO)
            opening_balance += session_opening_balance
        elif opened_at is not None and start <= opened_at < end:
            opening_balance += session_opening_balance
        close_at = _utc(close_report.closed_at) if close_report is not None else None
        close_occurred_today = close_at is not None and start <= close_at < end
        if close_report is not None and close_occurred_today:
            declared = _decimal(close_report.declared_balance)
            difference = _decimal(close_report.difference)
            declared_values.append(declared)
            difference_values.append(difference)
        else:
            declared = None
            difference = None
        if close_report is not None:
            handoff = close_report.custody_handoff
            handoff_at = _utc(handoff.delivered_at) if handoff is not None else None
            if handoff_at is not None and start <= handoff_at < end:
                # Closing removes the declared cash from the old drawer. The
                # successor float is already included in opening_balance, so
                # only the delivered amount is subtracted here. Include the
                # close difference to reconcile the ledger expectation to the
                # amount actually counted before delivery.
                custody_delivered_total += _decimal(handoff.delivered_amount)
                custody_difference_total += _decimal(close_report.difference)
        session_reads.append(
            {
                "session_id": session.id,
                "status": _value(session.status),
                "currency_code": session_currencies.get(session.id, report_currency),
                "opened_at": _utc(session.opened_at),
                "closed_at": _utc(session.closed_at),
                "opened_by_user_id": session.opened_by_user_id,
                "closed_by_user_id": session.closed_by_user_id,
                "opened_by_name": actor_labels.get(session.opened_by_user_id) if session.opened_by_user_id else None,
                "closed_by_name": actor_labels.get(session.closed_by_user_id) if session.closed_by_user_id else None,
                "opening_balance": session_opening_balance,
                "expected_balance": None,
                "declared_balance": declared,
                "difference": difference,
            }
        )

    # Physical cash is authoritative from the cash movements and cash custody
    # transitions; transaction totals are displayed separately so digital
    # payments never inflate it. A successor float is already included in the
    # summed openings, while a same-day close removes the declared delivery.
    cash_movement_net = cash_income - cash_expense + cash_adjustment
    physical_expected = (
        opening_balance
        + cash_movement_net
        + custody_difference_total
        - custody_delivered_total
    )
    for session_read in session_reads:
        session_net = physical_movement_net_by_session.get(session_read["session_id"], ZERO)
        session_read["expected_balance"] = _decimal(session_read["opening_balance"] + session_net)

    entries_truncated = len(entries) > ENTRY_LIMIT
    return {
        "hotel_id": hotel_id,
        "report_date": report_date.isoformat(),
        "timezone": timezone_name,
        "currency_code": report_currency,
        "gross_collected": _decimal(gross_total),
        "refunds": _decimal(refunds_total),
        "net_collected": _decimal(gross_total - refunds_total),
        "physical_cash_net_collected": _decimal(physical_net),
        "digital_net_collected": _decimal(digital_net),
        "by_payment_method": [
            {"payment_method": key, **{field: _decimal(value) if field != "transaction_count" else int(value) for field, value in row.items()}}
            for key, row in sorted(methods.items())
        ],
        "by_collector": [
            {
                "collector_user_id": key[0],
                "collector_name": key[1],
                **{field: _decimal(value) if field != "transaction_count" else int(value) for field, value in row.items()},
            }
            for key, row in sorted(collectors.items(), key=lambda item: item[0][1])
        ],
        "physical_cash": {
            "opening_balance": _decimal(opening_balance),
            "income_total": _decimal(cash_income),
            "expense_total": _decimal(cash_expense),
            "adjustment_total": _decimal(cash_adjustment),
            "custody_delivered_total": _decimal(custody_delivered_total),
            "custody_difference_total": _decimal(custody_difference_total),
            "expected_balance": _decimal(physical_expected),
            "declared_balance": _decimal(sum(declared_values, ZERO)) if declared_values else None,
            "difference": _decimal(sum(difference_values, ZERO)) if difference_values else None,
            "manual_income_total": _decimal(manual_income),
            "manual_expense_total": _decimal(manual_expense),
        },
        "prior_receipts": [
            {
                "transaction_id": transaction.id,
                "reservation_id": transaction.reservation_id,
                "confirmation_code": confirmation_code,
                "amount": _decimal(transaction.tender_amount if transaction.tender_amount is not None else transaction.amount),
                "currency_code": str(transaction.tender_currency or transaction.currency or "ARS").upper(),
                "collected_on": transaction.collected_on,
                "prior_receipt_note": transaction.prior_receipt_note,
                "recorded_at": _utc(transaction.created_at),
                "recorded_by_user_id": transaction.created_by_user_id,
                "recorded_by_name": _actor_name(transaction.created_by_user_id, actor_labels),
            }
            for transaction, confirmation_code in prior_receipt_rows[:ENTRY_LIMIT]
        ],
        "prior_receipt_totals": [
            {
                "currency_code": str(currency or "ARS").upper(),
                "amount": _decimal(amount),
                "transaction_count": int(count),
            }
            for currency, amount, count in prior_receipt_totals
        ],
        "prior_receipts_truncated": len(prior_receipt_rows) > ENTRY_LIMIT,
        "sessions": session_reads,
        "entries": entries[:ENTRY_LIMIT],
        "entries_truncated": entries_truncated,
        "generated_at": datetime.now(timezone.utc),
    }
