"""Financial report projections over the reservation and transaction ledgers.

Amounts stay in their source currency. This module never applies FX.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.models.hotel_config import HotelConfiguration
from app.models.reservation import Reservation, ReservationStatusEnum, reportable_origin
from app.models.room import RoomCategory
from app.models.transaction import Transaction, TransactionStatusEnum, TransactionTypeEnum
from app.services.operational_report_service import (
    billing_adjustment_totals_by_reservation,
    company_night_extra_balances_by_reservation,
    filter_pms_revenue_transactions,
    paid_amounts_by_reservation,
)
from app.services.reservation_service import deferred_company_reservation_ids
from app.services.timezones import normalize_timezone
from app.services.analytics_contracts import split_amount_evenly


ZERO = Decimal("0.00")


def _money(value: object) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("0.01"))


def _hotel_bounds(start_date: date, end_date: date, timezone_name: str) -> tuple[datetime, datetime]:
    zone = ZoneInfo(normalize_timezone(timezone_name))
    start = datetime.combine(start_date, time.min, tzinfo=zone).astimezone(timezone.utc)
    end = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=zone).astimezone(timezone.utc)
    # Transaction DateTime columns are timezone-naive but store UTC.
    return start.replace(tzinfo=None), end.replace(tzinfo=None)


def _local_day(value: datetime | None, timezone_name: str) -> date | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(ZoneInfo(timezone_name)).date()


def _aggregate_rows(rows: dict, *, group_fields: tuple[str, ...]) -> list[dict]:
    output = []
    for key, values in sorted(rows.items(), key=lambda item: tuple(str(part) for part in item[0])):
        record = dict(zip(group_fields, key))
        record.update({
            "gross_collected": _money(values["gross_collected"]),
            "refunds": _money(values["refunds"]),
            "net_collected": _money(values["net_collected"]),
            "transaction_count": int(values["transaction_count"]),
        })
        output.append(record)
    return output


def _empty_totals() -> dict[str, Decimal | int]:
    return {"gross_collected": ZERO, "refunds": ZERO, "net_collected": ZERO, "transaction_count": 0}


def _booked_nights_in_window(reservation: Reservation, *, start_date: date, end_date: date) -> int:
    overlap_start = max(reservation.check_in_date, start_date)
    overlap_end = min(reservation.check_out_date, end_date + timedelta(days=1))
    return max(0, (overlap_end - overlap_start).days)


def _booked_amount_in_window(reservation: Reservation, *, start_date: date, end_date: date) -> Decimal:
    """Allocate a contract total over its full stay, then sum only selected nights."""
    full_nights = max((reservation.check_out_date - reservation.check_in_date).days, 1)
    window_nights = _booked_nights_in_window(reservation, start_date=start_date, end_date=end_date)
    if window_nights <= 0:
        return ZERO
    first_night = max((start_date - reservation.check_in_date).days, 0)
    nightly_amounts = split_amount_evenly(_money(reservation.total_amount), full_nights)
    return sum(nightly_amounts[first_night:first_night + window_nights], ZERO)


def _validate_report_window(*, start_date: date, end_date: date) -> None:
    if end_date < start_date:
        raise ValueError("La fecha final debe ser igual o posterior a la inicial")
    if (end_date - start_date).days > 366:
        raise ValueError("El período no puede superar 366 días")


def _build_booked_value_projection(
    db: Session,
    *,
    hotel_id: int,
    reservations: list[Reservation],
    start_date: date,
    end_date: date,
) -> tuple[dict, set[int]]:
    """Build the booked-value contract and return its deferred reservation IDs."""
    deferred_ids = deferred_company_reservation_ids(
        db,
        hotel_id=hotel_id,
        reservations=reservations,
    )
    booked_by_currency: dict[str, Decimal] = defaultdict(lambda: ZERO)
    booked_count_by_currency: dict[str, int] = defaultdict(int)
    booked_night_count_by_currency: dict[str, int] = defaultdict(int)
    for reservation in reservations:
        if reservation.id in deferred_ids:
            continue
        currency = str(reservation.currency_code or "ARS").strip().upper()
        booked_by_currency[currency] += _booked_amount_in_window(
            reservation,
            start_date=start_date,
            end_date=end_date,
        )
        booked_count_by_currency[currency] += 1
        booked_night_count_by_currency[currency] += _booked_nights_in_window(
            reservation,
            start_date=start_date,
            end_date=end_date,
        )

    currencies = [
        {
            "currency_code": currency,
            "amount": _money(amount),
            "reservation_count": booked_count_by_currency[currency],
            "booked_night_count": booked_night_count_by_currency[currency],
        }
        for currency, amount in sorted(booked_by_currency.items())
    ]
    return {
        "total": currencies[0]["amount"] if len(currencies) == 1 else None,
        "currency_code": currencies[0]["currency_code"] if len(currencies) == 1 else None,
        "by_currency": currencies,
    }, deferred_ids


def build_booked_value_report(
    db: Session,
    *,
    hotel_id: int,
    start_date: date,
    end_date: date,
) -> dict:
    """Return only the booked-value projection used by the dashboard KPIs."""
    _validate_report_window(start_date=start_date, end_date=end_date)
    reservations = (
        db.query(
            Reservation.id,
            Reservation.hotel_id,
            Reservation.company_id,
            Reservation.settlement_status,
            Reservation.check_in_date,
            Reservation.check_out_date,
            Reservation.total_amount,
            Reservation.currency_code,
        )
        .filter(
            Reservation.hotel_id == hotel_id,
            Reservation.deleted_at.is_(None),
            Reservation.check_in_date <= end_date,
            Reservation.check_out_date > start_date,
            Reservation.status.notin_([ReservationStatusEnum.CANCELLED, ReservationStatusEnum.NO_SHOW]),
        )
        .all()
    )
    booked_value, _deferred_ids = _build_booked_value_projection(
        db,
        hotel_id=hotel_id,
        reservations=reservations,
        start_date=start_date,
        end_date=end_date,
    )
    return booked_value


def build_financial_report(
    db: Session,
    *,
    hotel_id: int,
    start_date: date,
    end_date: date,
) -> dict:
    _validate_report_window(start_date=start_date, end_date=end_date)

    hotel = db.get(HotelConfiguration, hotel_id)
    timezone_name = normalize_timezone((hotel.hotel_timezone if hotel else None) or "UTC")
    utc_start, utc_end = _hotel_bounds(start_date, end_date, timezone_name)
    current_date = datetime.now(ZoneInfo(timezone_name)).date()

    transaction_date_filter = or_(
        and_(
            Transaction.collected_before.is_(False),
            Transaction.processed_at >= utc_start,
            Transaction.processed_at < utc_end,
        ),
        and_(
            Transaction.collected_before.is_(False),
            Transaction.processed_at.is_(None),
            Transaction.created_at >= utc_start,
            Transaction.created_at < utc_end,
        ),
        and_(
            Transaction.collected_before.is_(True),
            Transaction.collected_on >= start_date,
            Transaction.collected_on <= end_date,
        ),
    )
    transactions = (
        db.query(Transaction)
        .filter(
            Transaction.hotel_id == hotel_id,
            Transaction.status == TransactionStatusEnum.COMPLETED,
            transaction_date_filter,
        )
        .order_by(Transaction.processed_at.asc(), Transaction.created_at.asc(), Transaction.id.asc())
        .all()
    )
    transactions = filter_pms_revenue_transactions(db, hotel_id=hotel_id, transactions=transactions)
    reservation_ids = {int(item.reservation_id) for item in transactions}
    report_reservations = (
        db.query(Reservation)
        .filter(Reservation.hotel_id == hotel_id, Reservation.id.in_(reservation_ids))
        .all()
        if reservation_ids
        else []
    )
    reservations_by_id = {item.id: item for item in report_reservations}
    category_ids = {item.category_id for item in report_reservations if item.category_id is not None}
    categories = (
        db.query(RoomCategory)
        .filter(RoomCategory.hotel_id == hotel_id, RoomCategory.id.in_(category_ids))
        .all()
        if category_ids
        else []
    )
    category_names = {item.id: item.name for item in categories}

    by_currency: dict[str, dict] = defaultdict(_empty_totals)
    by_method: dict[tuple[str, str], dict] = defaultdict(_empty_totals)
    by_category: dict[tuple[str, str, str], dict] = defaultdict(_empty_totals)
    by_channel: dict[tuple[str, str, str], dict] = defaultdict(_empty_totals)
    by_day: dict[tuple[str, str], Decimal] = defaultdict(lambda: ZERO)
    by_combination: dict[tuple[str, str, str, str], dict] = defaultdict(_empty_totals)

    for transaction in transactions:
        reservation = reservations_by_id.get(transaction.reservation_id)
        if reservation is None:
            continue
        currency_code = str(transaction.tender_currency or transaction.currency or "ARS").strip().upper()
        method = transaction.payment_method.value if hasattr(transaction.payment_method, "value") else str(transaction.payment_method)
        category_id = str(reservation.category_id) if reservation.category_id is not None else ""
        category_name = category_names.get(reservation.category_id, "Sin categoría")
        origin_value = reportable_origin(reservation)
        channel = origin_value.value if hasattr(origin_value, "value") else str(origin_value)
        amount = abs(_money(transaction.gross_amount if transaction.gross_amount is not None else (
            transaction.tender_amount if transaction.tender_amount is not None else transaction.amount
        )))
        is_refund = transaction.transaction_type == TransactionTypeEnum.REFUND
        signed = -amount if is_refund else amount
        targets = (
            by_currency[currency_code],
            by_method[(method, currency_code)],
            by_category[(category_id, category_name, currency_code)],
            by_channel[(channel, channel, currency_code)],
            by_combination[(method, category_name, channel, currency_code)],
        )
        for row in targets:
            if is_refund:
                row["refunds"] += amount
            else:
                row["gross_collected"] += amount
            row["net_collected"] += signed
            row["transaction_count"] += 1
        transaction_date = (
            transaction.collected_on
            if transaction.collected_before
            else _local_day(transaction.processed_at or transaction.created_at, timezone_name)
        )
        if transaction_date is not None:
            by_day[(transaction_date.isoformat(), currency_code)] += signed

    collected_currencies = [
        {"currency_code": currency, **{key: _money(value) if key != "transaction_count" else int(value) for key, value in row.items()}}
        for currency, row in sorted(by_currency.items())
    ]
    unique_collected_currencies = len(collected_currencies) == 1
    collected_total = collected_currencies[0]["net_collected"] if unique_collected_currencies else None
    legacy_by_method: dict[str, Decimal] = {}
    legacy_by_day: dict[str, Decimal] = {}
    if unique_collected_currencies:
        report_currency = collected_currencies[0]["currency_code"]
        legacy_by_method = {
            method: _money(values["net_collected"])
            for (method, currency), values in by_method.items()
            if currency == report_currency
        }
        legacy_by_day = {
            day: _money(amount)
            for (day, currency), amount in by_day.items()
            if currency == report_currency
        }

    # Booked room value is not revenue recognized or money collected. Keep it
    # as a separate reservation measure and group it by the reservation currency.
    booked_reservations = (
        db.query(Reservation)
        .filter(
            Reservation.hotel_id == hotel_id,
            Reservation.deleted_at.is_(None),
            Reservation.check_in_date <= end_date,
            Reservation.check_out_date > start_date,
            Reservation.status.notin_([ReservationStatusEnum.CANCELLED, ReservationStatusEnum.NO_SHOW]),
        )
        .all()
    )
    booked_value, booked_deferred_ids = _build_booked_value_projection(
        db,
        hotel_id=hotel_id,
        reservations=booked_reservations,
        start_date=start_date,
        end_date=end_date,
    )

    # Deprecated compatibility projection. Historically `expected` included
    # lodging value for non-deferred stays and selected company-night charges
    # for deferred stays. Keep that contract, with currency groups so unlike
    # amounts are never combined. New consumers should use booked_value and
    # receivables, which name the two different measures explicitly.
    expected_by_currency: dict[str, dict[str, Decimal | int]] = defaultdict(
        lambda: {"total": ZERO, "pending": ZERO, "reservations_count": 0}
    )
    booked_reservation_ids = {item.id for item in booked_reservations}
    expected_paid = paid_amounts_by_reservation(db, hotel_id, booked_reservation_ids)
    expected_adjustments = billing_adjustment_totals_by_reservation(
        db, hotel_id, booked_reservation_ids
    )
    for reservation in booked_reservations:
        currency = str(reservation.currency_code or "ARS").strip().upper()
        metrics = expected_by_currency[currency]
        metrics["reservations_count"] += 1
        if reservation.id in booked_deferred_ids:
            continue
        base_value = _money(reservation.total_amount)
        metrics["total"] += base_value
        metrics["pending"] += max(
            ZERO,
            base_value
            + _money(expected_adjustments.get(reservation.id, ZERO))
            - _money(expected_paid.get(reservation.id, ZERO)),
        )

    selected_company_ids = booked_deferred_ids.intersection(booked_reservation_ids)
    company_extra_totals, company_extra_due = company_night_extra_balances_by_reservation(
        db,
        hotel_id=hotel_id,
        reservation_ids=selected_company_ids,
        stay_date_from=start_date,
        stay_date_to=end_date,
    )
    currency_by_reservation = {
        item.id: str(item.currency_code or "ARS").strip().upper()
        for item in booked_reservations
    }
    for reservation_id, amount in company_extra_totals.items():
        expected_by_currency[currency_by_reservation[reservation_id]]["total"] += _money(amount)
    for reservation_id, amount in company_extra_due.items():
        expected_by_currency[currency_by_reservation[reservation_id]]["pending"] += _money(amount)
    expected_currencies = [
        {
            "currency_code": currency,
            "total": _money(values["total"]),
            "pending": _money(values["pending"]),
            "reservations_count": int(values["reservations_count"]),
        }
        for currency, values in sorted(expected_by_currency.items())
    ]
    expected_single_currency = len(expected_currencies) == 1
    expected_legacy_total = expected_currencies[0]["total"] if expected_single_currency else (
        ZERO if not expected_currencies else None
    )
    expected_legacy_pending = expected_currencies[0]["pending"] if expected_single_currency else (
        ZERO if not expected_currencies else None
    )
    expected_legacy_count = sum(item["reservations_count"] for item in expected_currencies)

    # Confirmed external OTA collections are reported separately from PMS
    # transactions and physical cash, in the currency the OTA actually paid.
    # The report deliberately does not convert amounts between currencies.
    external_rows = (
        db.query(Reservation)
        .filter(
            Reservation.hotel_id == hotel_id,
            Reservation.deleted_at.is_(None),
            Reservation.external_paid_confirmed.is_(True),
            Reservation.external_paid_amount > 0,
            Reservation.external_paid_confirmed_at >= utc_start,
            Reservation.external_paid_confirmed_at < utc_end,
        )
        .all()
    )
    external_category_ids = {
        item.category_id for item in external_rows if item.category_id is not None
    }
    if external_category_ids:
        external_categories = (
            db.query(RoomCategory)
            .filter(
                RoomCategory.hotel_id == hotel_id,
                RoomCategory.id.in_(external_category_ids),
            )
            .all()
        )
        category_names.update({item.id: item.name for item in external_categories})
    external_by_currency: dict[str, Decimal] = defaultdict(lambda: ZERO)
    external_by_channel: dict[tuple[str, str], Decimal] = defaultdict(lambda: ZERO)
    external_by_category: dict[tuple[str, str], Decimal] = defaultdict(lambda: ZERO)
    external_by_combination: dict[tuple[str, str, str], Decimal] = defaultdict(lambda: ZERO)
    for reservation in external_rows:
        currency = str(
            getattr(reservation, "external_paid_currency", None)
            or reservation.currency_code
            or "ARS"
        ).strip().upper()
        origin_value = reportable_origin(reservation)
        channel = origin_value.value if hasattr(origin_value, "value") else str(origin_value)
        category_name = category_names.get(reservation.category_id, "Sin categoría")
        amount = _money(reservation.external_paid_amount)
        external_by_currency[currency] += amount
        external_by_channel[(channel, currency)] += amount
        external_by_category[(category_name, currency)] += amount
        external_by_combination[(channel, category_name, currency)] += amount

    # Portfolio receivables are a current snapshot, not a historical balance
    # reconstructed from today's transaction state for the selected period.
    receivable_reservations = (
        db.query(Reservation)
        .filter(
            Reservation.hotel_id == hotel_id,
            Reservation.deleted_at.is_(None),
            Reservation.status.notin_([ReservationStatusEnum.CANCELLED, ReservationStatusEnum.NO_SHOW]),
        )
        .all()
    )
    deferred_ids = deferred_company_reservation_ids(
        db, hotel_id=hotel_id, reservations=receivable_reservations
    )
    receivable_ids = {item.id for item in receivable_reservations}
    paid_by_reservation = paid_amounts_by_reservation(db, hotel_id, receivable_ids)
    adjustments_by_reservation = billing_adjustment_totals_by_reservation(db, hotel_id, receivable_ids)
    receivables_by_currency: dict[str, dict[str, Decimal]] = defaultdict(
        lambda: {
            "overdue": ZERO,
            "due_at_check_in": ZERO,
            "due_today_company_nights": ZERO,
            "future": ZERO,
        }
    )
    for reservation in receivable_reservations:
        if reservation.id in deferred_ids:
            continue
        due = max(
            ZERO,
            _money(reservation.total_amount)
            + _money(adjustments_by_reservation.get(reservation.id, ZERO))
            - _money(paid_by_reservation.get(reservation.id, ZERO)),
        )
        if due <= ZERO:
            continue
        currency = str(reservation.currency_code or "ARS").strip().upper()
        bucket = "overdue" if reservation.check_in_date < current_date else (
            "due_at_check_in" if reservation.check_in_date == current_date else "future"
        )
        receivables_by_currency[currency][bucket] += due

    deferred_receivable_ids = deferred_ids.intersection(receivable_ids)
    company_ranges = (
        ("overdue", date.min, current_date - timedelta(days=1)),
        ("due_today_company_nights", current_date, current_date),
        ("future", current_date + timedelta(days=1), date.max),
    )
    for bucket, charge_start, charge_end in company_ranges:
        if charge_start > charge_end or not deferred_receivable_ids:
            continue
        _charge_totals, charge_due = company_night_extra_balances_by_reservation(
            db,
            hotel_id=hotel_id,
            reservation_ids=deferred_receivable_ids,
            stay_date_from=charge_start,
            stay_date_to=charge_end,
        )
        currencies_by_reservation = {
            item.id: str(item.currency_code or "ARS").strip().upper()
            for item in receivable_reservations
        }
        for reservation_id, amount in charge_due.items():
            currency = currencies_by_reservation.get(reservation_id, "ARS")
            receivables_by_currency[currency][bucket] += _money(amount)

    receivable_currencies = []
    for currency, amounts in sorted(receivables_by_currency.items()):
        total = sum(amounts.values(), ZERO)
        receivable_currencies.append({
            "currency_code": currency,
            **{key: _money(value) for key, value in amounts.items()},
            "total": _money(total),
        })

    return {
        "start_date": start_date,
        "end_date": end_date,
        "timezone": timezone_name,
        "receivables_as_of": current_date,
        "collected": {
            "currency_code": collected_currencies[0]["currency_code"] if unique_collected_currencies else None,
            "total": collected_total if unique_collected_currencies else (ZERO if not collected_currencies else None),
            "by_method": legacy_by_method,
            "by_day": legacy_by_day,
            "by_currency": collected_currencies,
            "by_method_by_currency": _aggregate_rows(by_method, group_fields=("payment_method", "currency_code")),
            "by_category": _aggregate_rows(by_category, group_fields=("category_id", "category_name", "currency_code")),
            "by_channel": _aggregate_rows(by_channel, group_fields=("channel_code", "channel_label", "currency_code")),
            "by_day_by_currency": [
                {"date": day, "currency_code": currency, "net_collected": _money(amount)}
                for (day, currency), amount in sorted(by_day.items())
            ],
            "by_combination": _aggregate_rows(
                by_combination,
                group_fields=("payment_method", "category_name", "channel_code", "currency_code"),
            ),
            "transactions_count": sum(int(row["transaction_count"]) for row in collected_currencies),
        },
        "expected": {
            "total": expected_legacy_total,
            "pending": expected_legacy_pending,
            "reservations_count": expected_legacy_count,
            "currency_code": expected_currencies[0]["currency_code"] if expected_single_currency else None,
            "by_currency": expected_currencies,
        },
        "booked_value": {
            **booked_value,
        },
        "external_ota_collected": {
            "by_currency": [
                {"currency_code": currency, "amount": _money(amount)}
                for currency, amount in sorted(external_by_currency.items())
            ],
            "by_channel": [
                {"channel_code": channel, "currency_code": currency, "amount": _money(amount)}
                for (channel, currency), amount in sorted(external_by_channel.items())
            ],
            "by_category": [
                {"category_name": category, "currency_code": currency, "amount": _money(amount)}
                for (category, currency), amount in sorted(external_by_category.items())
            ],
            "by_combination": [
                {
                    "channel_code": channel,
                    "category_name": category,
                    "currency_code": currency,
                    "amount": _money(amount),
                }
                for (channel, category, currency), amount in sorted(external_by_combination.items())
            ],
        },
        "receivables": {"by_currency": receivable_currencies},
    }
