"""
FastAPI routes for Reports & Night Audit.
Daily summaries, occupancy reports, revenue tracking.
"""
import csv
import io
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal
from fastapi import APIRouter, Depends, Query, HTTPException, Response
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.database import get_db
from app.services.timezones import hotel_today
from app.dependencies.auth import AuthContext, require_permission
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.hotel_config import HotelConfiguration
from app.models.transaction import Transaction, TransactionStatusEnum, TransactionTypeEnum
from app.models.room import Room
from app.schemas.reports import (
    ArrivalCountRead,
    BookedValueRead,
    DailyOperationalReportRead,
    NightlyOperationalSummaryRead,
    OperationalReportDeliveryRead,
    RevenueReportRead,
)
from app.services.financial_report_service import build_booked_value_report, build_financial_report
from app.services.financial_report_service import _hotel_bounds
from app.services.hotel_outbound_email_service import HotelOutboundEmailError, send_hotel_email
from app.services.operational_report_service import (
    company_night_extra_balances_by_reservation,
    daily_report as build_daily_operational_report,
    filter_pms_revenue_transactions,
    nightly_summary as build_nightly_summary,
    nightly_summary_email_body,
    operational_report_recipients,
    redact_daily_report_financials,
    redact_nightly_summary_financials,
    today_arrival_count,
)
from app.services.read_model_cache import get_cached_daily_report_payload
from app.services.reservation_service import (
    active_reservations,
    deferred_company_reservation_ids,
    visible_reservations,
)
from app.services.room_service import active_rooms
from app.services.permission_service import (
    PERMISSION_REPORTS_FINANCIAL_VIEW,
    PERMISSION_REPORTS_OPERATIONAL_VIEW,
    PERMISSION_RESERVATION_READ,
    resolve,
)

router = APIRouter(prefix="/api/reports", tags=["Reports"])


@router.get("/operational/arrivals/count", response_model=ArrivalCountRead)
def operational_today_arrival_count(
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_RESERVATION_READ)),
):
    report_date = hotel_today(db, context.hotel_id)
    return ArrivalCountRead(
        report_date=report_date,
        count=today_arrival_count(db, context.hotel_id, report_date),
    )


@router.get("/operational/daily", response_model=DailyOperationalReportRead)
def operational_daily_report(
    report_date: date = Query(default=None, description="Date for the report (defaults to today)"),
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_REPORTS_OPERATIONAL_VIEW)),
):
    if report_date is None:
        report_date = hotel_today(db, context.hotel_id)
    report = DailyOperationalReportRead.model_validate(
        get_cached_daily_report_payload(
            hotel_id=context.hotel_id,
            report_date=report_date,
            producer=lambda: build_daily_operational_report(db, context.hotel_id, report_date),
        )
    )
    if resolve(db, context.hotel_id, context.user_role, PERMISSION_REPORTS_FINANCIAL_VIEW, user_id=context.user_id):
        return report
    return redact_daily_report_financials(report)


@router.get("/operational/alerts", response_model=NightlyOperationalSummaryRead)
def operational_alerts(
    report_date: date = Query(default=None, description="Date for alerts (defaults to today)"),
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_REPORTS_OPERATIONAL_VIEW)),
):
    if report_date is None:
        report_date = hotel_today(db, context.hotel_id)
    summary = build_nightly_summary(db, context.hotel_id, report_date)
    if resolve(db, context.hotel_id, context.user_role, PERMISSION_REPORTS_FINANCIAL_VIEW, user_id=context.user_id):
        return summary
    return redact_nightly_summary_financials(summary)


@router.post("/operational/nightly-summary/trigger", response_model=OperationalReportDeliveryRead)
def trigger_nightly_summary_delivery(
    report_date: date = Query(default=None, description="Date for the nightly summary (defaults to today)"),
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_REPORTS_OPERATIONAL_VIEW)),
):
    if report_date is None:
        report_date = hotel_today(db, context.hotel_id)
    recipients = operational_report_recipients(db, context.hotel_id)
    if not recipients:
        raise HTTPException(status_code=400, detail="No operational report recipients configured for this hotel")

    summary = build_nightly_summary(db, context.hotel_id, report_date)
    try:
        result = send_hotel_email(
            db,
            context.hotel_id,
            to=recipients,
            subject=f"Nightly operational summary - {report_date.isoformat()}",
            body=nightly_summary_email_body(summary),
        )
    except HotelOutboundEmailError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    response = OperationalReportDeliveryRead(
        delivered=True,
        channel=result.channel,
        sender_email=result.sender_email,
        provider_message_id=result.provider_message_id,
        recipients=recipients,
    )
    if resolve(db, context.hotel_id, context.user_role, PERMISSION_REPORTS_FINANCIAL_VIEW, user_id=context.user_id):
        return response
    return response.model_copy(
        update={
            "channel": None,
            "sender_email": None,
            "provider_message_id": None,
            "recipients": [],
        }
    )


@router.get("/daily")
def daily_report(
    report_date: date = Query(default=None, description="Date for the report (defaults to today)"),
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_REPORTS_FINANCIAL_VIEW)),
):
    """
    Night Audit / Daily Report.
    Shows arrivals, departures, occupancy, revenue collected, and pending payments for a given date.
    """
    if report_date is None:
        report_date = hotel_today(db, context.hotel_id)

    next_day = report_date + timedelta(days=1)

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
    occupied = len([r for r in in_house if r.status == ReservationStatusEnum.CHECKED_IN])

    # ── Revenue today (completed transactions) ──
    hotel = db.get(HotelConfiguration, context.hotel_id)
    timezone_name = (hotel.hotel_timezone if hotel else None) or "UTC"
    day_start, day_end = _hotel_bounds(report_date, report_date, timezone_name)
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


@router.get("/occupancy")
def occupancy_report(
    start_date: date = Query(default=None),
    end_date: date = Query(default=None),
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_REPORTS_OPERATIONAL_VIEW)),
):
    """Occupancy report for a date range (default: last 30 days)."""
    if start_date is None:
        start_date = hotel_today(db, context.hotel_id) - timedelta(days=30)
    if end_date is None:
        end_date = hotel_today(db, context.hotel_id)
    # The sweep-line below materializes one row per overlapping reservation,
    # not per day, so an unbounded range on a hotel with a long history could
    # still pull an unbounded result set into memory. Cap the window instead
    # of aggregating deltas in SQL, since a portable GREATEST/LEAST clamp
    # across SQLite and PostgreSQL isn't worth the complexity for a
    # dashboard report.
    if (end_date - start_date).days > 366:
        raise HTTPException(status_code=422, detail="Date range must not exceed 366 days")

    reservation_scope = active_reservations(db, context.hotel_id)
    total_rooms = active_rooms(db, context.hotel_id).filter(Room.is_active.is_(True)).count()

    # Load the overlap candidates once. The previous implementation issued one
    # COUNT query per day in the requested range, making a 30-day dashboard
    # request 30 additional round trips. A sweep-line over date deltas keeps
    # the same half-open stay semantics (check-in included, check-out excluded)
    # with a fixed query count.
    occupancy_candidates = reservation_scope.with_entities(
        Reservation.check_in_date,
        Reservation.check_out_date,
    ).filter(
        Reservation.check_in_date <= end_date,
        Reservation.check_out_date > start_date,
        Reservation.status.in_([
            ReservationStatusEnum.CHECKED_IN,
            ReservationStatusEnum.PRE_CHECK_IN,
            ReservationStatusEnum.FULLY_PAID,
            ReservationStatusEnum.DEPOSIT_PAID,
            ReservationStatusEnum.PENDING,
        ]),
    ).all()
    occupancy_deltas: dict[date, int] = {}
    for candidate in occupancy_candidates:
        active_from = max(candidate.check_in_date, start_date)
        active_until = min(candidate.check_out_date, end_date + timedelta(days=1))
        occupancy_deltas[active_from] = occupancy_deltas.get(active_from, 0) + 1
        occupancy_deltas[active_until] = occupancy_deltas.get(active_until, 0) - 1

    days = []
    occupied_count = 0
    current = start_date
    while current <= end_date:
        occupied_count += occupancy_deltas.get(current, 0)

        days.append({
            "date": str(current),
            "occupied": occupied_count,
            "available": total_rooms - occupied_count,
            "rate": round(occupied_count / total_rooms * 100, 1) if total_rooms > 0 else 0,
        })
        current += timedelta(days=1)

    avg_occ = sum(d["rate"] for d in days) / len(days) if days else 0

    return {
        "start_date": str(start_date),
        "end_date": str(end_date),
        "total_rooms": total_rooms,
        "average_occupancy": round(avg_occ, 1),
        "daily": days,
    }


@router.get("/revenue", response_model=RevenueReportRead)
def revenue_report(
    start_date: date = Query(default=None),
    end_date: date = Query(default=None),
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_REPORTS_FINANCIAL_VIEW)),
):
    """Show hotel collections, OTA collections, booked value, and receivables separately."""
    if start_date is None:
        start_date = hotel_today(db, context.hotel_id) - timedelta(days=30)
    if end_date is None:
        end_date = hotel_today(db, context.hotel_id)

    try:
        return build_financial_report(
            db,
            hotel_id=context.hotel_id,
            start_date=start_date,
            end_date=end_date,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/booked-value", response_model=BookedValueRead)
def booked_value_report(
    start_date: date = Query(default=None),
    end_date: date = Query(default=None),
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_REPORTS_FINANCIAL_VIEW)),
):
    """Return the lightweight booked-value KPI without building the full finance report."""
    if start_date is None or end_date is None:
        default_date = hotel_today(db, context.hotel_id)
        if start_date is None:
            start_date = default_date - timedelta(days=30)
        if end_date is None:
            end_date = default_date
    try:
        return build_booked_value_report(
            db,
            hotel_id=context.hotel_id,
            start_date=start_date,
            end_date=end_date,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _safe_csv_cell(value: object) -> str:
    text = "" if value is None else str(value)
    if text.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + text
    return text


@router.get("/revenue/export.csv")
def export_revenue_report_csv(
    start_date: date = Query(default=None),
    end_date: date = Query(default=None),
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_REPORTS_FINANCIAL_VIEW)),
):
    """Export collected amounts grouped by method/category/channel/currency."""
    if start_date is None:
        start_date = hotel_today(db, context.hotel_id) - timedelta(days=30)
    if end_date is None:
        end_date = hotel_today(db, context.hotel_id)
    try:
        report = build_financial_report(
            db,
            hotel_id=context.hotel_id,
            start_date=start_date,
            end_date=end_date,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow([
        "tipo", "medio_de_pago", "categoria", "canal", "moneda",
        "cobrado_bruto", "devoluciones", "cobrado_neto", "operaciones",
    ])
    for item in report["collected"]["by_combination"]:
        writer.writerow([
            "cobro_en_hotel",
            _safe_csv_cell(item["payment_method"]),
            _safe_csv_cell(item["category_name"]),
            _safe_csv_cell(item["channel_code"]),
            _safe_csv_cell(item["currency_code"]),
            item["gross_collected"],
            item["refunds"],
            item["net_collected"],
            item["transaction_count"],
        ])
    for item in report["external_ota_collected"]["by_combination"]:
        writer.writerow([
            "cobro_externo_ota", "fuera_de_caja", _safe_csv_cell(item["category_name"]), _safe_csv_cell(item["channel_code"]),
            _safe_csv_cell(item["currency_code"]), item["amount"], 0, item["amount"], "",
        ])
    for item in report["booked_value"]["by_currency"]:
        writer.writerow([
            "valor_reservado_periodo", "no_es_cobro", "", "", _safe_csv_cell(item["currency_code"]),
            item["amount"], 0, item["amount"], item["reservation_count"],
        ])

    filename = f"reporte-financiero-{start_date.isoformat()}-{end_date.isoformat()}.csv"
    return Response(
        content=output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
