"""Durable SQL queue for coalesced reservation fact refreshes."""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import case
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.models.analytics import AnalyticsFactRefreshJob

logger = logging.getLogger(__name__)


def enqueue_analytics_fact_refresh(
    db: Session,
    *,
    hotel_id: int,
    reservation_id: int,
    date_from: date,
    date_to: date,
) -> None:
    """Queue or widen one hotel's refresh window for one reservation.

    Repeated edits to the same reservation are folded into a single row. The
    row contains only hotel/reservation identifiers and dates, never guest data.
    """
    if hotel_id <= 0 or reservation_id <= 0:
        raise ValueError("hotel_id and reservation_id must be positive")
    if date_to < date_from:
        return

    now = datetime.now(timezone.utc)
    values = {
        "hotel_id": hotel_id,
        "reservation_id": reservation_id,
        "date_from": date_from,
        "date_to": date_to,
        "attempts": 0,
        "available_at": now,
        "last_error_type": None,
        "created_at": now,
        "updated_at": now,
    }
    table = AnalyticsFactRefreshJob.__table__
    dialect_name = db.get_bind().dialect.name

    if dialect_name == "postgresql":
        insert_statement = postgresql_insert(AnalyticsFactRefreshJob).values(**values)
    elif dialect_name == "sqlite":
        insert_statement = sqlite_insert(AnalyticsFactRefreshJob).values(**values)
    else:
        current = (
            db.query(AnalyticsFactRefreshJob)
            .filter_by(hotel_id=hotel_id, reservation_id=reservation_id)
            .with_for_update()
            .one_or_none()
        )
        if current is None:
            db.add(AnalyticsFactRefreshJob(**values))
        else:
            current.date_from = min(current.date_from, date_from)
            current.date_to = max(current.date_to, date_to)
            current.attempts = 0
            current.available_at = now
            current.last_error_type = None
            current.updated_at = now
        return

    excluded = insert_statement.excluded
    statement = insert_statement.on_conflict_do_update(
        index_elements=["hotel_id", "reservation_id"],
        set_={
            "date_from": case(
                (table.c.date_from > excluded.date_from, excluded.date_from),
                else_=table.c.date_from,
            ),
            "date_to": case(
                (table.c.date_to < excluded.date_to, excluded.date_to),
                else_=table.c.date_to,
            ),
            "attempts": 0,
            "available_at": now,
            "last_error_type": None,
            "updated_at": now,
        },
    )
    db.execute(statement)


def process_analytics_fact_refresh_queue_for_hotel(
    db: Session,
    *,
    hotel_id: int,
    batch_size: int = 50,
) -> dict[str, int]:
    """Drain a bounded batch for one hotel, retaining failed work with backoff."""
    if hotel_id <= 0:
        raise ValueError("hotel_id must be positive")
    if batch_size < 1 or batch_size > 500:
        raise ValueError("batch_size must be between 1 and 500")

    now = datetime.now(timezone.utc)
    jobs = (
        db.query(AnalyticsFactRefreshJob)
        .filter(
            AnalyticsFactRefreshJob.hotel_id == hotel_id,
            AnalyticsFactRefreshJob.available_at <= now,
        )
        .order_by(AnalyticsFactRefreshJob.available_at.asc(), AnalyticsFactRefreshJob.id.asc())
        .with_for_update(skip_locked=True)
        .limit(batch_size)
        .all()
    )
    processed = 0
    deferred = 0

    # Import here so the queue module remains a small persistence boundary.
    from app.services.analytics_facts import touch_reservation_fact_window

    for job in jobs:
        try:
            with db.begin_nested():
                touch_reservation_fact_window(
                    db,
                    hotel_id=job.hotel_id,
                    reservation_id=job.reservation_id,
                    date_from=job.date_from,
                    date_to=job.date_to,
                    force_sync=True,
                )
                db.delete(job)
            processed += 1
        except Exception as exc:
            # The nested transaction rolls back fact writes, leaving this queue
            # row available for a bounded retry without losing source changes.
            job.attempts += 1
            job.last_error_type = type(exc).__name__[:80]
            retry_minutes = min(60, 2 ** min(job.attempts - 1, 6))
            job.available_at = now + timedelta(minutes=retry_minutes)
            job.updated_at = now
            db.flush()
            deferred += 1
            logger.warning(
                "analytics_fact_refresh.deferred hotel_id=%s reservation_id=%s attempts=%s error_type=%s",
                hotel_id,
                job.reservation_id,
                job.attempts,
                type(exc).__name__,
            )

    return {"processed": processed, "deferred": deferred}
