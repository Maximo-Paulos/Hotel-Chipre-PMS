from __future__ import annotations

from sqlalchemy import event
from sqlalchemy.orm import Session

from app.models.hotel_config import HotelConfiguration
from app.services import scheduled_hotel_jobs_service as scheduled_jobs


def test_scheduled_jobs_enumerate_hotels_once_and_scope_each_job(db: Session, db_engine, monkeypatch):
    db.add_all(
        [
            HotelConfiguration(id=7101, subscription_active=True),
            HotelConfiguration(id=7102, subscription_active=False),
        ]
    )
    db.commit()

    hotel_context: list[int] = []
    calls: list[tuple[str, int]] = []
    hotel_rows_selects: list[str] = []

    def record_query(_conn, _cursor, statement, _parameters, _context, _executemany):
        if "FROM hotel_configuration" in statement and "subscription_active" in statement:
            hotel_rows_selects.append(statement)

    event.listen(db_engine, "before_cursor_execute", record_query)
    monkeypatch.setattr(
        scheduled_jobs,
        "set_tenant_hotel_context",
        lambda _db, hotel_id: hotel_context.append(hotel_id),
    )
    monkeypatch.setattr(
        scheduled_jobs,
        "process_analytics_fact_refresh_queue_for_hotel",
        lambda _db, *, hotel_id, batch_size: calls.append(("analytics_facts", hotel_context[-1]))
        or {"processed": 3, "deferred": 0},
    )
    monkeypatch.setattr(
        scheduled_jobs,
        "sweep_no_shows",
        lambda _db, *, hotel_id, tenant_context_already_set: calls.append(("no_show", hotel_context[-1]))
        or {"scanned": 1, "marked": 0},
    )
    monkeypatch.setattr(
        scheduled_jobs,
        "generate_due_daily_reports",
        lambda _db: calls.append(("report", hotel_context[-1]))
        or [{"hotel_id": hotel_context[-1]}],
    )
    monkeypatch.setattr(
        scheduled_jobs,
        "process_pending_outbox",
        lambda _db: calls.append(("outbox", hotel_context[-1]))
        or {"processed": 2, "sent": 2},
    )

    try:
        totals = scheduled_jobs.process_scheduled_hotel_jobs(db)
    finally:
        event.remove(db_engine, "before_cursor_execute", record_query)

    assert len(hotel_rows_selects) == 1
    assert calls == [
        ("analytics_facts", 7101),
        ("no_show", 7101),
        ("report", 7101),
        ("outbox", 7101),
        ("analytics_facts", 7102),
        ("no_show", 7102),
    ]
    assert totals == {
        "hotels_scanned": 2,
        "active_hotels_scanned": 1,
        "no_shows_scanned": 2,
        "no_shows_marked": 0,
        "reports_generated": 1,
        "notifications_processed": 2,
        "notifications_sent": 2,
        "notifications_failed": 0,
        "notifications_expired": 0,
        "notifications_retried": 0,
        "notifications_deferred": 0,
        "analytics_facts_processed": 6,
        "analytics_facts_deferred": 0,
        "failed_jobs": 0,
        "failed_hotels": 0,
    }


def test_one_scheduled_job_failure_does_not_skip_other_jobs_or_hotels(db: Session, monkeypatch, caplog):
    db.add_all(
        [
            HotelConfiguration(id=7201, subscription_active=True),
            HotelConfiguration(id=7202, subscription_active=True),
        ]
    )
    db.commit()

    current_hotel: list[int] = []
    calls: list[tuple[str, int]] = []
    monkeypatch.setattr(
        scheduled_jobs,
        "set_tenant_hotel_context",
        lambda _db, hotel_id: current_hotel.append(hotel_id),
    )
    monkeypatch.setattr(
        scheduled_jobs,
        "process_analytics_fact_refresh_queue_for_hotel",
        lambda _db, *, hotel_id, batch_size: calls.append(("analytics_facts", hotel_id))
        or {"processed": 0, "deferred": 0},
    )
    monkeypatch.setattr(
        scheduled_jobs,
        "sweep_no_shows",
        lambda _db, *, hotel_id, tenant_context_already_set: calls.append(("no_show", hotel_id))
        or {"scanned": 0, "marked": 0},
    )

    def reports(_db):
        hotel_id = current_hotel[-1]
        calls.append(("report", hotel_id))
        if hotel_id == 7201:
            raise RuntimeError("synthetic report failure")
        return []

    monkeypatch.setattr(scheduled_jobs, "generate_due_daily_reports", reports)
    monkeypatch.setattr(
        scheduled_jobs,
        "process_pending_outbox",
        lambda _db: calls.append(("outbox", current_hotel[-1])) or {},
    )

    totals = scheduled_jobs.process_scheduled_hotel_jobs(db)

    assert calls == [
        ("analytics_facts", 7201),
        ("no_show", 7201),
        ("report", 7201),
        ("outbox", 7201),
        ("analytics_facts", 7202),
        ("no_show", 7202),
        ("report", 7202),
        ("outbox", 7202),
    ]
    assert totals["failed_jobs"] == 1
    assert totals["failed_hotels"] == 1
    assert "job=daily_reports error_type=RuntimeError" in caplog.text
