"""
Celery tasks for the notification backend: process the outbox (bounded
retry/expiry -> in-app/push/email delivery) and generate per-hotel daily
reports at their configured local hour.

Mirrors app/tasks/report_tasks.py's pattern: one explicit SessionLocal per
task run, tenant context set per hotel where relevant, and a failure in one
hotel/row never aborts the rest of the batch.
"""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.database import get_engine
from app.services.tenant_context import set_tenant_hotel_context
from app.tasks.celery_app import celery_app
from app.tasks.report_tasks import _active_hotel_ids

logger = logging.getLogger(__name__)


def _session(database_url: Optional[str] = None):
    settings = get_settings()
    url = database_url or settings.DATABASE_URL
    engine = get_engine(url)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


@celery_app.task(name="notifications.process_outbox")
def process_outbox(database_url: Optional[str] = None) -> dict:
    """Deliver each hotel's pending outbox rows under that hotel's RLS
    context. notification_outbox is tenant-isolated (FORCE ROW LEVEL
    SECURITY, no master-admin bypass -- see alembic/versions/20260818_
    notifications.py), so a query with no app.hotel_id set returns zero rows
    rather than crossing tenants. One hotel's failure must not block another's
    delivery, matching report_tasks.py's per-hotel isolation."""
    from app.services.notification_service import process_pending_outbox

    db = _session(database_url)
    totals = {"processed": 0, "sent": 0, "failed": 0, "expired": 0, "retried": 0, "deferred": 0}
    try:
        for hotel_id in _active_hotel_ids(db):
            try:
                set_tenant_hotel_context(db, hotel_id)
                counts = process_pending_outbox(db)
                db.commit()
                for key, value in counts.items():
                    totals[key] = totals.get(key, 0) + value
            except Exception as exc:
                db.rollback()
                logger.warning(
                    "notification_tasks.process_outbox_hotel_failed hotel_id=%s error_type=%s",
                    hotel_id, type(exc).__name__,
                )
        return totals
    finally:
        db.close()


@celery_app.task(name="notifications.generate_daily_reports")
def generate_daily_reports(database_url: Optional[str] = None) -> dict:
    """Same per-hotel RLS-context requirement as process_outbox above --
    daily_report_schedules is tenant-isolated too."""
    from app.services.notification_service import generate_due_daily_reports

    db = _session(database_url)
    results = []
    try:
        for hotel_id in _active_hotel_ids(db):
            try:
                set_tenant_hotel_context(db, hotel_id)
                hotel_results = generate_due_daily_reports(db)
                db.commit()
                results.extend(hotel_results)
            except Exception as exc:
                db.rollback()
                logger.warning(
                    "notification_tasks.generate_daily_reports_hotel_failed hotel_id=%s error_type=%s",
                    hotel_id, type(exc).__name__,
                )
        return {"hotels_reported": len(results), "results": results}
    finally:
        db.close()
