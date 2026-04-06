"""
FastAPI routes for Reports & Night Audit.
Daily summaries, occupancy reports, revenue tracking.
"""
from datetime import date, datetime, timezone, timedelta
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.dependencies.auth import AuthContext, require_roles
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.transaction import Transaction, TransactionStatusEnum, PaymentMethodEnum
from app.models.room import Room, RoomCategory
from app.models.guest import Guest

router = APIRouter(prefix="/api/reports", tags=["Reports"])


@router.get("/daily")
def daily_report(
    report_date: date = Query(default=None, description="Date for the report (defaults to today)"),
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
):
    """
    Night Audit / Daily Report.
    Shows arrivals, departures, occupancy, revenue collected, and pending payments for a given date.
    """
    if report_date is None:
        report_date = date.today()

    next_day = report_date + timedelta(days=1)

    reservation_scope = db.query(Reservation).filter(Reservation.hotel_id == context.hotel_id)

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

    total_rooms = db.query(Room).filter(Room.is_active == True, Room.hotel_id == context.hotel_id).count()
    occupied = len([r for r in in_house if r.status == ReservationStatusEnum.CHECKED_IN])

    # ── Revenue today (completed transactions) ──
    day_start = datetime(report_date.year, report_date.month, report_date.day, 0, 0, 0)
    day_end = datetime(report_date.year, report_date.month, report_date.day, 23, 59, 59)
    today_transactions = (
        db.query(Transaction)
        .filter(
            Transaction.status == TransactionStatusEnum.COMPLETED,
            Transaction.created_at >= day_start,
            Transaction.created_at <= day_end,
            Transaction.hotel_id == context.hotel_id,
        )
        .all()
    )

    revenue_by_method = {}
    total_revenue = 0.0
    for t in today_transactions:
        method = t.payment_method.value
        revenue_by_method[method] = revenue_by_method.get(method, 0) + t.amount
        total_revenue += t.amount

    # ── Pending payments ──
    pending_balance = sum(r.balance_due for r in in_house if r.balance_due > 0)

    # ── No-shows (expected arrival today but not checked in and no cancel) ──
    no_shows = [r for r in arrivals if r.status in (
        ReservationStatusEnum.PENDING,
        ReservationStatusEnum.DEPOSIT_PAID,
        ReservationStatusEnum.FULLY_PAID,
    ) and r.check_in_date < date.today()]

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
                    "total_amount": r.total_amount,
                    "balance_due": r.balance_due,
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
            "total": round(total_revenue, 2),
            "by_method": revenue_by_method,
            "transactions_count": len(today_transactions),
        },
        "pending_payments": {
            "total_balance": round(pending_balance, 2),
            "count": len([r for r in in_house if r.balance_due > 0]),
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
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
):
    """Occupancy report for a date range (default: last 30 days)."""
    if start_date is None:
        start_date = date.today() - timedelta(days=30)
    if end_date is None:
        end_date = date.today()

    reservation_scope = db.query(Reservation).filter(Reservation.hotel_id == context.hotel_id)
    total_rooms = db.query(Room).filter(Room.is_active == True, Room.hotel_id == context.hotel_id).count()

    days = []
    current = start_date
    while current <= end_date:
        # Count reservations spanning this date
        occupied_count = reservation_scope.filter(
            Reservation.check_in_date <= current,
            Reservation.check_out_date > current,
            Reservation.status.in_([
                ReservationStatusEnum.CHECKED_IN,
                ReservationStatusEnum.FULLY_PAID,
                ReservationStatusEnum.DEPOSIT_PAID,
                ReservationStatusEnum.PENDING,
            ]),
        ).count()

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


@router.get("/revenue")
def revenue_report(
    start_date: date = Query(default=None),
    end_date: date = Query(default=None),
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
):
    """Revenue report for a date range."""
    if start_date is None:
        start_date = date.today() - timedelta(days=30)
    if end_date is None:
        end_date = date.today()

    reservation_scope = db.query(Reservation).filter(Reservation.hotel_id == context.hotel_id)

    day_start = datetime(start_date.year, start_date.month, start_date.day, 0, 0, 0)
    day_end = datetime(end_date.year, end_date.month, end_date.day, 23, 59, 59)

    transactions = (
        db.query(Transaction)
        .filter(
            Transaction.status == TransactionStatusEnum.COMPLETED,
            Transaction.created_at >= day_start,
            Transaction.created_at <= day_end,
            Transaction.hotel_id == context.hotel_id,
        )
        .order_by(Transaction.created_at)
        .all()
    )

    by_method = {}
    by_day = {}
    total = 0.0

    for t in transactions:
        method = t.payment_method.value
        by_method[method] = round(by_method.get(method, 0) + t.amount, 2)
        day_key = str(t.created_at.date()) if t.created_at else "unknown"
        by_day[day_key] = round(by_day.get(day_key, 0) + t.amount, 2)
        total += t.amount

    # Get all reservations in period for expected revenue
    reservations = reservation_scope.filter(
        Reservation.check_in_date >= start_date,
        Reservation.check_in_date <= end_date,
        Reservation.status.notin_([ReservationStatusEnum.CANCELLED]),
    ).all()
    expected_total = sum(r.total_amount for r in reservations)
    total_pending = sum(r.balance_due for r in reservations)

    return {
        "start_date": str(start_date),
        "end_date": str(end_date),
        "collected": {
            "total": round(total, 2),
            "by_method": by_method,
            "by_day": by_day,
            "transactions_count": len(transactions),
        },
        "expected": {
            "total": round(expected_total, 2),
            "pending": round(total_pending, 2),
            "reservations_count": len(reservations),
        },
    }
