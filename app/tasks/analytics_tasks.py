"""
Celery tasks for Analytics R1.0 facts and no-show detection.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Optional

from app.config import get_settings
from app.database import get_engine
from app.models.analytics import AnalyticsExportJob, AnalyticsExportStatusEnum, FactReservationDaily
from app.models.cash_register import CashMovement
from app.models.hotel_config import HotelConfiguration
from app.models.room import Room, RoomCategory
from app.models.stock import StockMovement
from app.models.transaction import Transaction, TransactionStatusEnum
from app.services.analytics_exports import delete_export_file
from app.services.financial_ledger import signed_transaction_amount
from app.services.external_effects_policy import require_external_connections
from app.services.object_storage import ObjectStorageError
from app.services.analytics_warehouse import (
    DIM_DATE_TABLE,
    DIM_HOTEL_TABLE,
    DIM_ROOM_CATEGORY_TABLE,
    DIM_ROOM_TABLE,
    build_date_dimension_rows,
    build_hotel_dimension_row,
    build_room_category_dimension_row,
    build_room_dimension_row,
    canonical_payment_amount,
    ensure_schema,
    get_clickhouse_client,
    project_operational_fact_rows,
    project_reservation_fact_rows,
    reconcile_derived_fact,
    reconcile_reservation_fact_counts,
)
from app.services.tenant_context import set_tenant_hotel_context
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def _date_window(date_from: date, date_to: date) -> tuple[datetime, datetime]:
    if date_to < date_from:
        raise ValueError("date_to must be greater than or equal to date_from")
    return (
        datetime.combine(date_from, time.min),
        datetime.combine(date_to + timedelta(days=1), time.min),
    )


def _decimal_total(rows: list[object], field: str) -> Decimal:
    return sum(
        (Decimal(str(getattr(row, field))) for row in rows if getattr(row, field) is not None),
        Decimal("0"),
    )


def _project_operational_window(
    db,
    client,
    *,
    hotel_id: int,
    date_from: date,
    date_to: date,
    include_global_date_dimension: bool = True,
) -> dict:
    """Replay OLTP rows into PII-free ClickHouse facts and reconcile each set.

    This is deliberately replayable and provider-neutral. In production the
    preferred trigger is ClickPipes PostgreSQL CDC; the same projection code
    remains useful for backfills and a bounded recovery window.
    """

    start_at, end_at = _date_window(date_from, date_to)
    hotel = db.query(HotelConfiguration).filter(HotelConfiguration.id == hotel_id).one_or_none()
    if hotel is None:
        raise ValueError(f"hotel {hotel_id} does not exist")

    version = datetime.now(timezone.utc).isoformat()
    client.insert_json_each_row(
        DIM_HOTEL_TABLE,
        [
            build_hotel_dimension_row(
                {
                    "hotel_id": hotel.id,
                    "hotel_name": hotel.hotel_name,
                    "hotel_timezone": hotel.hotel_timezone,
                    "currency": hotel.default_currency,
                }
            )
        ],
        version=version,
    )
    if include_global_date_dimension:
        client.insert_json_each_row(
            DIM_DATE_TABLE,
            build_date_dimension_rows(date_from, date_to),
            version=version,
        )

    categories = db.query(RoomCategory).filter(RoomCategory.hotel_id == hotel_id).all()
    client.insert_json_each_row(
        DIM_ROOM_CATEGORY_TABLE,
        [
            build_room_category_dimension_row(
                {
                    "hotel_id": category.hotel_id,
                    "category_id": category.id,
                    "category_code": category.code,
                    "category_name": category.name,
                    "base_price_ars": category.base_price_per_night,
                }
            )
            for category in categories
        ],
        version=version,
    )
    rooms = db.query(Room).filter(Room.hotel_id == hotel_id).all()
    client.insert_json_each_row(
        DIM_ROOM_TABLE,
        [
            build_room_dimension_row(
                {
                    "hotel_id": room.hotel_id,
                    "room_id": room.id,
                    "room_number": room.room_number,
                    "category_id": room.category_id,
                    "status": room.status,
                    "is_active": room.is_active,
                }
            )
            for room in rooms
        ],
        version=version,
    )

    transactions = (
        db.query(Transaction)
        .filter(
            Transaction.hotel_id == hotel_id,
            Transaction.status == TransactionStatusEnum.COMPLETED,
            Transaction.created_at >= start_at,
            Transaction.created_at < end_at,
        )
        .order_by(Transaction.created_at.asc(), Transaction.id.asc())
        .all()
    )
    cash_movements = (
        db.query(CashMovement)
        .filter(
            CashMovement.hotel_id == hotel_id,
            CashMovement.recorded_at >= start_at,
            CashMovement.recorded_at < end_at,
        )
        .order_by(CashMovement.recorded_at.asc(), CashMovement.id.asc())
        .all()
    )
    stock_movements = (
        db.query(StockMovement)
        .filter(
            StockMovement.hotel_id == hotel_id,
            StockMovement.created_at >= start_at,
            StockMovement.created_at < end_at,
        )
        .order_by(StockMovement.created_at.asc(), StockMovement.id.asc())
        .all()
    )

    operational_rows = {
        "payment": [
            {
                "hotel_id": row.hotel_id,
                "transaction_id": row.id,
                "reservation_id": row.reservation_id,
                "transaction_date": row.created_at,
                "amount": canonical_payment_amount(
                    {
                        "amount": row.amount,
                        "transaction_type": row.transaction_type,
                        "status": row.status,
                    }
                ),
                "currency": row.currency,
                "payment_method": row.payment_method,
                "transaction_type": row.transaction_type,
                "status": row.status,
            }
            for row in transactions
        ],
        "cash_movement": [
            {
                "hotel_id": row.hotel_id,
                "cash_movement_id": row.id,
                "session_id": row.session_id,
                "recorded_at": row.recorded_at,
                "amount": row.amount,
                "currency": hotel.default_currency,
                "movement_type": row.movement_type,
            }
            for row in cash_movements
        ],
        "stock_movement": [
            {
                "hotel_id": row.hotel_id,
                "stock_movement_id": row.id,
                "item_id": row.item_id,
                "location_id": row.location_id,
                "reservation_id": row.reservation_id,
                "created_at": row.created_at,
                "quantity": row.quantity,
                "movement_type": row.movement_type,
            }
            for row in stock_movements
        ],
    }
    amounts = {
        "payment": sum(
            (signed_transaction_amount(row) for row in transactions),
            Decimal("0"),
        ),
        "cash_movement": _decimal_total(cash_movements, "amount"),
        "stock_movement": _decimal_total(stock_movements, "quantity"),
    }
    sync_results = {}
    reconciliations = {}
    for fact_name, rows in operational_rows.items():
        sync_results[fact_name] = project_operational_fact_rows(
            client,
            fact_name=fact_name,
            hotel_id=hotel_id,
            date_from=date_from,
            date_to=date_to,
            rows=rows,
        )
        reconciliation = reconcile_derived_fact(
            client,
            fact_name=fact_name,
            hotel_id=hotel_id,
            date_from=date_from,
            date_to=date_to,
            source_count=len(rows),
            source_amount=amounts[fact_name],
        )
        reconciliations[fact_name] = reconciliation
        if not reconciliation.ok:
            logger.error(
                "analytics.warehouse_reconciliation_failed",
                extra={
                    "hotel_id": hotel_id,
                    "fact_name": fact_name,
                    "source_count": reconciliation.source_count,
                    "warehouse_count": reconciliation.warehouse_count,
                    "source_amount": str(reconciliation.source_amount),
                    "warehouse_amount": str(reconciliation.warehouse_amount),
                },
            )
            raise RuntimeError(
                f"warehouse reconciliation mismatch for hotel={hotel_id} fact={fact_name}"
            )

    return {
        "hotel_id": hotel_id,
        "date_from": date_from.isoformat(),
        "date_to": date_to.isoformat(),
        "rows": {name: result.rows for name, result in sync_results.items()},
        "reconciliations": {
            name: {
                "source_count": result.source_count,
                "warehouse_count": result.warehouse_count,
                "source_amount": str(result.source_amount),
                "warehouse_amount": str(result.warehouse_amount),
                "ok": result.ok,
            }
            for name, result in reconciliations.items()
        },
    }


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
        logger.error("analytics.detect_no_shows failed error_type=%s", type(exc).__name__)
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
        logger.error("analytics.refresh_fact_reservation_daily failed error_type=%s", type(exc).__name__)
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
        logger.error("analytics.refresh_fact_room_occupancy_daily failed error_type=%s", type(exc).__name__)
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

        require_external_connections("scheduled ClickHouse projection")
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
        logger.error("analytics.project_reservation_facts_to_clickhouse failed error_type=%s", type(exc).__name__)
        raise self.retry(exc=exc)


@celery_app.task(
    bind=True,
    name="analytics.project_operational_facts_to_clickhouse",
    max_retries=3,
    default_retry_delay=60,
)
def project_operational_facts_to_clickhouse(
    self,
    hotel_id: int,
    date_from_str: str,
    date_to_str: str,
    database_url: Optional[str] = None,
):
    """Replay payments, cash and stock facts and fail closed on drift."""

    try:
        from sqlalchemy.orm import sessionmaker

        require_external_connections("scheduled ClickHouse projection")
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
            ensure_schema(client)
            result = _project_operational_window(
                db,
                client,
                hotel_id=hotel_id,
                date_from=date_from,
                date_to=date_to,
            )
            result["status"] = "ok"
            return result
        finally:
            db.close()
    except Exception as exc:
        logger.error("analytics.project_operational_facts_to_clickhouse failed error_type=%s", type(exc).__name__)
        raise self.retry(exc=exc)


def _project_all_hotels_window(
    *,
    date_from: date,
    date_to: date,
    database_url: Optional[str] = None,
) -> dict:
    from sqlalchemy.orm import sessionmaker

    # Keep this before the ClickHouse client and PostgreSQL engine. Both the
    # beat path and a directly queued stale task fail closed.
    require_external_connections("scheduled ClickHouse projection")
    client = get_clickhouse_client()
    if client is None:
        return {"status": "disabled", "hotels": 0}

    settings = get_settings()
    engine = get_engine(database_url or settings.DATABASE_URL)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    try:
        ensure_schema(client)
        client.insert_json_each_row(
            DIM_DATE_TABLE,
            build_date_dimension_rows(date_from, date_to),
            version=datetime.now(timezone.utc).isoformat(),
        )
        hotel_ids = [row[0] for row in db.query(HotelConfiguration.id).order_by(HotelConfiguration.id).all()]
        results = []
        for hotel_id in hotel_ids:
            set_tenant_hotel_context(db, hotel_id)
            results.append(
                _project_operational_window(
                    db,
                    client,
                    hotel_id=hotel_id,
                    date_from=date_from,
                    date_to=date_to,
                    include_global_date_dimension=False,
                )
            )
        return {"status": "ok", "hotels": len(results), "results": results}
    finally:
        db.close()


@celery_app.task(
    bind=True,
    name="analytics.project_all_derived_facts_incremental",
    max_retries=2,
    default_retry_delay=60,
)
def project_all_derived_facts_incremental(self, database_url: Optional[str] = None):
    """Five-minute bounded replay used alongside ClickPipes CDC."""

    try:
        today = datetime.now(timezone.utc).date()
        result = _project_all_hotels_window(
            date_from=today - timedelta(days=2),
            date_to=today,
            database_url=database_url,
        )
        result["window"] = "incremental"
        return result
    except Exception as exc:
        logger.error("analytics.project_all_derived_facts_incremental failed error_type=%s", type(exc).__name__)
        raise self.retry(exc=exc)


@celery_app.task(
    bind=True,
    name="analytics.reconcile_all_derived_facts_nightly",
    max_retries=1,
    default_retry_delay=300,
)
def reconcile_all_derived_facts_nightly(self, database_url: Optional[str] = None):
    """Nightly full-window replay/reconciliation; mismatches block publication."""

    try:
        today = datetime.now(timezone.utc).date()
        result = _project_all_hotels_window(
            date_from=today - timedelta(days=365),
            date_to=today,
            database_url=database_url,
        )
        result["window"] = "nightly"
        return result
    except Exception as exc:
        logger.error("analytics.reconcile_all_derived_facts_nightly failed error_type=%s", type(exc).__name__)
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
                        try:
                            delete_export_file(job)
                        except ObjectStorageError:
                            logger.warning(
                                "analytics.cleanup_expired_exports could not delete %s", job.file_path
                            )
                db.commit()
            return {"expired": len(expired_ids), "expired_ids": expired_ids}
        finally:
            db.close()
    except Exception as exc:
        logger.error("analytics.cleanup_expired_exports failed error_type=%s", type(exc).__name__)
        raise self.retry(exc=exc)
