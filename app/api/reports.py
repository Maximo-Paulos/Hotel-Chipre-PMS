"""
FastAPI routes for Reports & Night Audit.
Daily summaries, occupancy reports, revenue tracking.
"""
import csv
import io
from datetime import date, timedelta
from fastapi import APIRouter, Depends, Query, HTTPException, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.timezones import hotel_today
from app.dependencies.auth import AuthContext, require_permission
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.room import Room
from app.schemas.reports import (
    ArrivalCountRead,
    BookedValueRead,
    DailyOperationalReportRead,
    NightlyOperationalSummaryRead,
    OperationalReportDeliveryRead,
    RevenueReportRead,
)
from app.services.daily_report_service import build_daily_report
from app.services.financial_report_service import build_booked_value_report, build_financial_report
from app.services.hotel_outbound_email_service import HotelOutboundEmailError, send_hotel_email
from app.services.operational_report_service import (
    daily_report as build_daily_operational_report,
    nightly_summary as build_nightly_summary,
    nightly_summary_email_body,
    operational_report_recipients,
    redact_daily_report_financials,
    redact_nightly_summary_financials,
    today_arrival_count,
)
from app.services.read_model_cache import get_cached_daily_report_payload
from app.services.reservation_service import active_reservations
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
    pending_page: int = Query(default=1, ge=1),
    pending_page_size: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_REPORTS_OPERATIONAL_VIEW)),
):
    if report_date is None:
        report_date = hotel_today(db, context.hotel_id)
    report = DailyOperationalReportRead.model_validate(
        get_cached_daily_report_payload(
            hotel_id=context.hotel_id,
            report_date=report_date,
            pending_page=pending_page,
            pending_page_size=pending_page_size,
            producer=lambda: build_daily_operational_report(
                db,
                context.hotel_id,
                report_date,
                pending_page=pending_page,
                pending_page_size=pending_page_size,
            ),
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
    return build_daily_report(db, report_date=report_date, context=context)


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
    active_room_ids = active_rooms(db, context.hotel_id).filter(Room.is_active.is_(True)).with_entities(Room.id)
    occupancy_candidates = reservation_scope.with_entities(
        Reservation.room_id,
        Reservation.check_in_date,
        Reservation.check_out_date,
    ).filter(
        Reservation.room_id.is_not(None),
        Reservation.room_id.in_(active_room_ids),
        Reservation.is_wait_listed.is_(False),
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
    occupancy_deltas: dict[date, dict[int, int]] = {}
    for candidate in occupancy_candidates:
        active_from = max(candidate.check_in_date, start_date)
        active_until = min(candidate.check_out_date, end_date + timedelta(days=1))
        room_id = int(candidate.room_id)
        start_deltas = occupancy_deltas.setdefault(active_from, {})
        start_deltas[room_id] = start_deltas.get(room_id, 0) + 1
        end_deltas = occupancy_deltas.setdefault(active_until, {})
        end_deltas[room_id] = end_deltas.get(room_id, 0) - 1

    days = []
    occupied_count = 0
    reservation_count_by_room: dict[int, int] = {}
    current = start_date
    while current <= end_date:
        for room_id, delta in occupancy_deltas.get(current, {}).items():
            before = reservation_count_by_room.get(room_id, 0)
            after = before + delta
            if before <= 0 < after:
                occupied_count += 1
            elif before > 0 >= after:
                occupied_count -= 1
            if after > 0:
                reservation_count_by_room[room_id] = after
            else:
                reservation_count_by_room.pop(room_id, None)

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
