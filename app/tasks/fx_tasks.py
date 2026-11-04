"""Scheduled persistence of public FX quotes used by reservation conversions."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from app.database import get_session_factory
from app.services.external_effects_policy import dolarapi_rates_enabled
from app.services.fx_rate_cache_service import store_supported_fx_rates
from app.services.fx_service import _refresh_supported_rates
from app.tasks.celery_app import celery_app


@celery_app.task(
    bind=True,
    name="fx.refresh_daily_rate_cache",
    max_retries=2,
    default_retry_delay=900,
    time_limit=90,
    soft_time_limit=75,
)
def refresh_daily_rate_cache(self) -> dict:
    """Fetch DolarAPI's supported rate series and upsert the durable cache.

    This task is gated independently from payment, email, and OTA integrations.
    A missing provider result is retried twice with a 15-minute delay; existing
    cache rows remain untouched when the provider returns no valid quote.
    """
    if not dolarapi_rates_enabled():
        return {"status": "disabled", "updated": 0}

    rates = asyncio.run(_refresh_supported_rates())
    if not rates:
        raise self.retry(
            exc=RuntimeError("DolarAPI returned no supported rates"),
            countdown=900,
        )

    db = get_session_factory()()
    try:
        observed_at = datetime.now(UTC)
        updated = store_supported_fx_rates(
            db,
            rates,
            cache_source="daily",
            observed_at=observed_at,
        )
        if updated == 0:
            db.rollback()
            raise self.retry(
                exc=RuntimeError("DolarAPI returned no valid rates for cache"),
                countdown=900,
            )
        db.commit()
        return {
            "status": "ok",
            "updated": updated,
            "observed_at": observed_at.isoformat(),
        }
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
