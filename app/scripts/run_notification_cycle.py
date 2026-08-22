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


def main() -> None:
    from app.tasks.notification_tasks import generate_daily_reports, process_outbox

    report_result = generate_daily_reports()
    logger.info("generate_daily_reports: %s", report_result)

    outbox_result = process_outbox()
    logger.info("process_outbox: %s", outbox_result)


if __name__ == "__main__":
    main()
