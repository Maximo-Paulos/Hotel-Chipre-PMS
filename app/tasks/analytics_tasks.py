"""
Celery tasks for Analytics R1.0 facts and no-show detection.
"""
from __future__ import annotations

from pathlib import Path
import logging
from datetime import datetime, timezone
from typing import Optional

from app.config import get_settings
from app.database import get_engine
from app.models.analytics import AnalyticsExportJob, AnalyticsExportStatusEnum
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


@celery_app.task(
    bind=True,
    name="analytics.detect_no_shows",
    max_retries=3,
    default_retry_delay=60,
)
def detect_no_shows(
    self,
    hotel_id: int,
    now_iso: str | None = None,
    database_url: Optional[str] = None,
    performed_by_user_id: Optional[int] = None,
):
    try:
        from sqlalchemy.orm import sessionmaker

        from app.services.analytics_facts import detect_no_shows as detect_no_shows_service

        settings = get_settings()
        url = database_url or settings.DATABASE_URL
        engine = get_engine(url)
        SessionLocal = sessionmaker(bind=engine)
        db = SessionLocal()

        try:
            result = detect_no_shows_service(
                db,
                hotel_id=hotel_id,
                now=_parse_datetime(now_iso),
                performed_by_user_id=performed_by_user_id,
            )
            db.commit()
            return {
                "hotel_id": result.hotel_id,
                "scanned": result.scanned,
                "marked": result.marked,
                "reservation_ids": list(result.reservation_ids),
            }
        finally:
            db.close()
    except Exception as exc:
        logger.error("analytics.detect_no_shows failed: %s", exc)
        raise self.retry(exc=exc)


@celery_app.task(
    bind=True,
    name="analytics.refresh_fact_reservation_daily",
    max_retries=3,
    default_retry_delay=60,
)
def refresh_fact_reservation_daily(
    self,
    hotel_id: int,
    date_from_str: str,
    date_to_str: str,
    database_url: Optional[str] = None,
):
    try:
        from datetime import date
        from sqlalchemy.orm import sessionmaker

        from app.services.analytics_facts import refresh_fact_reservation_daily as refresh_service

        settings = get_settings()
        url = database_url or settings.DATABASE_URL
        engine = get_engine(url)
        SessionLocal = sessionmaker(bind=engine)
        db = SessionLocal()

        try:
            result = refresh_service(
                db,
                hotel_id=hotel_id,
                date_from=date.fromisoformat(date_from_str),
                date_to=date.fromisoformat(date_to_str),
            )
            db.commit()
            return {
                "hotel_id": result.hotel_id,
                "date_from": result.date_from.isoformat(),
                "date_to": result.date_to.isoformat(),
                "deleted": result.deleted,
                "inserted": result.inserted,
            }
        finally:
            db.close()
    except Exception as exc:
        logger.error("analytics.refresh_fact_reservation_daily failed: %s", exc)
        raise self.retry(exc=exc)


@celery_app.task(
    bind=True,
    name="analytics.refresh_fact_room_occupancy_daily",
    max_retries=3,
    default_retry_delay=60,
)
def refresh_fact_room_occupancy_daily(
    self,
    hotel_id: int,
    date_from_str: str,
    date_to_str: str,
    database_url: Optional[str] = None,
):
    try:
        from datetime import date
        from sqlalchemy.orm import sessionmaker

        from app.services.analytics_facts import refresh_fact_room_occupancy_daily as refresh_service

        settings = get_settings()
        url = database_url or settings.DATABASE_URL
        engine = get_engine(url)
        SessionLocal = sessionmaker(bind=engine)
        db = SessionLocal()

        try:
            result = refresh_service(
                db,
                hotel_id=hotel_id,
                date_from=date.fromisoformat(date_from_str),
                date_to=date.fromisoformat(date_to_str),
            )
            db.commit()
            return {
                "hotel_id": result.hotel_id,
                "date_from": result.date_from.isoformat(),
                "date_to": result.date_to.isoformat(),
                "deleted": result.deleted,
                "inserted": result.inserted,
            }
        finally:
            db.close()
    except Exception as exc:
        logger.error("analytics.refresh_fact_room_occupancy_daily failed: %s", exc)
        raise self.retry(exc=exc)


@celery_app.task(
    bind=True,
    name="analytics.cleanup_expired_exports",
    max_retries=1,
    default_retry_delay=60,
)
def cleanup_expired_exports(self, database_url: Optional[str] = None):
    try:
        from sqlalchemy.orm import sessionmaker

        settings = get_settings()
        url = database_url or settings.DATABASE_URL
        engine = get_engine(url)
        SessionLocal = sessionmaker(bind=engine)
        db = SessionLocal()

        expired_ids: list[int] = []
        try:
            now = datetime.now(timezone.utc)
            jobs = (
                db.query(AnalyticsExportJob)
                .filter(AnalyticsExportJob.status != AnalyticsExportStatusEnum.EXPIRED)
                .all()
            )
            for job in jobs:
                expires_at = job.expires_at
                if expires_at is None:
                    continue
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=timezone.utc)
                else:
                    expires_at = expires_at.astimezone(timezone.utc)
                if expires_at > now:
                    continue
                job.status = AnalyticsExportStatusEnum.EXPIRED
                expired_ids.append(job.id)
                if job.file_path:
                    path = Path(job.file_path)
                    if path.exists():
                        try:
                            path.unlink()
                        except OSError:
                            logger.warning("analytics.cleanup_expired_exports could not delete %s", path)
            db.commit()
            return {"expired": len(expired_ids), "expired_ids": expired_ids}
        finally:
            db.close()
    except Exception as exc:
        logger.error("analytics.cleanup_expired_exports failed: %s", exc)
        raise self.retry(exc=exc)
