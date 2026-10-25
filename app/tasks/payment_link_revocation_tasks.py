"""Durable, tenant-scoped recovery for canceled Mercado Pago checkout links."""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.database import get_engine
from app.models.hotel_config import HotelConfiguration
from app.services.external_effects_policy import external_connections_enabled
from app.services.payment_link_service import process_payment_link_revocations
from app.services.tenant_context import set_tenant_hotel_context

logger = logging.getLogger(__name__)

# The provider adapter makes at most three sequential HTTP calls for one link,
# each with a 20 second timeout. Two links therefore bound provider wait time
# to about 120 seconds and leave time in the five-minute Render Cron interval
# for the SQL-only scheduled jobs that run first.
MAX_REVOCATIONS_PER_CYCLE = 2
SCHEDULE_INTERVAL_SECONDS = 5 * 60


def _empty_totals(*, external_connections_disabled: bool = False) -> dict[str, int]:
    return {
        "hotels_scanned": 0,
        "hotels_visited": 0,
        "processed": 0,
        "succeeded": 0,
        "failed": 0,
        "skipped": int(external_connections_disabled),
        "failed_jobs": 0,
        "failed_hotels": 0,
        "attempts_used": 0,
        "attempt_limit": MAX_REVOCATIONS_PER_CYCLE,
        "external_connections_disabled": int(external_connections_disabled),
    }


def _positive_count(result: dict[str, Any], key: str) -> int:
    value = result.get(key, 0)
    if isinstance(value, bool):
        return int(value)
    try:
        return max(0, int(value))
    except (TypeError, ValueError, OverflowError):
        return 0


def _rotated_hotel_ids(
    hotel_ids: list[int], *, now: datetime | None = None
) -> list[int]:
    """Rotate two positions every five-minute slot for predictable fairness."""
    if len(hotel_ids) < 2:
        return hotel_ids

    cycle_time = now or datetime.now(UTC)
    if cycle_time.tzinfo is None:
        cycle_time = cycle_time.replace(tzinfo=UTC)
    cycle_number = int(cycle_time.timestamp()) // SCHEDULE_INTERVAL_SECONDS
    offset = (cycle_number * MAX_REVOCATIONS_PER_CYCLE) % len(hotel_ids)
    return hotel_ids[offset:] + hotel_ids[:offset]


def _process_pending_revocations(
    db: Session, *, now: datetime | None = None
) -> dict[str, int]:
    """Enumerate every hotel regardless of subscription, rotating visits by cycle."""
    totals = _empty_totals()
    rows = (
        db.query(HotelConfiguration.id)
        .order_by(HotelConfiguration.id.asc())
        .all()
    )
    db.commit()
    hotel_ids = [int(row[0]) for row in rows]
    totals["hotels_scanned"] = len(hotel_ids)

    # This query intentionally selects only IDs and has no subscription filter:
    # cancellation cleanup remains owed even after a hotel's subscription ends.
    for hotel_id in _rotated_hotel_ids(hotel_ids, now=now):
        if totals["attempts_used"] >= MAX_REVOCATIONS_PER_CYCLE:
            break
        totals["hotels_visited"] += 1
        attempt_slot_reserved = False
        try:
            set_tenant_hotel_context(db, hotel_id)
            counts = process_payment_link_revocations(db, hotel_id, limit=1)
            if not isinstance(counts, dict):
                # A malformed service result may follow provider I/O. Charge
                # one slot before recording the failure to preserve the bound.
                totals["attempts_used"] += 1
                attempt_slot_reserved = True
                raise TypeError("payment-link revocation service returned an invalid result")

            for key in ("processed", "succeeded", "failed", "skipped"):
                totals[key] += _positive_count(counts, key)

            # The service is called with limit=1. A processed or concurrently
            # skipped claim consumes this run's global provider-attempt budget.
            if _positive_count(counts, "processed") or _positive_count(counts, "skipped"):
                totals["attempts_used"] += 1
                attempt_slot_reserved = True
            db.commit()
        except Exception as exc:  # noqa: BLE001 - one tenant must not block the next
            db.rollback()
            # A raised error can occur after provider I/O, so reserve its slot.
            if not attempt_slot_reserved and totals["attempts_used"] < MAX_REVOCATIONS_PER_CYCLE:
                totals["attempts_used"] += 1
            totals["failed_jobs"] += 1
            totals["failed_hotels"] += 1
            logger.warning(
                "payment_link_revocation_tasks.hotel_failed hotel_id=%s error_type=%s",
                hotel_id,
                type(exc).__name__,
            )
    return totals


def run_payment_link_revocation_tasks(database_url: str | None = None) -> dict[str, int]:
    """Drain a small, fair batch after the SQL-only scheduled hotel jobs."""
    settings = get_settings()
    # Must precede engine/session creation, hotel enumeration, or claim attempts.
    # A closed provider lane leaves durable pending rows untouched for a later run.
    if not external_connections_enabled(settings):
        return _empty_totals(external_connections_disabled=True)

    engine = get_engine(database_url or settings.DATABASE_URL)
    db = sessionmaker(bind=engine)()
    try:
        return _process_pending_revocations(db)
    finally:
        try:
            db.close()
        finally:
            engine.dispose()
