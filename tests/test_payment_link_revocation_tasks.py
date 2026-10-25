from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from app.models.hotel_config import HotelConfiguration
from app.tasks import payment_link_revocation_tasks as revocation_tasks
from app.tasks import run_scheduled_hotel_jobs as cron_entrypoint


class _HotelRowsQuery:
    def __init__(self, rows):
        self.rows = rows

    def order_by(self, *_args):
        return self

    def all(self):
        return list(self.rows)


class _FakeSession:
    def __init__(self, hotel_ids):
        self.hotel_ids = hotel_ids
        self.query_entities = []
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def query(self, *entities):
        self.query_entities.append(entities)
        return _HotelRowsQuery((hotel_id,) for hotel_id in self.hotel_ids)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True


def test_closed_provider_lane_skips_before_opening_database_or_claiming(monkeypatch):
    settings = SimpleNamespace(DATABASE_URL="postgresql://synthetic")
    monkeypatch.setattr(revocation_tasks, "get_settings", lambda: settings)
    monkeypatch.setattr(
        revocation_tasks,
        "external_connections_enabled",
        lambda received: received is not settings,
    )

    def unexpected(*_args, **_kwargs):
        raise AssertionError("database/session must not be opened while provider lane is closed")

    monkeypatch.setattr(revocation_tasks, "get_engine", unexpected)
    monkeypatch.setattr(revocation_tasks, "sessionmaker", unexpected)
    monkeypatch.setattr(revocation_tasks, "process_payment_link_revocations", unexpected)

    result = revocation_tasks.run_payment_link_revocation_tasks()

    assert result["external_connections_disabled"] == 1
    assert result["skipped"] == 1
    assert result["hotels_scanned"] == 0
    assert result["attempts_used"] == 0
    assert result["failed_jobs"] == 0


def test_enabled_task_visits_active_and_inactive_hotels_under_each_context(monkeypatch):
    inactive_hotel, active_hotel = 91_001, 91_002
    subscriptions = {inactive_hotel: False, active_hotel: True}
    db = _FakeSession([inactive_hotel, active_hotel])
    engine = SimpleNamespace(disposed=False)
    engine.dispose = lambda: setattr(engine, "disposed", True)
    settings = SimpleNamespace(DATABASE_URL="postgresql://synthetic")
    current_hotel: list[int] = []
    provider_service_calls: list[tuple[int, bool, int]] = []

    monkeypatch.setattr(revocation_tasks, "get_settings", lambda: settings)
    monkeypatch.setattr(
        revocation_tasks, "external_connections_enabled", lambda _settings: True
    )
    monkeypatch.setattr(
        revocation_tasks,
        "get_engine",
        lambda url: engine if url == settings.DATABASE_URL else None,
    )
    monkeypatch.setattr(
        revocation_tasks, "sessionmaker", lambda *, bind: lambda: db
    )
    monkeypatch.setattr(
        revocation_tasks,
        "set_tenant_hotel_context",
        lambda _db, hotel_id: current_hotel.append(hotel_id),
    )

    def process_one(_db, hotel_id, *, limit):
        assert current_hotel[-1] == hotel_id
        provider_service_calls.append((hotel_id, subscriptions[hotel_id], limit))
        return {"processed": 1, "succeeded": 1, "failed": 0, "skipped": 0}

    monkeypatch.setattr(
        revocation_tasks, "process_payment_link_revocations", process_one
    )

    result = revocation_tasks.run_payment_link_revocation_tasks()

    assert db.query_entities == [(HotelConfiguration.id,)]
    assert provider_service_calls == [
        (inactive_hotel, False, 1),
        (active_hotel, True, 1),
    ]
    assert result["hotels_scanned"] == 2
    assert result["hotels_visited"] == 2
    assert result["attempts_used"] == result["attempt_limit"] == 2
    assert result["succeeded"] == result["processed"] == 2
    assert result["failed_jobs"] == 0
    assert db.closed is True
    assert engine.disposed is True


def test_two_link_batch_rotates_between_five_minute_cycles(monkeypatch):
    hotel_ids = [91_101, 91_102, 91_103, 91_104, 91_105]
    now = datetime(2026, 10, 22, 12, 0, tzinfo=UTC)
    first_cycle_slot = int(now.timestamp()) // revocation_tasks.SCHEDULE_INTERVAL_SECONDS
    all_calls: list[int] = []

    def run_cycle(cycle_time):
        db = _FakeSession(hotel_ids)
        current_hotel: list[int] = []
        monkeypatch.setattr(
            revocation_tasks,
            "set_tenant_hotel_context",
            lambda _db, hotel_id: current_hotel.append(hotel_id),
        )

        def process_one(_db, hotel_id, *, limit):
            assert limit == 1
            assert current_hotel[-1] == hotel_id
            all_calls.append(hotel_id)
            return {"processed": 1, "succeeded": 1, "failed": 0, "skipped": 0}

        monkeypatch.setattr(
            revocation_tasks, "process_payment_link_revocations", process_one
        )
        return revocation_tasks._process_pending_revocations(db, now=cycle_time)

    first = run_cycle(now)
    second = run_cycle(now + timedelta(seconds=revocation_tasks.SCHEDULE_INTERVAL_SECONDS))

    first_start = (first_cycle_slot * 2) % len(hotel_ids)
    second_start = ((first_cycle_slot + 1) * 2) % len(hotel_ids)
    assert all_calls[:2] == [
        hotel_ids[first_start],
        hotel_ids[(first_start + 1) % len(hotel_ids)],
    ]
    assert all_calls[2:] == [
        hotel_ids[second_start],
        hotel_ids[(second_start + 1) % len(hotel_ids)],
    ]
    assert first["attempts_used"] == second["attempts_used"] == 2


def test_cron_runs_provider_phase_after_sql_hotel_jobs(monkeypatch):
    events: list[str] = []
    monkeypatch.setattr(
        cron_entrypoint,
        "run_scheduled_hotel_jobs",
        lambda: events.append("sql")
        or {
            "hotels_scanned": 0,
            "active_hotels_scanned": 0,
            "no_shows_scanned": 0,
            "no_shows_marked": 0,
            "reports_generated": 0,
            "notifications_processed": 0,
            "notifications_sent": 0,
            "notifications_failed": 0,
            "notifications_deferred": 0,
            "notifications_retried": 0,
            "analytics_facts_processed": 0,
            "analytics_facts_deferred": 0,
            "failed_jobs": 0,
            "failed_hotels": 0,
        },
    )
    monkeypatch.setattr(
        cron_entrypoint,
        "run_payment_link_revocation_tasks",
        lambda: events.append("provider")
        or {
            "hotels_scanned": 0,
            "hotels_visited": 0,
            "processed": 0,
            "succeeded": 0,
            "failed": 0,
            "skipped": 0,
            "attempts_used": 0,
            "attempt_limit": 2,
            "external_connections_disabled": 0,
            "failed_jobs": 0,
            "failed_hotels": 0,
        },
    )

    assert cron_entrypoint.main() == 0
    assert events == ["sql", "provider"]
