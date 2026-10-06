"""CLI entry point for the database-only no-show Render Cron job."""
from __future__ import annotations

import logging

from app.services.no_show_sweep_service import run_no_show_sweep

logger = logging.getLogger(__name__)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        totals = run_no_show_sweep()
    except Exception as exc:
        logger.error("no_show_cron.failed error_type=%s", type(exc).__name__)
        return 1

    logger.info(
        "no_show_cron.completed hotels_scanned=%s scanned=%s marked=%s failed_hotels=%s",
        totals["hotels_scanned"],
        totals["scanned"],
        totals["marked"],
        totals["failed_hotels"],
    )
    return 1 if totals["failed_hotels"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
