"""Celery task that drains the durable domain-event outbox.

Mirrors app/tasks/notification_tasks.py's pattern: one explicit SessionLocal
per task run, tenant context set per hotel (outbox rows are RLS-protected on
PostgreSQL), and a failure in one hotel never blocks another's replay.
"""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.database import get_engine
from app.services.tenant_context import set_tenant_hotel_context
from app.services.service_heartbeat import record_heartbeat
from app.tasks.celery_app import celery_app
from app.tasks.report_tasks import _active_hotel_ids

logger = logging.getLogger(__name__)


def _session(database_url: Optional[str] = None):
    settings = get_settings()
    url = database_url or settings.DATABASE_URL
    engine = get_engine(url)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


@celery_app.task(name="domain_events.publish_outbox")
def publish_outbox(database_url: Optional[str] = None) -> dict:
    """Replay pending domain_event_outbox rows onto Redis/Valkey, per hotel.

    Bounded recovery path for the after-commit fast path: a row only stays
    pending here when the process died, or Redis was unavailable, between the
    business commit and the first publish attempt.
    """
    from app.services.domain_events import publish_pending_domain_events

    db = _session(database_url)
    totals = {"selected": 0, "published": 0, "failed": 0}
    try:
        try:
            record_heartbeat(db, service_name="celery-worker", instance_id="domain-events", queue_name="critical", metadata={"task": "domain_events.publish_outbox"})
            db.commit()
        except Exception as exc:
            # A rolling deployment can run replay before the optional
            # heartbeat table exists. Durable event replay still proceeds.
            db.rollback()
            logger.warning(
                "domain_event_tasks.heartbeat_unavailable error_type=%s",
                type(exc).__name__,
            )
        for hotel_id in _active_hotel_ids(db):
            try:
                set_tenant_hotel_context(db, hotel_id)
                result = publish_pending_domain_events(db, hotel_id=hotel_id)
                db.commit()
                for key in ("selected", "published", "failed"):
                    totals[key] += result.get(key, 0)
            except Exception as exc:
                db.rollback()
                logger.warning(
                    "domain_event_tasks.publish_outbox_hotel_failed hotel_id=%s error_type=%s",
                    hotel_id, type(exc).__name__,
                )
        return totals
    finally:
        db.close()
