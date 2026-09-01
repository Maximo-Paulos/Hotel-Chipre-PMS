from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.dialects import postgresql

from app.models.domain_event_outbox import DomainEventOutbox
from app.models.hotel_config import HotelConfiguration
from app.services import domain_events
from app.tasks.celery_app import celery_app


def _seed_hotels(db, *hotel_ids: int) -> None:
    db.execute(
        HotelConfiguration.__table__.insert(),
        [{"id": hotel_id, "subscription_active": True} for hotel_id in hotel_ids],
    )
    db.commit()


def _outbox_row(*, hotel_id: int, event_type: str = "analytics.changed", **kwargs):
    return DomainEventOutbox(
        hotel_id=hotel_id,
        domain="analytics",
        event_type=event_type,
        payload={"family": "home"},
        **kwargs,
    )


def _successful_event(**kwargs):
    occurred_at = kwargs.get("occurred_at")
    if isinstance(occurred_at, datetime):
        occurred_at = occurred_at.isoformat()
    return domain_events.DomainEvent(
        hotel_id=kwargs["hotel_id"],
        domain=kwargs["domain"],
        event_type=kwargs["event_type"],
        revision=kwargs.get("revision") or 11,
        occurred_at=occurred_at or datetime.now(timezone.utc).isoformat(),
        payload=dict(kwargs.get("payload") or {}),
    )


def test_after_commit_publish_failure_leaves_row_for_worker_restart(db, monkeypatch):
    _seed_hotels(db, 1)

    def fail_after_commit(**_kwargs):
        raise ConnectionError("redis connection details must not be persisted")

    monkeypatch.setattr(domain_events, "publish_domain_event", fail_after_commit)
    domain_events.queue_domain_change(
        db,
        hotel_id=1,
        domain="analytics",
        event_type="analytics.changed",
        payload={"family": "home"},
    )
    db.commit()

    pending = db.query(DomainEventOutbox).filter(DomainEventOutbox.hotel_id == 1).one()
    assert pending.published_at is None
    assert pending.attempts == 1
    assert pending.last_error == "ConnectionError"

    published = []
    monkeypatch.setattr(
        domain_events,
        "publish_domain_event",
        lambda **kwargs: published.append(kwargs) or _successful_event(**kwargs),
    )
    result = domain_events.publish_pending_domain_events(db, hotel_id=1)
    db.commit()

    assert result["selected"] == 1
    assert result["published"] == 1
    assert result["failed"] == 0
    assert published[0]["hotel_id"] == 1
    refreshed = db.query(DomainEventOutbox).filter(DomainEventOutbox.hotel_id == 1).one()
    assert refreshed.published_at is not None
    assert refreshed.revision == 11
    assert refreshed.attempts == 2
    assert refreshed.last_error is None


def test_celery_task_drains_row_after_after_commit_failure(tmp_path, monkeypatch):
    database_url = f"sqlite:///{tmp_path / 'celery-outbox.db'}"
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    engine = create_engine(database_url)
    HotelConfiguration.__table__.create(engine)
    DomainEventOutbox.__table__.create(engine)
    db = Session(engine)
    try:
        _seed_hotels(db, 1)

        def fail_after_commit(**_kwargs):
            raise ConnectionError("transport unavailable")

        monkeypatch.setattr(domain_events, "publish_domain_event", fail_after_commit)
        domain_events.queue_domain_change(
            db,
            hotel_id=1,
            domain="analytics",
            event_type="analytics.changed",
            payload={"family": "home"},
        )
        db.commit()
    finally:
        db.close()
        engine.dispose()

    monkeypatch.setattr(
        domain_events,
        "publish_domain_event",
        lambda **kwargs: _successful_event(**kwargs),
    )
    result = celery_app.tasks["domain_events.publish_outbox"].run(database_url=database_url)

    assert result["selected"] == 1
    assert result["published"] == 1
    verify_engine = create_engine(database_url)
    verify_db = Session(verify_engine)
    try:
        row = verify_db.query(DomainEventOutbox).one()
        assert row.published_at is not None
        assert row.attempts == 2
    finally:
        verify_db.close()
        verify_engine.dispose()


def test_rollback_removes_durable_event_row(db):
    _seed_hotels(db, 1)
    domain_events.queue_domain_change(
        db,
        hotel_id=1,
        domain="reservations",
        event_type="reservation.changed",
        payload={"reservation_id": 9},
    )
    db.flush()
    assert db.query(DomainEventOutbox).count() == 1

    db.rollback()

    assert db.query(DomainEventOutbox).count() == 0


def test_worker_is_tenant_scoped_and_uses_stored_revision(db, monkeypatch):
    _seed_hotels(db, 1, 2)
    stored_time = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)
    db.add_all(
        [
            _outbox_row(hotel_id=1, revision=7, occurred_at=stored_time),
            _outbox_row(hotel_id=2, revision=8, occurred_at=stored_time),
        ]
    )
    db.commit()

    published = []
    monkeypatch.setattr(
        domain_events,
        "publish_domain_event",
        lambda **kwargs: published.append(kwargs) or _successful_event(**kwargs),
    )
    result = domain_events.publish_pending_domain_events(db, hotel_id=1)
    db.commit()

    assert result["published"] == 1
    assert [item["hotel_id"] for item in published] == [1]
    assert published[0]["revision"] == 7
    assert published[0]["occurred_at"] == stored_time
    hotel_one = db.query(DomainEventOutbox).filter(DomainEventOutbox.hotel_id == 1).one()
    hotel_two = db.query(DomainEventOutbox).filter(DomainEventOutbox.hotel_id == 2).one()
    assert hotel_one.published_at is not None
    assert hotel_two.published_at is None


def test_worker_records_bounded_failure_and_backoff_without_error_message(db, monkeypatch):
    _seed_hotels(db, 1)
    db.add(_outbox_row(hotel_id=1))
    db.commit()

    def fail_publish(**_kwargs):
        raise RuntimeError("DSN, token, and guest data must not enter last_error")

    monkeypatch.setattr(domain_events, "publish_domain_event", fail_publish)
    result = domain_events.publish_pending_domain_events(db, hotel_id=1)
    db.commit()

    assert result["failed"] == 1
    assert result["retry_after_seconds"] == domain_events.OUTBOX_RETRY_BASE_SECONDS
    row = db.query(DomainEventOutbox).filter(DomainEventOutbox.hotel_id == 1).one()
    assert row.published_at is None
    assert row.attempts == 1
    assert row.last_error == "publish_failed:RuntimeError"
    assert "DSN" not in row.last_error


def test_old_pending_row_emits_stale_metric_alert(db, caplog):
    _seed_hotels(db, 1)
    now = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)
    db.add(_outbox_row(hotel_id=1, occurred_at=now - timedelta(minutes=10)))
    db.commit()

    with caplog.at_level("WARNING", logger="app.services.domain_events"):
        metrics = domain_events.get_domain_event_outbox_metrics(
            db,
            hotel_id=1,
            now=now,
            stale_after_seconds=60,
        )

    assert metrics["pending_count"] == 1
    assert metrics["oldest_age_seconds"] == 600.0
    assert metrics["stale"] is True
    assert any(record.message == "realtime_events.outbox_stale" for record in caplog.records)


def test_worker_query_contains_postgresql_skip_locked_clause(db):
    query = (
        db.query(DomainEventOutbox)
        .filter(
            DomainEventOutbox.hotel_id == 1,
            DomainEventOutbox.published_at.is_(None),
        )
        .order_by(DomainEventOutbox.id.asc())
        .with_for_update(skip_locked=True)
        .limit(100)
    )
    sql = str(query.statement.compile(dialect=postgresql.dialect()))
    assert "FOR UPDATE SKIP LOCKED" in sql


def test_invalid_worker_tenant_is_rejected(db):
    with pytest.raises(ValueError, match="hotel_id"):
        domain_events.publish_pending_domain_events(db, hotel_id=0)


def test_celery_registers_durable_outbox_task():
    assert "domain_events.publish_outbox" in celery_app.tasks
