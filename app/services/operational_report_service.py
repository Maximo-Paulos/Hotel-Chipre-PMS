from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Iterable

from sqlalchemy import or_
from sqlalchemy.orm import Session

import logging

from app.models.cash_register import CashSession, CashSessionStatusEnum
from app.models.company_night_charge import CompanyNightCharge, CompanyNightChargePaymentAllocation
from app.models.hotel_config import HotelConfiguration
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.room import Room
from app.models.room_block import RoomBlock
from app.models.transaction import Transaction, TransactionStatusEnum, TransactionTypeEnum
from app.schemas.reports import (
    ActiveRoomBlockItem,
    AvailableWithReviewItem,
    CashSessionStatusRead,
    DailyOperationalReportRead,
    NightlyOperationalSummaryRead,
    OperationalAlertRead,
    OperationalReservationGroup,
    OperationalReservationSummary,
)
from app.services.financial_ledger import (
    billing_adjustment_totals_by_reservation,
    paid_amounts_by_reservation,
)
from app.services.reservation_service import active_reservations, deferred_company_reservation_ids
from app.services.timezones import hotel_today


logger = logging.getLogger(__name__)


ACTIVE_RESERVATION_STATUSES = (
    ReservationStatusEnum.PENDING,
    ReservationStatusEnum.DEPOSIT_PAID,
    ReservationStatusEnum.FULLY_PAID,
    ReservationStatusEnum.PRE_CHECK_IN,
    ReservationStatusEnum.CHECKED_IN,
)

ARRIVAL_PENDING_STATUSES = (
    ReservationStatusEnum.PENDING,
    ReservationStatusEnum.DEPOSIT_PAID,
    ReservationStatusEnum.FULLY_PAID,
    ReservationStatusEnum.PRE_CHECK_IN,
)


def _guest_name(reservation: Reservation) -> str | None:
    guest = reservation.guest
    if not guest:
        return None
    return guest.full_name


def _reservation_summary(
    reservation: Reservation,
    paid_amount: Decimal | None = None,
    adjustment_total: Decimal | None = None,
    *,
    company_billing_deferred: bool = False,
    company_night_extra_due: Decimal | None = None,
) -> OperationalReservationSummary:
    room = reservation.room
    paid = paid_amount if paid_amount is not None else Decimal(reservation.amount_paid or 0)
    adjustments = adjustment_total if adjustment_total is not None else Decimal("0")
    total_due = Decimal(reservation.total_amount or 0) + adjustments
    return OperationalReservationSummary(
        reservation_id=reservation.id,
        confirmation_code=reservation.confirmation_code,
        guest_id=reservation.guest_id,
        guest_name=_guest_name(reservation),
        room_id=reservation.room_id,
        room_number=room.room_number if room else None,
        status=reservation.status.value,
        check_in_date=reservation.check_in_date,
        check_out_date=reservation.check_out_date,
        total_amount=None if company_billing_deferred else Decimal(reservation.total_amount or 0),
        amount_paid=None if company_billing_deferred else paid,
        balance_due=None if company_billing_deferred else max(Decimal("0"), total_due - paid),
        currency_code=str(reservation.currency_code or "ARS").strip().upper(),
        company_billing_deferred=company_billing_deferred,
        company_night_extra_due=company_night_extra_due if company_billing_deferred else None,
    )


def _group(
    reservations: Iterable[Reservation],
    paid_by_reservation: dict[int, Decimal] | None = None,
    adjustments_by_reservation: dict[int, Decimal] | None = None,
    deferred_reservation_ids: set[int] | None = None,
    company_night_extra_due_by_reservation: dict[int, Decimal] | None = None,
) -> OperationalReservationGroup:
    paid_by_reservation = paid_by_reservation or {}
    adjustments_by_reservation = adjustments_by_reservation or {}
    deferred_reservation_ids = deferred_reservation_ids or set()
    company_night_extra_due_by_reservation = company_night_extra_due_by_reservation or {}
    items = [
        _reservation_summary(
            reservation,
            paid_by_reservation.get(reservation.id),
            adjustments_by_reservation.get(reservation.id),
            company_billing_deferred=reservation.id in deferred_reservation_ids,
            company_night_extra_due=company_night_extra_due_by_reservation.get(reservation.id),
        )
        for reservation in reservations
    ]
    return OperationalReservationGroup(count=len(items), reservations=items)


def company_night_extra_balances_by_reservation(
    db: Session,
    *,
    hotel_id: int,
    reservation_ids: set[int],
    stay_date_from: date,
    stay_date_to: date,
) -> tuple[dict[int, Decimal], dict[int, Decimal]]:
    """Return approved company-extra totals and remaining amounts by stay date.

    Reservation base lodging is deliberately absent: only explicit
    CompanyNightCharge rows are collectible inside the PMS. A transaction is
    credited here only if its full amount is allocated to those extras.
    """
    if not reservation_ids or stay_date_to < stay_date_from:
        return {}, {}
    charges = (
        db.query(CompanyNightCharge)
        .filter(
            CompanyNightCharge.hotel_id == hotel_id,
            CompanyNightCharge.reservation_id.in_(reservation_ids),
        )
        .order_by(CompanyNightCharge.id.asc())
        .all()
    )
    if not charges:
        return {}, {}

    charges_by_id = {charge.id: charge for charge in charges}
    allocations = (
        db.query(CompanyNightChargePaymentAllocation, Transaction)
        .join(
            Transaction,
            (Transaction.id == CompanyNightChargePaymentAllocation.transaction_id)
            & (Transaction.hotel_id == CompanyNightChargePaymentAllocation.hotel_id),
        )
        .filter(
            CompanyNightChargePaymentAllocation.hotel_id == hotel_id,
            CompanyNightChargePaymentAllocation.company_night_charge_id.in_(charges_by_id),
        )
        .all()
    )
    allocated_total_by_transaction: dict[int, Decimal] = {}
    for allocation, _transaction in allocations:
        allocated_total_by_transaction[allocation.transaction_id] = (
            allocated_total_by_transaction.get(allocation.transaction_id, Decimal("0.00"))
            + Decimal(str(allocation.amount or 0))
        )

    refunds_by_transaction: dict[int, Decimal] = {}
    allocated_transaction_ids = set(allocated_total_by_transaction)
    if allocated_transaction_ids:
        for transaction_id, amount in (
            db.query(Transaction.refund_of_transaction_id, Transaction.amount)
            .filter(
                Transaction.hotel_id == hotel_id,
                Transaction.refund_of_transaction_id.in_(allocated_transaction_ids),
                Transaction.transaction_type == TransactionTypeEnum.REFUND,
                Transaction.status == TransactionStatusEnum.COMPLETED,
            )
            .all()
        ):
            refunds_by_transaction[transaction_id] = (
                refunds_by_transaction.get(transaction_id, Decimal("0.00"))
                + Decimal(str(amount or 0))
            )

    paid_by_charge: dict[int, Decimal] = {}
    for allocation, transaction in allocations:
        charge_id = allocation.company_night_charge_id
        if transaction.status == TransactionStatusEnum.PENDING:
            continue
        if (
            transaction.status != TransactionStatusEnum.COMPLETED
            or transaction.transaction_type == TransactionTypeEnum.REFUND
        ):
            continue
        transaction_amount = Decimal(str(transaction.amount or 0))
        allocated_amount = allocated_total_by_transaction.get(transaction.id, Decimal("0.00"))
        if (
            transaction_amount <= 0
            or allocated_amount.quantize(Decimal("0.01"))
            != transaction_amount.quantize(Decimal("0.01"))
        ):
            continue
        refunded = min(refunds_by_transaction.get(transaction.id, Decimal("0.00")), transaction_amount)
        net_fraction = Decimal("1") - refunded / transaction_amount
        paid_by_charge[charge_id] = paid_by_charge.get(charge_id, Decimal("0.00")) + (
            Decimal(str(allocation.amount or 0)) * net_fraction
        )

    totals: dict[int, Decimal] = {}
    due: dict[int, Decimal] = {}
    for charge in charges:
        if not stay_date_from <= charge.stay_date <= stay_date_to:
            continue
        amount = Decimal(str(charge.amount or 0)).quantize(Decimal("0.01"))
        totals[charge.reservation_id] = totals.get(charge.reservation_id, Decimal("0.00")) + amount
        remaining = max(Decimal("0.00"), amount - paid_by_charge.get(charge.id, Decimal("0.00")))
        due[charge.reservation_id] = due.get(charge.reservation_id, Decimal("0.00")) + remaining
    return (
        {key: value.quantize(Decimal("0.01")) for key, value in totals.items()},
        {key: value.quantize(Decimal("0.01")) for key, value in due.items()},
    )


def filter_pms_revenue_transactions(
    db: Session,
    *,
    hotel_id: int,
    transactions: list[Transaction],
) -> list[Transaction]:
    """Exclude deferred lodging receipts while retaining selected-extra ledger rows."""
    if not transactions:
        return []
    reservation_ids = {transaction.reservation_id for transaction in transactions}
    reservations = (
        db.query(Reservation)
        .filter(Reservation.hotel_id == hotel_id, Reservation.id.in_(reservation_ids))
        .all()
    )
    deferred_ids = deferred_company_reservation_ids(
        db,
        hotel_id=hotel_id,
        reservations=reservations,
    )
    if not deferred_ids:
        return transactions

    deferred_transactions = {
        transaction.id: transaction
        for transaction in transactions
        if transaction.reservation_id in deferred_ids
    }
    if not deferred_transactions:
        return transactions

    allocation_rows = (
        db.query(CompanyNightChargePaymentAllocation, Transaction)
        .join(
            CompanyNightCharge,
            (CompanyNightCharge.id == CompanyNightChargePaymentAllocation.company_night_charge_id)
            & (CompanyNightCharge.hotel_id == CompanyNightChargePaymentAllocation.hotel_id),
        )
        .join(
            Transaction,
            (Transaction.id == CompanyNightChargePaymentAllocation.transaction_id)
            & (Transaction.hotel_id == CompanyNightChargePaymentAllocation.hotel_id),
        )
        .filter(
            CompanyNightChargePaymentAllocation.hotel_id == hotel_id,
            CompanyNightCharge.reservation_id.in_(deferred_ids),
            CompanyNightChargePaymentAllocation.transaction_id.in_(deferred_transactions),
        )
        .all()
    )
    allocated_by_transaction: dict[int, Decimal] = {}
    for allocation, _transaction in allocation_rows:
        allocated_by_transaction[allocation.transaction_id] = (
            allocated_by_transaction.get(allocation.transaction_id, Decimal("0.00"))
            + Decimal(str(allocation.amount or 0))
        )
    eligible_extra_transactions = {
        transaction_id
        for transaction_id, allocated_amount in allocated_by_transaction.items()
        if transaction_id in deferred_transactions
        and allocated_amount.quantize(Decimal("0.01"))
        == Decimal(str(deferred_transactions[transaction_id].amount or 0)).quantize(Decimal("0.01"))
    }
    eligible_refunds = {
        transaction.id
        for transaction in transactions
        if transaction.reservation_id in deferred_ids
        and transaction.transaction_type == TransactionTypeEnum.REFUND
        and transaction.refund_of_transaction_id in eligible_extra_transactions
    }
    return [
        transaction
        for transaction in transactions
        if transaction.reservation_id not in deferred_ids
        or transaction.id in eligible_extra_transactions
        or transaction.id in eligible_refunds
    ]


def _active_room_blocks(db: Session, hotel_id: int, report_date: date) -> list[ActiveRoomBlockItem]:
    blocks = (
        db.query(RoomBlock)
        .filter(
            RoomBlock.hotel_id == hotel_id,
            RoomBlock.resolved_at.is_(None),
            RoomBlock.starts_at <= report_date,
            or_(RoomBlock.ends_at.is_(None), RoomBlock.ends_at > report_date),
        )
        .order_by(RoomBlock.starts_at.asc(), RoomBlock.id.asc())
        .all()
    )
    return [
        ActiveRoomBlockItem(
            room_block_id=block.id,
            room_id=block.room_id,
            room_number=block.room.room_number if block.room else None,
            reason_code=block.reason_code.value,
            reason_note=block.reason_note,
            starts_at=block.starts_at,
            ends_at=block.ends_at,
            is_indefinite=bool(block.is_indefinite),
        )
        for block in blocks
    ]


def _available_with_review(db: Session, hotel_id: int, report_date: date) -> list[AvailableWithReviewItem]:
    reservations = (
        active_reservations(db, hotel_id)
        .outerjoin(Room, Reservation.room_id == Room.id)
        .filter(
            Reservation.requires_manual_review.is_(True),
            Reservation.status.in_(ACTIVE_RESERVATION_STATUSES),
            Reservation.check_out_date > report_date,
        )
        .order_by(Reservation.check_in_date.asc(), Reservation.id.asc())
        .all()
    )
    return [
        AvailableWithReviewItem(
            reservation_id=reservation.id,
            confirmation_code=reservation.confirmation_code,
            room_id=reservation.room_id,
            room_number=reservation.room.room_number if reservation.room else None,
            check_in_date=reservation.check_in_date,
            check_out_date=reservation.check_out_date,
            allocation_status=reservation.allocation_status,
        )
        for reservation in reservations
    ]


def _cash_session(db: Session, hotel_id: int) -> CashSessionStatusRead:
    session = (
        db.query(CashSession)
        .filter(CashSession.hotel_id == hotel_id, CashSession.status == CashSessionStatusEnum.OPEN)
        .order_by(CashSession.opened_at.desc(), CashSession.id.desc())
        .first()
    )
    if session is None:
        return CashSessionStatusRead(status="closed")
    return CashSessionStatusRead(
        status=session.status.value,
        session_id=session.id,
        opened_at=session.opened_at,
        opened_by_user_id=session.opened_by_user_id,
        currency_code=session.currency_code,
    )


def _alerts(
    *,
    pending_payments: OperationalReservationGroup,
    late_arrivals: list[OperationalReservationSummary],
    available_with_review: list[AvailableWithReviewItem],
    active_room_blocks: list[ActiveRoomBlockItem],
    cash_session: CashSessionStatusRead,
) -> list[OperationalAlertRead]:
    alerts: list[OperationalAlertRead] = []
    for item in pending_payments.reservations:
        alerts.append(
            OperationalAlertRead(
                code="pending_payment",
                severity="warning",
                message=f"Reservation {item.confirmation_code} has balance due.",
                reservation_id=item.reservation_id,
                amount=(
                    item.company_night_extra_due
                    if item.company_billing_deferred
                    else item.balance_due
                ),
                currency_code=item.currency_code,
                room_id=item.room_id,
            )
        )
    for item in late_arrivals:
        alerts.append(
            OperationalAlertRead(
                code="late_arrival",
                severity="warning",
                message=f"Reservation {item.confirmation_code} has not checked in after its arrival date.",
                reservation_id=item.reservation_id,
                room_id=item.room_id,
            )
        )
    for item in available_with_review:
        alerts.append(
            OperationalAlertRead(
                code="available_with_review",
                severity="warning",
                message=f"Room {item.room_number or item.room_id} is assigned to a reservation requiring review.",
                reservation_id=item.reservation_id,
                room_id=item.room_id,
            )
        )
    for item in active_room_blocks:
        alerts.append(
            OperationalAlertRead(
                code="active_room_block",
                severity="info",
                message=f"Room {item.room_number or item.room_id} has an active block.",
                room_id=item.room_id,
                room_block_id=item.room_block_id,
            )
        )
    if cash_session.status != "open":
        alerts.append(
            OperationalAlertRead(
                code="cash_session_closed",
                severity="info",
                message="No open cash session is active for this hotel.",
            )
        )
    return alerts


def _arrivals_query(db: Session, hotel_id: int, report_date: date):
    return active_reservations(db, hotel_id).filter(
        Reservation.check_in_date == report_date,
        Reservation.status.notin_((
            ReservationStatusEnum.CANCELLED,
            ReservationStatusEnum.NO_SHOW,
        )),
    )


def today_arrival_count(db: Session, hotel_id: int, report_date: date) -> int:
    """Count operational arrivals without loading or exposing reservation data."""
    return _arrivals_query(db, hotel_id, report_date).count()


def daily_report(db: Session, hotel_id: int, report_date: date) -> DailyOperationalReportRead:
    reservation_scope = active_reservations(db, hotel_id)

    arrivals = (
        _arrivals_query(db, hotel_id, report_date)
        .order_by(Reservation.id.asc())
        .all()
    )
    no_shows = (
        reservation_scope.filter(
            Reservation.check_in_date == report_date,
            Reservation.status == ReservationStatusEnum.NO_SHOW,
        )
        .order_by(Reservation.id.asc())
        .all()
    )
    departures = (
        reservation_scope.filter(
            Reservation.check_out_date == report_date,
            Reservation.status != ReservationStatusEnum.CANCELLED,
        )
        .order_by(Reservation.id.asc())
        .all()
    )
    balance_candidates = (
        reservation_scope.filter(
            Reservation.status.in_(ACTIVE_RESERVATION_STATUSES),
            Reservation.check_out_date > report_date,
        )
        .order_by(Reservation.check_in_date.asc(), Reservation.id.asc())
        .all()
    )
    late_arrivals = (
        reservation_scope.filter(
            Reservation.check_in_date < report_date,
            Reservation.check_out_date > report_date,
            Reservation.status.in_(ARRIVAL_PENDING_STATUSES),
        )
        .order_by(Reservation.check_in_date.asc(), Reservation.id.asc())
        .all()
    )
    candidate_ids = {
        reservation.id
        for reservation in (*arrivals, *no_shows, *departures, *balance_candidates, *late_arrivals)
    }
    deferred_ids = deferred_company_reservation_ids(
        db,
        hotel_id=hotel_id,
        reservations=[*arrivals, *no_shows, *departures, *balance_candidates, *late_arrivals],
    )
    _extra_totals, extra_due_by_reservation = company_night_extra_balances_by_reservation(
        db,
        hotel_id=hotel_id,
        reservation_ids=deferred_ids,
        stay_date_from=report_date,
        stay_date_to=report_date,
    )
    # The operational due reflects confirmed OTA credits as well as local
    # payments; cash/revenue totals remain transaction-only elsewhere.
    paid_by_reservation = paid_amounts_by_reservation(db, hotel_id, candidate_ids)
    # Consumption/extra charges (BillingAdjustment) are part of the collectible
    # balance, same as the canonical operational_balance_due helper used
    # elsewhere; omitting them understated/hid pending payments once a guest
    # had unpaid consumption on an otherwise fully-paid stay.
    adjustments_by_reservation = billing_adjustment_totals_by_reservation(db, hotel_id, candidate_ids)
    pending_payments = [
        reservation
        for reservation in balance_candidates
        if (
            extra_due_by_reservation.get(reservation.id, Decimal("0.00")) > 0
            if reservation.id in deferred_ids
            else (
                Decimal(reservation.total_amount or 0)
                + adjustments_by_reservation.get(reservation.id, Decimal("0"))
                - paid_by_reservation.get(reservation.id, Decimal("0"))
            ) > 0
        )
    ]

    pending_group = _group(
        pending_payments,
        paid_by_reservation,
        adjustments_by_reservation,
        deferred_ids,
        extra_due_by_reservation,
    )
    late_items = [
        _reservation_summary(
            reservation,
            paid_by_reservation.get(reservation.id),
            adjustments_by_reservation.get(reservation.id),
            company_billing_deferred=reservation.id in deferred_ids,
            company_night_extra_due=extra_due_by_reservation.get(reservation.id),
        )
        for reservation in late_arrivals
    ]
    review_items = _available_with_review(db, hotel_id, report_date)
    block_items = _active_room_blocks(db, hotel_id, report_date)
    cash_session = _cash_session(db, hotel_id)

    return DailyOperationalReportRead(
        hotel_id=hotel_id,
        report_date=report_date,
        generated_at=datetime.now(timezone.utc),
        arrivals=_group(
            arrivals,
            paid_by_reservation,
            adjustments_by_reservation,
            deferred_ids,
            extra_due_by_reservation,
        ),
        no_shows=_group(
            no_shows,
            paid_by_reservation,
            adjustments_by_reservation,
            deferred_ids,
            extra_due_by_reservation,
        ),
        departures=_group(
            departures,
            paid_by_reservation,
            adjustments_by_reservation,
            deferred_ids,
            extra_due_by_reservation,
        ),
        pending_payments=pending_group,
        late_arrivals=late_items,
        available_with_review=review_items,
        active_room_blocks=block_items,
        cash_session=cash_session,
        alerts=_alerts(
            pending_payments=pending_group,
            late_arrivals=late_items,
            available_with_review=review_items,
            active_room_blocks=block_items,
            cash_session=cash_session,
        ),
    )


def redact_daily_report_financials(
    report: DailyOperationalReportRead,
) -> DailyOperationalReportRead:
    """Project a daily report onto the manager-safe operational contract."""

    payload = report.model_dump()
    for group_name in ("arrivals", "no_shows", "departures"):
        for reservation in payload[group_name]["reservations"]:
            reservation["total_amount"] = None
            reservation["amount_paid"] = None
            reservation["balance_due"] = None
            reservation["company_night_extra_due"] = None
    for reservation in payload["late_arrivals"]:
        reservation["total_amount"] = None
        reservation["amount_paid"] = None
        reservation["balance_due"] = None
        reservation["company_night_extra_due"] = None

    # Even a debtor count/list is financial information. Managers receive no
    # pending-payment identities or alerts from the operational report lane.
    payload["pending_payments"] = {"count": 0, "reservations": []}
    payload["cash_session"] = {
        "status": payload["cash_session"]["status"],
        "session_id": None,
        "opened_at": None,
        "opened_by_user_id": None,
        "currency_code": None,
    }
    payload["alerts"] = [
        {**alert, "cash_session_id": None}
        for alert in payload["alerts"]
        if alert["code"] != "pending_payment"
    ]
    return DailyOperationalReportRead.model_validate(payload)


def nightly_summary(db: Session, hotel_id: int, report_date: date) -> NightlyOperationalSummaryRead:
    report = daily_report(db, hotel_id, report_date)
    return NightlyOperationalSummaryRead(
        hotel_id=hotel_id,
        report_date=report.report_date,
        generated_at=report.generated_at,
        alert_count=len(report.alerts),
        pending_payment_count=report.pending_payments.count,
        late_arrival_count=len(report.late_arrivals),
        available_with_review_count=len(report.available_with_review),
        active_room_block_count=len(report.active_room_blocks),
        cash_session_status=report.cash_session.status,
        alerts=report.alerts,
    )


def redact_nightly_summary_financials(
    summary: NightlyOperationalSummaryRead,
) -> NightlyOperationalSummaryRead:
    """Remove debtor and cash identifiers from the manager alert payload."""

    payload = summary.model_dump()
    payload["pending_payment_count"] = 0
    payload["alerts"] = [
        {**alert, "cash_session_id": None}
        for alert in payload["alerts"]
        if alert["code"] != "pending_payment"
    ]
    payload["alert_count"] = len(payload["alerts"])
    return NightlyOperationalSummaryRead.model_validate(payload)


def operational_report_recipients(db: Session, hotel_id: int) -> list[str]:
    hotel = db.get(HotelConfiguration, hotel_id)
    if not hotel:
        return []
    recipients: list[str] = []
    configured = hotel.operational_report_recipients
    if isinstance(configured, list):
        recipients.extend(str(item).strip().lower() for item in configured if str(item).strip())
    if hotel.owner_email:
        recipients.append(hotel.owner_email.strip().lower())
    return sorted(set(recipients))


def daily_report_email_body(report: DailyOperationalReportRead) -> str:
    lines = [
        f"Daily operational report for hotel {report.hotel_id}",
        f"Date: {report.report_date.isoformat()}",
        "",
        f"Arrivals: {report.arrivals.count}",
        f"Departures: {report.departures.count}",
        f"Pending payments: {report.pending_payments.count}",
        f"Late arrivals: {len(report.late_arrivals)}",
        f"Available with review: {len(report.available_with_review)}",
        f"Active room blocks: {len(report.active_room_blocks)}",
        f"Cash session: {report.cash_session.status}",
    ]
    if report.available_with_review:
        lines.append("")
        lines.append("Reservations available with review")
        for item in report.available_with_review:
            lines.append(
                f"- {item.confirmation_code} (room {item.room_number or item.room_id}) "
                f"check-in {item.check_in_date.isoformat()}"
            )
    if report.alerts:
        lines.append("")
        lines.append("Alerts")
        for alert in report.alerts:
            lines.append(f"- [{alert.severity}] {alert.code}: {alert.message}")
    return "\n".join(lines)


def manual_review_alert_body(reservation: Reservation, report_date: date) -> str:
    room = reservation.room
    return "\n".join(
        [
            f"Immediate review required for reservation {reservation.confirmation_code}",
            f"Hotel: {reservation.hotel_id}",
            f"Room: {room.room_number if room else reservation.room_id}",
            f"Check-in: {reservation.check_in_date.isoformat()}",
            f"Check-out: {reservation.check_out_date.isoformat()}",
            f"Allocation status: {reservation.allocation_status}",
            "",
            (
                "This reservation is active today and could not be cleanly allocated. "
                "Please review the room assignment manually."
            ),
        ]
    )


def is_review_for_today(reservation: Reservation, today: date) -> bool:
    """A review is 'for today' when the stay is active on `today`.

    §13.3: reviews affecting a reservation checking in today or already in-house
    today trigger an immediate alert; future reviews wait for the morning report.
    """
    return reservation.check_in_date <= today < reservation.check_out_date


def nightly_summary_email_body(summary: NightlyOperationalSummaryRead) -> str:
    lines = [
        f"Nightly operational summary for hotel {summary.hotel_id}",
        f"Date: {summary.report_date.isoformat()}",
        "",
        f"Alerts: {summary.alert_count}",
        f"Pending payments: {summary.pending_payment_count}",
        f"Late arrivals: {summary.late_arrival_count}",
        f"Available with review: {summary.available_with_review_count}",
        f"Active room blocks: {summary.active_room_block_count}",
        f"Cash session: {summary.cash_session_status}",
    ]
    if summary.alerts:
        lines.append("")
        lines.append("Alerts")
        for alert in summary.alerts:
            lines.append(f"- [{alert.severity}] {alert.code}: {alert.message}")
    return "\n".join(lines)


def route_manual_review(db: Session, reservation: Reservation, *, today: date | None = None) -> bool:
    """§13.3 review routing.

    If the reservation under manual review is active *today*, dispatch an
    immediate alert email to the hotel's configured recipients. Future reviews
    are intentionally left for the morning report (which surfaces them via
    ``_available_with_review``) and this function is a no-op for them.

    Fully best-effort: any failure (no recipients, email error, etc.) is
    swallowed so the calling allocation flow is never aborted.

    Returns True only when an immediate alert was actually sent.
    """
    # Imported lazily to avoid import cycles and to keep the email dependency
    # optional in environments where Gmail is not configured.
    from app.services.hotel_outbound_email_service import (
        HotelOutboundEmailError,
        send_hotel_email,
    )

    try:
        if today is None:
            today = hotel_today(db, reservation.hotel_id)
        if not is_review_for_today(reservation, today):
            return False
        recipients = operational_report_recipients(db, reservation.hotel_id)
        if not recipients:
            logger.info(
                "route_manual_review: no recipients for hotel %s, reservation %s; "
                "deferring to morning report",
                reservation.hotel_id,
                reservation.id,
            )
            return False
        send_hotel_email(
            db,
            reservation.hotel_id,
            to=recipients,
            subject=(
                f"Immediate review required - reservation {reservation.confirmation_code}"
            ),
            body=manual_review_alert_body(reservation, today),
        )
        return True
    except HotelOutboundEmailError as exc:
        logger.warning(
            "route_manual_review: email delivery failed for reservation %s: %s",
            getattr(reservation, "id", None),
            exc,
        )
        return False
    except Exception as exc:  # defensive: never break the allocation flow
        logger.warning(
            "route_manual_review: unexpected failure for reservation %s: %s",
            getattr(reservation, "id", None),
            exc,
        )
        return False
