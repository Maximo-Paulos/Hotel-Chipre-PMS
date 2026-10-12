"""Bounded SQL-only scheduled work, isolated by hotel and job."""
from __future__ import annotations

import logging
from typing import Callable

from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.database import get_engine
from app.models.hotel_config import HotelConfiguration
from app.services.analytics_fact_refresh_queue import process_analytics_fact_refresh_queue_for_hotel
from app.services.no_show_sweep_service import sweep_no_shows
from app.services.notification_service import generate_due_daily_reports, process_pending_outbox
from app.services.tenant_context import set_tenant_hotel_context

logger = logging.getLogger(__name__)


def process_scheduled_hotel_jobs(db: Session) -> dict[str, int]:
    """Run no-show, due-report, and outbox work once per hotel.

    The hotel inventory is read once for the whole cycle. Each operation then
    runs under that hotel's RLS context and a savepoint so one failed job does
    not discard other work for the hotel or stop the remaining hotels.
    Reports and outbox delivery stay limited to hotels with an active
    subscription, matching the existing notification task behavior. No-show
    reconciliation continues for every hotel so an expired subscription does
    not strand an existing reservation.
    """
    hotel_rows = (
        db.query(HotelConfiguration.id, HotelConfiguration.subscription_active)
        .order_by(HotelConfiguration.id.asc())
        .all()
    )
    db.commit()

    totals = {
        "hotels_scanned": 0,
        "active_hotels_scanned": 0,
        "no_shows_scanned": 0,
        "no_shows_marked": 0,
        "reports_generated": 0,
        "notifications_processed": 0,
        "notifications_sent": 0,
        "notifications_failed": 0,
        "notifications_expired": 0,
        "notifications_retried": 0,
        "notifications_deferred": 0,
        "analytics_facts_processed": 0,
        "analytics_facts_deferred": 0,
        "failed_jobs": 0,
        "failed_hotels": 0,
    }
    totals["hotels_scanned"] = len(hotel_rows)

    for hotel_id, subscription_active in hotel_rows:
        set_tenant_hotel_context(db, hotel_id)
        if subscription_active:
            totals["active_hotels_scanned"] += 1

        jobs: list[tuple[str, Callable[[], object]]] = [
            (
                "analytics_fact_refresh",
                lambda hotel_id=hotel_id: process_analytics_fact_refresh_queue_for_hotel(
                    db,
                    hotel_id=hotel_id,
                    batch_size=50,
                ),
            ),
            (
                "no_show",
                lambda hotel_id=hotel_id: sweep_no_shows(
                    db,
                    hotel_id=hotel_id,
                    tenant_context_already_set=True,
                ),
            ),
        ]
        if subscription_active:
            jobs.extend(
                [
                    ("daily_reports", lambda: generate_due_daily_reports(db)),
                    ("notification_outbox", lambda: process_pending_outbox(db)),
                ]
            )

        hotel_failed = False
        for job_name, run_job in jobs:
            try:
                with db.begin_nested():
                    result = run_job()
                if job_name == "no_show" and isinstance(result, dict):
                    totals["no_shows_scanned"] += int(result.get("scanned", 0))
                    totals["no_shows_marked"] += int(result.get("marked", 0))
                elif job_name == "daily_reports" and isinstance(result, list):
                    totals["reports_generated"] += len(result)
                elif job_name == "notification_outbox" and isinstance(result, dict):
                    for key in (
                        "processed",
                        "sent",
                        "failed",
                        "expired",
                        "retried",
                        "deferred",
                    ):
                        totals[f"notifications_{key}"] += int(result.get(key, 0))
                elif job_name == "analytics_fact_refresh" and isinstance(result, dict):
                    totals["analytics_facts_processed"] += int(result.get("processed", 0))
                    totals["analytics_facts_deferred"] += int(result.get("deferred", 0))
            except Exception as exc:
                hotel_failed = True
                totals["failed_jobs"] += 1
                logger.warning(
                    "scheduled_hotel_jobs.job_failed hotel_id=%s job=%s error_type=%s",
                    hotel_id,
                    job_name,
                    type(exc).__name__,
                )

        try:
            db.commit()
        except Exception as exc:
            db.rollback()
            hotel_failed = True
            totals["failed_jobs"] += 1
            logger.warning(
                "scheduled_hotel_jobs.hotel_commit_failed hotel_id=%s error_type=%s",
                hotel_id,
                type(exc).__name__,
            )
        if hotel_failed:
            totals["failed_hotels"] += 1

    return totals


def run_scheduled_hotel_jobs(database_url: str | None = None) -> dict[str, int]:
    """Open one SQL session, run the bounded cycle, then release its pool."""
    settings = get_settings()
    engine = get_engine(database_url or settings.DATABASE_URL)
    db = sessionmaker(bind=engine)()
    try:
        return process_scheduled_hotel_jobs(db)
    finally:
        try:
            db.close()
        finally:
            engine.dispose()
