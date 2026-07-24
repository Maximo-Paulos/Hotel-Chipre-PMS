from __future__ import annotations

from datetime import date

from app.services import analytics_warehouse
from app.tasks.celery_app import celery_app


def test_derived_analytics_has_incremental_and_nightly_schedules():
    schedule = celery_app.conf.beat_schedule

    assert schedule["analytics-derived-facts-incremental"]["task"] == (
        "analytics.project_all_derived_facts_incremental"
    )
    assert schedule["analytics-derived-facts-incremental"]["schedule"] == 300.0
    assert schedule["analytics-derived-facts-nightly-reconciliation"]["task"] == (
        "analytics.reconcile_all_derived_facts_nightly"
    )


def test_date_dimension_is_global_and_bounded():
    rows = analytics_warehouse.build_date_dimension_rows(date(2026, 7, 1), date(2026, 7, 3))

    assert [row["calendar_date"] for row in rows] == [
        "2026-07-01",
        "2026-07-02",
        "2026-07-03",
    ]
    assert all("hotel_id" not in row for row in rows)
