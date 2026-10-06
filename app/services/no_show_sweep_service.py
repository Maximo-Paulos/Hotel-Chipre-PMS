"""Database-only no-show reconciliation shared by Celery and Render Cron."""
from __future__ import annotations

import logging
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session, sessionmaker

from app.database import get_engine
from app.models.hotel_config import HotelConfiguration
from app.models.reservation import Reservation, ReservationStatusEnum
from app.services.reservation_service import ReservationError, mark_reservation_no_show
from app.services.row_locks import lock_query
from app.services.tenant_context import set_tenant_hotel_context
from app.services.timezones import normalize_timezone

logger = logging.getLogger(__name__)

ELIGIBLE_STATUSES = (
    ReservationStatusEnum.PENDING,
    ReservationStatusEnum.DEPOSIT_PAID,
    ReservationStatusEnum.FULLY_PAID,
)


def sweep_no_shows(db: Session, *, hotel_id: int | None = None, now_utc: datetime | None = None) -> dict:
    """Mark eligible, not-arrived reservations after each hotel's local cutoff.

    The cutoff is measured from local midnight on the scheduled check-in date,
    matching the existing analytics no-show detector. This is an operational
    status transition only: payment rows, deposits, refunds, and policy fields
    are not touched.
    """
    current_utc = now_utc or datetime.now(timezone.utc)
    if current_utc.tzinfo is None:
        current_utc = current_utc.replace(tzinfo=timezone.utc)
    else:
        current_utc = current_utc.astimezone(timezone.utc)

    # Reservation lifecycle cleanup must continue even when a hotel's
    # subscription has expired or been canceled; otherwise existing stays can
    # remain indefinitely in an open state.
    hotels_query = db.query(HotelConfiguration.id)
    if hotel_id is not None:
        hotels_query = hotels_query.filter(HotelConfiguration.id == hotel_id)
    hotel_ids = [row[0] for row in hotels_query.order_by(HotelConfiguration.id.asc()).all()]
    totals = {"hotels_scanned": 0, "scanned": 0, "marked": 0, "reservation_ids": []}

    for current_hotel_id in hotel_ids:
        set_tenant_hotel_context(db, current_hotel_id)
        hotel = db.query(HotelConfiguration).filter(
            HotelConfiguration.id == current_hotel_id
        ).one_or_none()
        if hotel is None:
            continue
        try:
            timezone_name = normalize_timezone(hotel.hotel_timezone or "UTC")
        except ValueError:
            timezone_name = "UTC"
        hotel_zone = ZoneInfo(timezone_name)
        cutoff_hours = max(int(hotel.no_show_cutoff_hours), 0)
        eligible_through_local_date = (
            current_utc - timedelta(hours=cutoff_hours)
        ).astimezone(hotel_zone).date()
        candidate_query = (
            db.query(Reservation)
            .filter(
                Reservation.hotel_id == current_hotel_id,
                Reservation.deleted_at.is_(None),
                Reservation.status.in_(ELIGIBLE_STATUSES),
                Reservation.check_in_date <= eligible_through_local_date,
            )
            .order_by(Reservation.check_in_date.asc(), Reservation.id.asc())
        )
        # Reservation has joined eager-loaded nullable relations. A bare
        # FOR UPDATE makes PostgreSQL try to lock the nullable side of those
        # joins and fail; target only the reservation row.
        candidates = lock_query(candidate_query, Reservation).all()
        totals["hotels_scanned"] += 1
        totals["scanned"] += len(candidates)
        for reservation in candidates:
            cutoff_utc = datetime.combine(
                reservation.check_in_date, time.min, tzinfo=hotel_zone
            ).astimezone(timezone.utc) + timedelta(hours=cutoff_hours)
            if current_utc < cutoff_utc:
                continue
            try:
                mark_reservation_no_show(
                    db,
                    reservation,
                    hotel_id=current_hotel_id,
                    client_version=reservation.version,
                    notes="Marcada automáticamente tras el límite de no-show del hotel",
                )
            except ReservationError:
                # Another request may have transitioned the reservation after
                # selection. Leave it unchanged and continue within this hotel.
                logger.info(
                    "no_show_sweep.transition_skipped hotel_id=%s reservation_id=%s",
                    current_hotel_id,
                    reservation.id,
                    exc_info=True,
                )
                continue
            totals["marked"] += 1
            totals["reservation_ids"].append(reservation.id)
        db.flush()
    return totals


def run_no_show_sweep(database_url: str | None = None) -> dict:
    """Run the reconciliation once, committing each hotel's results separately."""
    engine = get_engine(database_url)
    db = sessionmaker(bind=engine)()
    totals = {
        "hotels_scanned": 0,
        "scanned": 0,
        "marked": 0,
        "failed_hotels": 0,
        "reservation_ids": [],
    }
    try:
        # Do not reuse report_tasks._active_hotel_ids: that helper excludes
        # canceled/expired subscriptions, while operational state still needs
        # to reconcile reservations belonging to those hotels.
        hotel_ids = [
            row[0]
            for row in db.query(HotelConfiguration.id).order_by(HotelConfiguration.id.asc()).all()
        ]
        for current_hotel_id in hotel_ids:
            try:
                result = sweep_no_shows(db, hotel_id=current_hotel_id)
                db.commit()
                for key in ("hotels_scanned", "scanned", "marked"):
                    totals[key] += result[key]
                totals["reservation_ids"].extend(result["reservation_ids"])
            except Exception as exc:
                db.rollback()
                totals["failed_hotels"] += 1
                logger.error(
                    "no_show_sweep.hotel_failed hotel_id=%s error_type=%s",
                    current_hotel_id,
                    type(exc).__name__,
                )
        return totals
    finally:
        try:
            db.close()
        finally:
            engine.dispose()
