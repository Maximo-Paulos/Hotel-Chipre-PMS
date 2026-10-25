"""Render Cron entrypoint for tenant-isolated jobs and bounded provider recovery."""
from __future__ import annotations

import logging

from app.services.scheduled_hotel_jobs_service import run_scheduled_hotel_jobs
from app.tasks.payment_link_revocation_tasks import run_payment_link_revocation_tasks

logger = logging.getLogger(__name__)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        totals = run_scheduled_hotel_jobs()
    except Exception as exc:  # noqa: BLE001 - cron boundary must report failures safely
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

    # Provider traffic runs in a distinct session and only after the regular
    # tenant-scoped SQL job pass has completed.
    try:
        revocations = run_payment_link_revocation_tasks()
    except Exception as exc:  # noqa: BLE001 - cron boundary must report failures safely
        logger.error(
            "payment_link_revocation_tasks.cron_failed error_type=%s",
            type(exc).__name__,
        )
        return 1

    logger.info(
        "payment_link_revocation_tasks.completed hotels_scanned=%s hotels_visited=%s "
        "processed=%s succeeded=%s failed=%s skipped=%s attempts=%s attempt_limit=%s "
        "external_connections_disabled=%s failed_jobs=%s failed_hotels=%s",
        revocations["hotels_scanned"],
        revocations["hotels_visited"],
        revocations["processed"],
        revocations["succeeded"],
        revocations["failed"],
        revocations["skipped"],
        revocations["attempts_used"],
        revocations["attempt_limit"],
        revocations["external_connections_disabled"],
        revocations["failed_jobs"],
        revocations["failed_hotels"],
    )
    return 1 if totals["failed_jobs"] or revocations["failed_jobs"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
