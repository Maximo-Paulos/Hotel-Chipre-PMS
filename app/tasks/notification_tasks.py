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
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def _session(database_url: Optional[str] = None):
    settings = get_settings()
    url = database_url or settings.DATABASE_URL
    engine = get_engine(url)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


@celery_app.task(name="notifications.process_outbox")
def process_outbox(database_url: Optional[str] = None) -> dict:
    from app.services.notification_service import process_pending_outbox

    db = _session(database_url)
    try:
        counts = process_pending_outbox(db)
        db.commit()
        return counts
    except Exception as exc:
        db.rollback()
        logger.error("notification_tasks.process_outbox_failed error_type=%s", type(exc).__name__)
        raise
    finally:
        db.close()


@celery_app.task(name="notifications.generate_daily_reports")
def generate_daily_reports(database_url: Optional[str] = None) -> dict:
    from app.services.notification_service import generate_due_daily_reports

    db = _session(database_url)
    try:
        results = generate_due_daily_reports(db)
        db.commit()
        return {"hotels_reported": len(results), "results": results}
    except Exception as exc:
        db.rollback()
        logger.error("notification_tasks.generate_daily_reports_failed error_type=%s", type(exc).__name__)
        raise
    finally:
        db.close()
