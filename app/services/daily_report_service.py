"""Build the legacy financial daily-report projection used by its API route."""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.models.hotel_config import HotelConfiguration
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.room import Room
from app.models.transaction import Transaction, TransactionStatusEnum, TransactionTypeEnum
from app.services.operational_report_service import (
    company_night_extra_balances_by_reservation,
    filter_pms_revenue_transactions,
)
from app.services.reservation_service import (
    deferred_company_reservation_ids,
    visible_reservations,
)
from app.services.room_service import active_rooms
from app.services.timezones import hotel_local_date_bounds, hotel_today

if TYPE_CHECKING:
    from app.dependencies.auth import AuthContext


def build_daily_report(db: Session, *, report_date: date, context: AuthContext) -> dict:
    """Return the established daily financial report for the caller's hotel.

    The API route resolves its default date and enforces report permission. The
    caller context is retained here because reservation visibility is bounded by
    the actor's hotel role.
    """
    reservation_scope = visible_reservations(db, context)

    arrivals = reservation_scope.filter(
        Reservation.check_in_date == report_date,
        Reservation.status.notin_([ReservationStatusEnum.CANCELLED]),
    ).all()

    departures = reservation_scope.filter(
        Reservation.check_out_date == report_date,
    ).all()

    in_house = reservation_scope.filter(
        Reservation.check_in_date <= report_date,
        Reservation.check_out_date > report_date,
        Reservation.status.in_([
            ReservationStatusEnum.PARTIAL_CHECK_IN,
            ReservationStatusEnum.CHECKED_IN,
            ReservationStatusEnum.FULLY_PAID,
            ReservationStatusEnum.DEPOSIT_PAID,
            ReservationStatusEnum.PENDING,
        ]),
    ).all()
    deferred_reservation_ids = deferred_company_reservation_ids(
        db,
        hotel_id=context.hotel_id,
        reservations=[*arrivals, *departures, *in_house],
    )
    _extra_totals, extra_due_by_reservation = company_night_extra_balances_by_reservation(
        db,
        hotel_id=context.hotel_id,
        reservation_ids=deferred_reservation_ids,
        stay_date_from=report_date,
        stay_date_to=report_date,
    )

    total_rooms = active_rooms(db, context.hotel_id).filter(Room.is_active.is_(True)).count()
    occupied = len([
        r for r in in_house
        if r.status in {ReservationStatusEnum.PARTIAL_CHECK_IN, ReservationStatusEnum.CHECKED_IN}
    ])

    # ── Revenue today (completed transactions) ──
    hotel = db.get(HotelConfiguration, context.hotel_id)
    timezone_name = (hotel.hotel_timezone if hotel else None) or "UTC"
    day_start, day_end = hotel_local_date_bounds(report_date, report_date, timezone_name)
    today_transactions = (
        db.query(Transaction)
        .filter(
            Transaction.status == TransactionStatusEnum.COMPLETED,
            Transaction.collected_before.is_(False),
            or_(
                and_(Transaction.processed_at >= day_start, Transaction.processed_at < day_end),
                and_(
                    Transaction.processed_at.is_(None),
                    Transaction.created_at >= day_start,
                    Transaction.created_at < day_end,
                ),
            ),
            Transaction.hotel_id == context.hotel_id,
        )
        .all()
    )
    today_transactions = filter_pms_revenue_transactions(
        db,
        hotel_id=context.hotel_id,
        transactions=today_transactions,
    )

    revenue_by_currency: dict[str, Decimal] = {}
    revenue_by_method: dict[tuple[str, str], Decimal] = {}
    for t in today_transactions:
        method = t.payment_method.value
        currency_code = str(t.tender_currency or t.currency or "ARS").strip().upper()
        amount = Decimal(str(t.gross_amount if t.gross_amount is not None else (
            t.tender_amount if t.tender_amount is not None else t.amount
        ))).quantize(Decimal("0.01"))
        if t.transaction_type == TransactionTypeEnum.REFUND:
            amount = -abs(amount)
        else:
            amount = abs(amount)
        revenue_by_currency[currency_code] = revenue_by_currency.get(currency_code, Decimal("0.00")) + amount
        key = (method, currency_code)
        revenue_by_method[key] = revenue_by_method.get(key, Decimal("0.00")) + amount

    revenue_single_currency = len(revenue_by_currency) == 1
    revenue_total_legacy = next(iter(revenue_by_currency.values())) if revenue_single_currency else (
        Decimal("0.00") if not revenue_by_currency else None
    )
    revenue_methods_legacy: dict[str, Decimal] = {}
    if revenue_single_currency:
        single_currency = next(iter(revenue_by_currency))
        revenue_methods_legacy = {
            method: amount
            for (method, currency), amount in revenue_by_method.items()
            if currency == single_currency
        }

    # ── Pending payments ──
    pending_amounts = [
        extra_due_by_reservation.get(r.id, Decimal("0.00"))
        if r.id in deferred_reservation_ids
        else Decimal(str(r.balance_due or 0))
        for r in in_house
    ]
    pending_by_currency: dict[str, Decimal] = {}
    for reservation, amount in zip(in_house, pending_amounts):
        if amount > 0:
            currency_code = str(reservation.currency_code or "ARS").strip().upper()
            pending_by_currency[currency_code] = pending_by_currency.get(currency_code, Decimal("0.00")) + amount
    pending_balance_legacy = next(iter(pending_by_currency.values())) if len(pending_by_currency) == 1 else (
        Decimal("0.00") if not pending_by_currency else None
    )

    # ── No-shows (expected arrival today but not checked in and no cancel) ──
    no_shows = [r for r in arrivals if r.status in (
        ReservationStatusEnum.PENDING,
        ReservationStatusEnum.DEPOSIT_PAID,
        ReservationStatusEnum.FULLY_PAID,
    ) and r.check_in_date < hotel_today(db, context.hotel_id)]

    return {
        "report_date": str(report_date),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "occupancy": {
            "total_rooms": total_rooms,
            "occupied": occupied,
            "available": total_rooms - occupied,
            "occupancy_rate": round(occupied / total_rooms * 100, 1) if total_rooms > 0 else 0,
        },
        "arrivals": {
            "count": len(arrivals),
            "reservations": [
                {
                    "id": r.id,
                    "confirmation_code": r.confirmation_code,
                    "guest_id": r.guest_id,
                    "room_id": r.room_id,
                    "status": r.status.value,
                    "company_billing_deferred": r.id in deferred_reservation_ids,
                    "total_amount": None if r.id in deferred_reservation_ids else r.total_amount,
                    "balance_due": None if r.id in deferred_reservation_ids else r.balance_due,
                    "company_night_extra_due": (
                        extra_due_by_reservation.get(r.id, Decimal("0.00"))
                        if r.id in deferred_reservation_ids
                        else None
                    ),
                }
                for r in arrivals
            ],
        },
        "departures": {
            "count": len(departures),
            "reservations": [
                {
                    "id": r.id,
                    "confirmation_code": r.confirmation_code,
                    "guest_id": r.guest_id,
                    "room_id": r.room_id,
                    "status": r.status.value,
                }
                for r in departures
            ],
        },
        "in_house": {
            "count": len(in_house),
            "checked_in": occupied,
            "expected": len(in_house) - occupied,
        },
        "revenue": {
            "currency_code": next(iter(revenue_by_currency)) if len(revenue_by_currency) == 1 else None,
            "total": revenue_total_legacy,
            "by_method": revenue_methods_legacy,
            "by_currency": [
                {"currency_code": currency, "total": amount}
                for currency, amount in sorted(revenue_by_currency.items())
            ],
            "by_method_by_currency": [
                {"payment_method": method, "currency_code": currency, "total": amount}
                for (method, currency), amount in sorted(revenue_by_method.items())
            ],
            "timezone": timezone_name,
            "transactions_count": len(today_transactions),
        },
        "pending_payments": {
            "currency_code": next(iter(pending_by_currency)) if len(pending_by_currency) == 1 else None,
            "total_balance": pending_balance_legacy,
            "by_currency": [
                {"currency_code": currency, "total_balance": amount}
                for currency, amount in sorted(pending_by_currency.items())
            ],
            "count": sum(1 for amount in pending_amounts if amount > 0),
        },
        "no_shows": {
            "count": len(no_shows),
            "reservations": [
                {"id": r.id, "confirmation_code": r.confirmation_code, "status": r.status.value}
                for r in no_shows
            ],
        },
    }
