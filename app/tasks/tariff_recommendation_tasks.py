"""Daily generation of reviewable, never-auto-published tariff drafts."""
from __future__ import annotations

import logging

from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.database import get_engine
from app.services.tenant_context import set_tenant_hotel_context
from app.tasks.celery_app import celery_app
from app.tasks.report_tasks import _active_hotel_ids

logger = logging.getLogger(__name__)


@celery_app.task(name="tariff_recommendations.generate_daily")
def generate_daily_tariff_recommendations(database_url: str | None = None) -> dict[str, int]:
    """Create human-review drafts for opted-in hotels using persisted PMS data."""
    from app.services.tariff_recommendation_service import (
        generate_daily_rate_recommendations,
    )

    settings = get_settings()
    engine = get_engine(database_url or settings.DATABASE_URL)
    db = sessionmaker(bind=engine)()
    totals = {"hotels": 0, "categories": 0, "drafts_created": 0, "dates_suggested": 0, "failed_hotels": 0}
    try:
        for hotel_id in _active_hotel_ids(db):
            try:
                set_tenant_hotel_context(db, hotel_id)
                result = generate_daily_rate_recommendations(db, hotel_id=hotel_id)
                db.commit()
                totals["hotels"] += 1
                for key in ("categories", "drafts_created", "dates_suggested"):
                    totals[key] += int(result.get(key, 0))
            except Exception as exc:  # noqa: BLE001 - isolate one hotel's failure from the daily batch.
                db.rollback()
                totals["failed_hotels"] += 1
                logger.warning(
                    "tariff_recommendation_tasks.hotel_failed hotel_id=%s error_type=%s",
                    hotel_id,
                    type(exc).__name__,
                )
        return totals
    finally:
        db.close()
