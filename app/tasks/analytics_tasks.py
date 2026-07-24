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
from app.models.analytics import AnalyticsExportJob, AnalyticsExportStatusEnum, FactReservationDaily
from app.services.analytics_warehouse import (
    ensure_schema,
    get_clickhouse_client,
    project_reservation_fact_rows,
    reconcile_reservation_fact_counts,
)
from app.services.tenant_context import set_tenant_hotel_context
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
            set_tenant_hotel_context(db, hotel_id)
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
            set_tenant_hotel_context(db, hotel_id)
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
            set_tenant_hotel_context(db, hotel_id)
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
    name="analytics.project_reservation_facts_to_clickhouse",
    max_retries=3,
    default_retry_delay=60,
)
def project_reservation_facts_to_clickhouse(
    self,
    hotel_id: int,
    date_from_str: str,
    date_to_str: str,
    database_url: Optional[str] = None,
):
    """Project PostgreSQL facts and reconcile the derived ClickHouse window.

    This is intentionally a pull-based CDC consumer: a future Debezium/WAL
    trigger can enqueue the same task, while the task remains replayable and
    safe because ClickHouse uses ReplacingMergeTree(version).
    """

    try:
        from datetime import date
        from sqlalchemy.orm import sessionmaker

        client = get_clickhouse_client()
        if client is None:
            return {"status": "disabled", "hotel_id": hotel_id}

        settings = get_settings()
        url = database_url or settings.DATABASE_URL
        engine = get_engine(url)
        SessionLocal = sessionmaker(bind=engine)
        db = SessionLocal()
        date_from = date.fromisoformat(date_from_str)
        date_to = date.fromisoformat(date_to_str)
        try:
            set_tenant_hotel_context(db, hotel_id)
            source_rows = (
                db.query(FactReservationDaily)
                .filter(
                    FactReservationDaily.hotel_id == hotel_id,
                    FactReservationDaily.stay_date >= date_from,
                    FactReservationDaily.stay_date <= date_to,
                )
                .order_by(FactReservationDaily.stay_date.asc(), FactReservationDaily.reservation_id.asc())
                .all()
            )
            rows = [
                {
                    "hotel_id": fact.hotel_id,
                    "reservation_id": fact.reservation_id,
                    "stay_date": fact.stay_date,
                    "room_id": fact.room_id,
                    "category_id": fact.category_id,
                    "revenue_gross_ars": fact.revenue_gross_ars,
                    "status": getattr(fact.status, "value", fact.status),
                }
                for fact in source_rows
            ]
            ensure_schema(client)
            sync_result = project_reservation_fact_rows(
                client,
                hotel_id=hotel_id,
                date_from=date_from,
                date_to=date_to,
                rows=rows,
            )
            reconciliation = reconcile_reservation_fact_counts(
                client,
                hotel_id=hotel_id,
                date_from=date_from,
                date_to=date_to,
                source_count=len(rows),
            )
            if not reconciliation.ok:
                raise RuntimeError(
                    f"ClickHouse reconciliation mismatch for hotel {hotel_id}: "
                    f"source={reconciliation.source_count} warehouse={reconciliation.warehouse_count}"
                )
            return {
                "status": "ok",
                "hotel_id": hotel_id,
                "date_from": date_from.isoformat(),
                "date_to": date_to.isoformat(),
                "rows": sync_result.rows,
                "source_count": reconciliation.source_count,
                "warehouse_count": reconciliation.warehouse_count,
            }
        finally:
            db.close()
    except Exception as exc:
        logger.error("analytics.project_reservation_facts_to_clickhouse failed: %s", exc)
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
            from app.models.hotel_config import HotelConfiguration

            hotel_ids = [row[0] for row in db.query(HotelConfiguration.id).all()]
            for hotel_id in hotel_ids:
                set_tenant_hotel_context(db, hotel_id)
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
