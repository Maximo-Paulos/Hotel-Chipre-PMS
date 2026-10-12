"""One-shot notification cycle: generate due daily reports, then deliver
pending outbox rows. No Celery worker/beat/Redis required -- both task
functions are plain, synchronously callable (see app/tasks/notification_tasks.py).

Intended as a Render Cron Job command:
    python -m app.scripts.run_notification_cycle
"""
from __future__ import annotations

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main() -> int:
    from app.tasks.notification_tasks import generate_daily_reports, process_outbox

    report_result = generate_daily_reports.run()
    logger.info("generate_daily_reports hotels_reported=%s", report_result.get("hotels_reported", 0))

    outbox_result = process_outbox.run()
    logger.info(
        "process_outbox processed=%s sent=%s failed=%s expired=%s retried=%s deferred=%s",
        outbox_result.get("processed", 0),
        outbox_result.get("sent", 0),
        outbox_result.get("failed", 0),
        outbox_result.get("expired", 0),
        outbox_result.get("retried", 0),
        outbox_result.get("deferred", 0),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
