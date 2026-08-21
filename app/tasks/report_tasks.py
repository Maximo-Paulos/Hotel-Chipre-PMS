"""
Celery tasks for scheduled operational reports (BRM §15.1).

Two beat-driven tasks iterate every active hotel and deliver its operational
report by email through the per-hotel Gmail connection (``send_hotel_email``),
never to a global MASTER_ADMIN_EMAIL.

Delivery is best-effort and isolated per hotel: a failure for one hotel
(missing Gmail connection, no recipients, transient API error, ...) is logged
and the loop continues with the remaining hotels.
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Optional

from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.database import get_engine
from app.services.external_effects_policy import require_external_connections
from app.services.tenant_context import set_tenant_hotel_context
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def _active_hotel_ids(db) -> list[int]:
    from app.models.hotel_config import HotelConfiguration

    rows = (
        db.query(HotelConfiguration.id)
        .filter(HotelConfiguration.subscription_active.is_(True))
        .order_by(HotelConfiguration.id.asc())
        .all()
    )
    return [row[0] for row in rows]


def _send_report_for_hotel(db, hotel_id: int, report_date: date, *, kind: str) -> bool:
    """Build and email the report for a single hotel. Returns True on send.

    Best-effort: returns False (without raising) when there are no recipients or
    when email delivery fails, so the caller can keep processing other hotels.
    """
    from app.services.hotel_outbound_email_service import (
        HotelOutboundEmailError,
        send_hotel_email,
    )
    from app.services.operational_report_service import (
        daily_report,
        daily_report_email_body,
        nightly_summary,
        nightly_summary_email_body,
        operational_report_recipients,
    )

    recipients = operational_report_recipients(db, hotel_id)
    if not recipients:
        logger.info("report_tasks: hotel %s has no recipients; skipping %s report", hotel_id, kind)
        return False

    if kind == "morning":
        report = daily_report(db, hotel_id, report_date)
        subject = f"Daily operational report - {report_date.isoformat()}"
        body = daily_report_email_body(report)
    else:
        summary = nightly_summary(db, hotel_id, report_date)
        subject = f"Nightly operational summary - {report_date.isoformat()}"
        body = nightly_summary_email_body(summary)

    try:
        send_hotel_email(db, hotel_id, to=recipients, subject=subject, body=body)
    except HotelOutboundEmailError as exc:
        logger.warning(
            "report_tasks: %s report email failed for hotel %s error_type=%s",
            kind,
            hotel_id,
            type(exc).__name__,
        )
        return False
    return True


def _run_scheduled_reports(
    kind: str,
    *,
    report_date: date | None = None,
    database_url: Optional[str] = None,
) -> dict:
    settings = get_settings()
    # Must precede engine/session creation, hotel queries and Gmail credential
    # lookup. A queued stale task is therefore safe even after the lane closes.
    require_external_connections("scheduled operational report delivery", settings)
    url = database_url or settings.DATABASE_URL
    engine = get_engine(url)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    if report_date is None:
        report_date = date.today()

    sent = 0
    failed = 0
    hotel_ids: list[int] = []
    try:
        hotel_ids = _active_hotel_ids(db)
        for hotel_id in hotel_ids:
            try:
                set_tenant_hotel_context(db, hotel_id)
                if _send_report_for_hotel(db, hotel_id, report_date, kind=kind):
                    sent += 1
                else:
                    failed += 1
                db.commit()
            except Exception as exc:  # one hotel must never abort the rest
                failed += 1
                db.rollback()
                logger.warning(
                    "report_tasks: %s report errored for hotel %s error_type=%s",
                    kind,
                    hotel_id,
                    type(exc).__name__,
                )
    finally:
        db.close()

    return {
        "kind": kind,
        "report_date": report_date.isoformat(),
        "hotels": len(hotel_ids),
        "sent": sent,
        "failed": failed,
    }


@celery_app.task(name="reports.send_morning_reports")
def send_morning_reports(report_date_str: str | None = None, database_url: Optional[str] = None) -> dict:
    report_date = date.fromisoformat(report_date_str) if report_date_str else None
    return _run_scheduled_reports("morning", report_date=report_date, database_url=database_url)


@celery_app.task(name="reports.send_nightly_reports")
def send_nightly_reports(report_date_str: str | None = None, database_url: Optional[str] = None) -> dict:
    report_date = date.fromisoformat(report_date_str) if report_date_str else None
    return _run_scheduled_reports("nightly", report_date=report_date, database_url=database_url)
