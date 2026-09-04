from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.api import events
from app.config import Settings
from app.dependencies.auth import AuthContext
from app.models.domain_event_outbox import DomainEventOutbox
from app.models.hotel_config import HotelConfiguration
from app.services import domain_events


def _event_engine():
    """A minimal SQLite engine with just the tables the after_commit hook writes to."""

    engine = create_engine("sqlite://")
    DomainEventOutbox.__table__.create(engine)
    return engine


class FakeRedis:
    def __init__(self):
        self.values: dict[str, int] = {}
        self.published: list[tuple[str, str]] = []
        self.pinged = False

    def ping(self):
        self.pinged = True
        return True

    def incr(self, key: str) -> int:
        self.values[key] = self.values.get(key, 0) + 1
        return self.values[key]

    def publish(self, channel: str, payload: str) -> int:
        self.published.append((channel, payload))
        return 1


def _settings(**overrides) -> Settings:
    values = {
        "REALTIME_EVENTS_ENABLED": True,
        "DISTRIBUTED_LOCK_REQUIRED": True,
        "REDIS_URL": "redis://localhost:6379/0",
    }
    values.update(overrides)
    return Settings(**values)


def test_realtime_fallback_poll_budget_is_below_ten_seconds():
    assert _settings().REALTIME_EVENTS_FALLBACK_POLL_SECONDS == 2.0
    with pytest.raises(ValueError):
        _settings(REALTIME_EVENTS_FALLBACK_POLL_SECONDS=6)


def test_publish_domain_event_scopes_channel_and_increments_revision(monkeypatch: pytest.MonkeyPatch):
    fake = FakeRedis()
    monkeypatch.setattr(domain_events, "_settings", lambda: _settings())
    monkeypatch.setattr(domain_events, "_get_redis_client", lambda: fake)

    first = domain_events.publish_domain_event(
        hotel_id=42,
        domain="reservations",
        event_type="reservation.created",
        payload={"reservation_id": 17, "source": "manual"},
    )
    second = domain_events.publish_domain_event(
        hotel_id=42,
        domain="reservations",
        event_type="reservation.payment_recorded",
        payload={"reservation_id": 17, "payment_id": 91},
    )

    assert first is not None
    assert second is not None
    assert first.revision == 1
    assert second.revision == 2
    assert first.channel == "hotel:42:events"
    assert fake.published[0][0] == "hotel:42:events"
    assert json.loads(fake.published[0][1]) == first.as_payload()
    assert "email" not in fake.published[0][1]
    assert "guest_name" not in fake.published[0][1]


def test_publish_domain_event_rejects_unknown_domain_or_sensitive_payload():
    with pytest.raises(ValueError, match="domain"):
        domain_events.validate_event_input(
            hotel_id=42,
            domain="unknown",
            event_type="x.changed",
            payload={},
        )


def test_security_permission_domain_accepts_effective_permissions_family():
    assert domain_events.validate_event_input(
        hotel_id=42,
        domain="security",
        event_type="permissions.changed",
        payload={"family": "effective_permissions"},
    ) == {"family": "effective_permissions"}


def test_permission_invalidation_publishes_without_error_logging(monkeypatch, caplog):
    from app.services import permission_service

    fake = FakeRedis()
    monkeypatch.setattr(domain_events, "_settings", lambda: _settings(DISTRIBUTED_LOCK_REQUIRED=True))
    monkeypatch.setattr(domain_events, "_get_redis_client", lambda: fake)

    with caplog.at_level("WARNING", logger="app.services.permission_service"):
        permission_service.publish_permission_invalidation(42)

    assert len(fake.published) == 1
    payload = json.loads(fake.published[0][1])
    assert payload["domain"] == "security"
    assert payload["event_type"] == "permissions.changed"
    assert payload["payload"] == {"family": "effective_permissions"}
    assert not any(record.levelno >= 40 for record in caplog.records)


def test_permission_invalidation_degrades_to_warning_for_unexpected_backend_failure(monkeypatch, caplog):
    from app.services import permission_service

    def fail_to_publish(**_kwargs):
        raise ConnectionError("redis unavailable")

    monkeypatch.setattr(domain_events, "publish_domain_event", fail_to_publish)

    with caplog.at_level("WARNING", logger="app.services.permission_service"):
        permission_service.publish_permission_invalidation(42)

    assert any(
        record.message == "permission_invalidation.failed" and record.levelno == 30
        for record in caplog.records
    )
    assert not any(record.levelno >= 40 for record in caplog.records)

    with pytest.raises(ValueError, match="payload key"):
        domain_events.validate_event_input(
            hotel_id=42,
            domain="guests",
            event_type="guest.changed",
            payload={"email": "private@example.test"},
        )


def test_optional_backend_degrades_without_fabricating_an_event(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(domain_events, "_settings", lambda: _settings(DISTRIBUTED_LOCK_REQUIRED=False))
    monkeypatch.setattr(domain_events, "_get_redis_client", lambda: None)

    assert domain_events.publish_domain_event(
        hotel_id=42,
        domain="analytics",
        event_type="analytics.invalidated",
        payload={"family": "home"},
    ) is None


def test_required_backend_raises_when_unavailable(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(domain_events, "_settings", lambda: _settings(DISTRIBUTED_LOCK_REQUIRED=True))
    monkeypatch.setattr(domain_events, "_get_redis_client", lambda: None)

    with pytest.raises(domain_events.RealtimeEventsUnavailable):
        domain_events.publish_domain_event(
            hotel_id=42,
            domain="rooms",
            event_type="room.changed",
            payload={"room_id": 7},
        )


def test_queued_domain_change_publishes_once_after_commit(monkeypatch: pytest.MonkeyPatch):
    published: list[dict] = []
    monkeypatch.setattr(domain_events, "publish_domain_event", lambda **kwargs: published.append(kwargs))
    session = Session(_event_engine())
    try:
        session.execute(text("SELECT 1"))
        domain_events.queue_domain_change(
            session,
            hotel_id=42,
            domain="payments",
            event_type="payment.changed",
            payload={"reservation_id": 17, "payment_id": 91},
        )
        # The collector is transaction-scoped and repeated model/service calls
        # must not publish the same signal twice.
        domain_events.queue_domain_change(
            session,
            hotel_id=42,
            domain="payments",
            event_type="payment.changed",
            payload={"reservation_id": 17, "payment_id": 91},
        )
        session.commit()
    finally:
        session.close()

    assert len(published) == 1
    assert published[0]["hotel_id"] == 42
    assert published[0]["domain"] == "payments"
    assert published[0]["event_type"] == "payment.changed"
    assert published[0]["payload"] == {"reservation_id": 17, "payment_id": 91}
    assert published[0]["event_id"]
    assert published[0]["cursor"] == 1
    assert published[0]["schema_version"] == 1


def test_queued_domain_change_is_discarded_on_rollback(monkeypatch: pytest.MonkeyPatch):
    published: list[dict] = []
    monkeypatch.setattr(domain_events, "publish_domain_event", lambda **kwargs: published.append(kwargs))
    session = Session(_event_engine())
    try:
        session.execute(text("SELECT 1"))
        domain_events.queue_domain_change(
            session,
            hotel_id=42,
            domain="reservations",
            event_type="reservation.changed",
            payload={"reservation_id": 17},
        )
        session.rollback()
        # A later successful transaction on the same Session must not flush a
        # signal for the rolled-back write.
        session.execute(text("SELECT 1"))
        session.commit()
    finally:
        session.close()

    assert published == []


def test_model_change_collector_fans_out_payment_dependencies_without_sensitive_fields(
    monkeypatch: pytest.MonkeyPatch,
):
    published: list[dict] = []
    monkeypatch.setattr(domain_events, "publish_domain_event", lambda **kwargs: published.append(kwargs))
    transaction = SimpleNamespace(
        __tablename__="transactions",
        hotel_id=42,
        id=91,
        reservation_id=17,
        status="completed",
        amount=1250,
        description="guest phone number",
    )
    session = SimpleNamespace(
        info={}, new=[transaction], dirty=[], deleted=[], add=lambda _row: None, get_bind=lambda: None
    )

    domain_events.queue_model_changes(session)
    domain_events.publish_queued_domain_changes(session)

    assert {event["domain"] for event in published} == {"payments", "cash", "analytics"}
    for event in published:
        assert event["payload"] == {
            "transaction_id": 91,
            "reservation_id": 17,
            "status": "completed",
        }
        assert "amount" not in event["payload"]
        assert "description" not in event["payload"]


def test_derived_analytics_changes_are_coalesced_by_family(monkeypatch: pytest.MonkeyPatch):
    published: list[dict] = []
    monkeypatch.setattr(domain_events, "publish_domain_event", lambda **kwargs: published.append(kwargs))
    session = SimpleNamespace(
        info={},
        new=[
            SimpleNamespace(__tablename__="fact_reservation_daily", hotel_id=42, id=1),
            SimpleNamespace(__tablename__="fact_reservation_daily", hotel_id=42, id=2),
        ],
        dirty=[],
        deleted=[],
        add=lambda _row: None,
        get_bind=lambda: None,
    )

    domain_events.queue_model_changes(session)
    domain_events.publish_queued_domain_changes(session)

    assert len(published) == 1
    assert published[0]["hotel_id"] == 42
    assert published[0]["domain"] == "analytics"
    assert published[0]["event_type"] == "analytics.read_model.changed"
    assert published[0]["payload"] == {"family": "reservation_daily"}
    assert published[0]["event_id"]


def test_session_hooks_publish_model_changes_only_after_commit(monkeypatch: pytest.MonkeyPatch):
    published: list[dict] = []
    monkeypatch.setattr(domain_events, "publish_domain_event", lambda **kwargs: published.append(kwargs))
    engine = _event_engine()
    HotelConfiguration.__table__.create(engine)
    session = Session(engine)
    try:
        config = HotelConfiguration(id=501, hotel_name="Commit hotel")
        session.add(config)
        session.flush()
        assert published == []
        session.commit()
        assert {event["domain"] for event in published} == {"settings", "analytics"}

        published.clear()
        session.add(HotelConfiguration(id=502, hotel_name="Rollback hotel"))
        session.flush()
        session.rollback()
        assert published == []
    finally:
        session.close()
        engine.dispose()


def test_nested_rollback_prunes_only_nested_realtime_signals(monkeypatch: pytest.MonkeyPatch):
    published: list[dict] = []
    monkeypatch.setattr(domain_events, "publish_domain_event", lambda **kwargs: published.append(kwargs))
    engine = _event_engine()
    HotelConfiguration.__table__.create(engine)
    session = Session(engine)
    try:
        session.add(HotelConfiguration(id=503, hotel_name="Outer hotel"))
        session.flush()
        try:
            with session.begin_nested():
                session.add(HotelConfiguration(id=504, hotel_name="Nested hotel"))
                session.flush()
                raise RuntimeError("rollback nested work")
        except RuntimeError:
            pass
        session.commit()
    finally:
        session.close()
        engine.dispose()

    assert published
    assert all(event["hotel_id"] == 503 for event in published)


def test_nested_commit_publishes_only_after_root_commit(monkeypatch: pytest.MonkeyPatch):
    published: list[dict] = []
    monkeypatch.setattr(domain_events, "publish_domain_event", lambda **kwargs: published.append(kwargs))
    engine = _event_engine()
    HotelConfiguration.__table__.create(engine)
    session = Session(engine)
    try:
        session.add(HotelConfiguration(id=505, hotel_name="Outer hotel"))
        session.flush()
        with session.begin_nested():
            session.add(HotelConfiguration(id=506, hotel_name="Nested hotel"))
            session.flush()
        assert published == []
        session.commit()
    finally:
        session.close()
        engine.dispose()

    assert {event["hotel_id"] for event in published} == {505, 506}


def test_stream_endpoint_sets_no_cache_headers_and_tenant_stream(monkeypatch: pytest.MonkeyPatch):
    fake = FakeRedis()

    class FakePubSub:
        def subscribe(self, channel: str):
            self.channel = channel

        def get_message(self, timeout: int):
            return None

        def close(self):
            return None

    fake.pubsub = lambda **kwargs: FakePubSub()
    monkeypatch.setattr(events, "get_realtime_client", lambda: fake)
    monkeypatch.setattr(events, "get_settings", lambda: _settings(REALTIME_EVENTS_HEARTBEAT_SECONDS=10))

    class ClosableDb:
        closed = False

        def close(self):
            self.closed = True

    db = ClosableDb()
    response = events.stream_domain_events(
        AuthContext(hotel_id=42, user_id=9, user_role="owner", is_verified=True),
        db,
    )
    assert response.media_type == "text/event-stream"
    assert response.headers["cache-control"] == "no-cache, no-store"
    assert db.closed is True
    async def read_first_frame():
        return await response.body_iterator.__anext__()

    first_frame = asyncio.run(read_first_frame())
    assert '"hotel_id": 42' in first_frame


def test_stream_closes_with_control_event_when_membership_is_revoked(monkeypatch: pytest.MonkeyPatch):
    fake = FakeRedis()

    class FakePubSub:
        def subscribe(self, channel: str):
            self.channel = channel

        def get_message(self, timeout: int):
            return None

        def close(self):
            return None

    fake.pubsub = lambda **kwargs: FakePubSub()
    clock = iter((0.0, 61.0, 61.0))
    monkeypatch.setattr(domain_events.time, "monotonic", lambda: next(clock))
    stream = domain_events.iter_event_stream(
        42,
        fake,
        heartbeat_seconds=1,
        authorization_check=lambda: False,
        authorization_revalidate_seconds=60,
    )
    assert '"status": "ready"' in next(stream)
    control = next(stream)
    assert "event: control" in control
    assert "authorization_lost" in control


def test_stream_endpoint_uses_postgres_transport_when_redis_is_unavailable(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(events, "get_realtime_client", lambda: None)
    monkeypatch.setattr(
        events,
        "get_settings",
        lambda: _settings(REALTIME_EVENTS_FALLBACK_POLL_SECONDS=1),
    )
    monkeypatch.setattr(
        events,
        "iter_postgres_event_stream",
        lambda *args, **kwargs: iter(["event: ready\ndata: {\"transport\": \"postgres-outbox\"}\n\n"]),
    )

    class ClosableDb:
        closed = False

        def close(self):
            self.closed = True

    db = ClosableDb()
    response = events.stream_domain_events(
        AuthContext(hotel_id=42, user_id=9, user_role="owner", is_verified=True),
        db,
    )
    assert response.headers["x-realtime-transport"] == "postgres-outbox"
    assert db.closed is True


def test_postgres_fallback_stream_reads_committed_outbox_without_payload():
    engine = _event_engine()
    factory = sessionmaker(bind=engine)
    session = factory()
    session.add(
        DomainEventOutbox(
            event_id="00000000-0000-0000-0000-000000000042",
            hotel_id=42,
            domain="reservations",
            event_type="reservation.updated",
            payload={"reservation_id": 7},
            schema_version=1,
            stream_cursor=17,
            revision=3,
            occurred_at=datetime.now(timezone.utc),
            status="pending",
        )
    )
    session.commit()
    session.close()

    stream = domain_events.iter_postgres_event_stream(
        42,
        after_cursor=0,
        poll_seconds=1,
        session_factory=factory,
    )
    assert '"transport": "postgres-outbox"' in next(stream)
    frame = next(stream)
    assert '"cursor": 17' in frame
    assert '"payload": {}' in frame
    assert '"reservation_id": 7' not in frame
    stream.close()
    engine.dispose()


def test_postgres_fallback_stream_starts_after_latest_cursor_when_cursor_is_omitted(monkeypatch: pytest.MonkeyPatch):
    engine = _event_engine()
    factory = sessionmaker(bind=engine)
    session = factory()
    session.add(
        DomainEventOutbox(
            event_id="00000000-0000-0000-0000-000000000043",
            hotel_id=42,
            domain="reservations",
            event_type="reservation.updated",
            payload={},
            stream_cursor=22,
            occurred_at=datetime.now(timezone.utc),
            status="published",
        )
    )
    session.commit()
    session.close()

    stream = domain_events.iter_postgres_event_stream(
        42,
        poll_seconds=1,
        session_factory=factory,
    )
    ready = next(stream)
    assert '"cursor": 22' in ready
    class StopPolling(Exception):
        pass

    monkeypatch.setattr(domain_events.time, "sleep", lambda _seconds: (_ for _ in ()).throw(StopPolling()))
    assert next(stream) == ": heartbeat\n\n"
    with pytest.raises(StopPolling):
        next(stream)
    engine.dispose()


def test_postgres_fallback_stream_caps_poll_interval_at_five_seconds(monkeypatch: pytest.MonkeyPatch):
    engine = _event_engine()
    factory = sessionmaker(bind=engine)
    stream = domain_events.iter_postgres_event_stream(
        42,
        after_cursor=0,
        poll_seconds=60,
        session_factory=factory,
    )
    assert '"transport": "postgres-outbox"' in next(stream)

    class StopPolling(Exception):
        pass

    sleep_calls: list[float] = []

    def stop_after_recording(seconds: float):
        sleep_calls.append(seconds)
        raise StopPolling()

    monkeypatch.setattr(domain_events.time, "sleep", stop_after_recording)
    assert next(stream) == ": heartbeat\n\n"
    with pytest.raises(StopPolling):
        next(stream)
    assert sleep_calls == [5.0]
    stream.close()
    engine.dispose()
