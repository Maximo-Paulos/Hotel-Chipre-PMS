"""SQL-only Render Cron entrypoint for tenant-isolated hotel jobs."""
from __future__ import annotations

import logging

from app.services.scheduled_hotel_jobs_service import run_scheduled_hotel_jobs

logger = logging.getLogger(__name__)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        totals = run_scheduled_hotel_jobs()
    except Exception as exc:
        logger.error("scheduled_hotel_jobs.cron_failed error_type=%s", type(exc).__name__)
        return 1

    logger.info(
        "scheduled_hotel_jobs.completed hotels=%s active_hotels=%s no_shows_scanned=%s "
        "no_shows_marked=%s reports_generated=%s notifications_processed=%s "
        "notifications_sent=%s notifications_failed=%s notifications_deferred=%s "
        "notifications_retried=%s analytics_facts_processed=%s analytics_facts_deferred=%s "
        "failed_jobs=%s failed_hotels=%s",
        totals["hotels_scanned"],
        totals["active_hotels_scanned"],
        totals["no_shows_scanned"],
        totals["no_shows_marked"],
        totals["reports_generated"],
        totals["notifications_processed"],
        totals["notifications_sent"],
        totals["notifications_failed"],
        totals["notifications_deferred"],
        totals["notifications_retried"],
        totals["analytics_facts_processed"],
        totals["analytics_facts_deferred"],
        totals["failed_jobs"],
        totals["failed_hotels"],
    )
    return 1 if totals["failed_jobs"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
