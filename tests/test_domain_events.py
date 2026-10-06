from __future__ import annotations

import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.schema import CreateIndex

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


def _thread_safe_event_engine():
    """Share the in-memory SQLite connection with async iterator worker threads."""

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
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


def _successful_publisher(published: list[dict]):
    def publish(**kwargs):
        published.append(kwargs)
        return SimpleNamespace(revision=len(published))

    return publish


def test_realtime_fallback_poll_budget_is_below_ten_seconds():
    assert _settings().REALTIME_EVENTS_FALLBACK_POLL_SECONDS == 2.0
    with pytest.raises(ValueError):
        _settings(REALTIME_EVENTS_FALLBACK_POLL_SECONDS=6)


def test_outbox_recovery_index_matches_tenant_scoped_effective_cursor_expression():
    recovery_index = next(
        index
        for index in DomainEventOutbox.__table__.indexes
        if index.name == "ix_domain_event_outbox_recovery_cursor"
    )

    ddl = str(CreateIndex(recovery_index).compile(dialect=postgresql.dialect())).lower()

    assert "(hotel_id, coalesce(stream_cursor, id))" in ddl


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
    # Direct permission invalidation is best effort and must bypass the
    # durable outbox cooldown.
    domain_events._outbox_publish_cooldown.record_failure()
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


def test_outbox_cooldown_skips_later_durable_transaction_without_touching_row_metadata(
    monkeypatch: pytest.MonkeyPatch,
):
    class FakeClock:
        now = 100.0

        def monotonic(self) -> float:
            return self.now

    clock = FakeClock()
    monkeypatch.setattr(
        domain_events,
        "_outbox_publish_cooldown",
        domain_events._OutboxPublishCooldown(monotonic=clock.monotonic),
    )
    attempted: list[dict] = []

    def publish(**kwargs):
        attempted.append(kwargs)
        if kwargs["event_type"] == "rooms.first_failed":
            raise ConnectionError("redis unavailable")
        return SimpleNamespace(revision=len(attempted))

    monkeypatch.setattr(domain_events, "publish_domain_event", publish)
    engine = _event_engine()
    try:
        with Session(engine) as first_session:
            first_session.execute(text("SELECT 1"))
            domain_events.queue_domain_change(
                first_session,
                hotel_id=42,
                domain="rooms",
                event_type="rooms.first_failed",
                payload={"room_id": 1},
            )
            first_session.commit()

        with Session(engine) as second_session:
            second_session.execute(text("SELECT 1"))
            domain_events.queue_domain_change(
                second_session,
                hotel_id=42,
                domain="reservations",
                event_type="reservations.cooldown_skipped",
                payload={"reservation_id": 2},
            )
            domain_events.queue_domain_change(
                second_session,
                hotel_id=42,
                domain="settings",
                event_type="settings.best_effort",
                payload={"family": "hotel"},
                durable=False,
            )
            second_session.commit()

        assert [event["event_type"] for event in attempted] == [
            "rooms.first_failed",
            "settings.best_effort",
        ]
        assert "event_id" not in attempted[-1]

        with Session(engine) as verification_session:
            rows = verification_session.query(DomainEventOutbox).order_by(DomainEventOutbox.id).all()
            state_by_type = {
                row.event_type: (
                    row.status,
                    row.attempts,
                    row.revision,
                    row.last_error,
                    row.next_attempt_at,
                )
                for row in rows
            }

        failed_status, failed_attempts, _, failed_error, failed_next_attempt = state_by_type[
            "rooms.first_failed"
        ]
        assert failed_status == "pending"
        assert failed_attempts == 1
        assert failed_error == "ConnectionError"
        assert failed_next_attempt is not None
        assert state_by_type["reservations.cooldown_skipped"] == (
            "pending",
            0,
            0,
            None,
            None,
        )
    finally:
        engine.dispose()


def test_outbox_cooldown_allows_one_probe_after_expiry_and_success_clears_it():
    class FakeClock:
        now = 100.0

        def monotonic(self) -> float:
            return self.now

    clock = FakeClock()
    cooldown = domain_events._OutboxPublishCooldown(
        cooldown_seconds=30.0,
        monotonic=clock.monotonic,
    )

    initial_permit = cooldown.try_acquire()
    assert initial_permit is not None
    cooldown.record_failure()
    assert cooldown.try_acquire() is None

    clock.now += 30.0
    with ThreadPoolExecutor(max_workers=8) as pool:
        permits = list(pool.map(lambda _index: cooldown.try_acquire(), range(16)))

    probes = [permit for permit in permits if permit is not None]
    assert len(probes) == 1
    assert probes[0].probe_generation is not None
    cooldown.record_success(probes[0])

    after_success = cooldown.try_acquire()
    assert after_success is not None
    assert after_success.probe_generation is None

    cooldown.record_failure()
    assert cooldown.try_acquire() is None


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
    monkeypatch.setattr(domain_events, "publish_domain_event", _successful_publisher(published))
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


@pytest.mark.parametrize("first_failure", ["exception", "none"])
def test_failed_durable_publish_leaves_later_durable_rows_pending_but_attempts_ephemeral_events(
    monkeypatch: pytest.MonkeyPatch,
    first_failure: str,
):
    attempted: list[dict] = []

    def publish(**kwargs):
        attempted.append(kwargs)
        if kwargs["event_type"] == "rooms.first":
            if first_failure == "exception":
                raise ConnectionError("redis unavailable")
            return None
        return SimpleNamespace(revision=len(attempted))

    monkeypatch.setattr(domain_events, "publish_domain_event", publish)
    engine = _event_engine()
    session = Session(engine)
    try:
        session.execute(text("SELECT 1"))
        domain_events.queue_domain_change(
            session,
            hotel_id=42,
            domain="rooms",
            event_type="rooms.first",
            payload={"room_id": 1},
        )
        domain_events.queue_domain_change(
            session,
            hotel_id=42,
            domain="reservations",
            event_type="reservations.later",
            payload={"reservation_id": 2},
        )
        domain_events.queue_domain_change(
            session,
            hotel_id=42,
            domain="settings",
            event_type="settings.ephemeral",
            payload={"family": "hotel"},
            durable=False,
        )
        session.commit()
    finally:
        session.close()

    assert [event["event_type"] for event in attempted] == [
        "rooms.first",
        "settings.ephemeral",
    ]
    assert "event_id" in attempted[0]
    assert "event_id" not in attempted[1]

    with Session(engine) as verification_session:
        rows = verification_session.query(DomainEventOutbox).order_by(DomainEventOutbox.event_type).all()
        state_by_type = {
            row.event_type: (row.status, row.attempts, row.last_error)
            for row in rows
        }
        event_ids_by_type = {row.event_type: row.event_id for row in rows}

    expected_error = "ConnectionError" if first_failure == "exception" else "RealtimeEventsUnavailable"
    assert state_by_type == {
        "reservations.later": ("pending", 0, None),
        "rooms.first": ("pending", 1, expected_error),
    }

    recovered: list[dict] = []
    monkeypatch.setattr(domain_events, "publish_domain_event", _successful_publisher(recovered))
    with Session(engine) as recovery_session:
        replay_result = domain_events.publish_pending_domain_events(recovery_session, hotel_id=42)
        recovery_session.commit()

    assert replay_result == {
        "selected": 2,
        "published": 2,
        "failed": 0,
        "retry_after_seconds": None,
    }
    assert [event["event_type"] for event in recovered] == ["rooms.first", "reservations.later"]
    assert {event["event_type"]: event["event_id"] for event in recovered} == event_ids_by_type

    with Session(engine) as verification_session:
        replayed_rows = verification_session.query(DomainEventOutbox).order_by(DomainEventOutbox.event_type).all()
        replayed_state_by_type = {
            row.event_type: (row.status, row.attempts, row.last_error)
            for row in replayed_rows
        }

    assert replayed_state_by_type == {
        "reservations.later": ("published", 1, None),
        "rooms.first": ("published", 2, None),
    }
    engine.dispose()


def test_successful_batch_publishes_each_durable_and_ephemeral_event(monkeypatch: pytest.MonkeyPatch):
    attempted: list[dict] = []

    def publish(**kwargs):
        attempted.append(kwargs)
        return SimpleNamespace(revision=len(attempted))

    monkeypatch.setattr(domain_events, "publish_domain_event", publish)
    engine = _event_engine()
    session = Session(engine)
    try:
        session.execute(text("SELECT 1"))
        domain_events.queue_domain_change(
            session,
            hotel_id=42,
            domain="rooms",
            event_type="rooms.first",
            payload={"room_id": 1},
        )
        domain_events.queue_domain_change(
            session,
            hotel_id=42,
            domain="reservations",
            event_type="reservations.second",
            payload={"reservation_id": 2},
        )
        domain_events.queue_domain_change(
            session,
            hotel_id=42,
            domain="settings",
            event_type="settings.ephemeral",
            payload={"family": "hotel"},
            durable=False,
        )
        session.commit()
    finally:
        session.close()

    assert [event["event_type"] for event in attempted] == [
        "rooms.first",
        "reservations.second",
        "settings.ephemeral",
    ]
    with Session(engine) as verification_session:
        rows = verification_session.query(DomainEventOutbox).order_by(DomainEventOutbox.event_type).all()
        state_by_type = {
            row.event_type: (row.status, row.attempts, row.revision)
            for row in rows
        }

    assert state_by_type == {
        "reservations.second": ("published", 1, 2),
        "rooms.first": ("published", 1, 1),
    }
    engine.dispose()


def test_outbox_rows_are_read_after_redis_with_their_hotel_context(monkeypatch: pytest.MonkeyPatch):
    engine = _event_engine()
    session = Session(engine)
    order: list[tuple] = []
    original_get = Session.get
    original_set_context = domain_events.set_tenant_hotel_context

    def publish(**kwargs):
        # No durable row lookup may check out a connection between publishes.
        assert not any(entry[0] == "fetch" for entry in order)
        order.append(("publish", kwargs["hotel_id"]))
        return SimpleNamespace(revision=len(order))

    def set_context(db, hotel_id):
        order.append(("context", hotel_id))
        original_set_context(db, hotel_id)

    def track_outbox_get(db, model, ident, *args, **kwargs):
        if model is DomainEventOutbox and db is not session:
            hotel_id = db.info.get("_tenant_settings", {}).get("app.hotel_id")
            order.append(("fetch", hotel_id, ident))
        return original_get(db, model, ident, *args, **kwargs)

    monkeypatch.setattr(domain_events, "publish_domain_event", publish)
    monkeypatch.setattr(domain_events, "set_tenant_hotel_context", set_context)
    monkeypatch.setattr(Session, "get", track_outbox_get)

    try:
        session.execute(text("SELECT 1"))
        domain_events.queue_domain_change(
            session,
            hotel_id=42,
            domain="rooms",
            event_type="rooms.first",
            payload={"room_id": 1},
        )
        domain_events.queue_domain_change(
            session,
            hotel_id=42,
            domain="reservations",
            event_type="reservations.second",
            payload={"reservation_id": 2},
        )
        domain_events.queue_domain_change(
            session,
            hotel_id=99,
            domain="settings",
            event_type="settings.third",
            payload={"family": "hotel"},
        )
        session.commit()
    finally:
        session.close()
        engine.dispose()

    assert [entry[:2] for entry in order[:3]] == [
        ("publish", 42),
        ("publish", 42),
        ("publish", 99),
    ]
    row_accesses = order[3:]
    assert [entry[:2] for entry in row_accesses] == [
        ("context", 42),
        ("fetch", "42"),
        ("fetch", "42"),
        ("context", 99),
        ("fetch", "99"),
    ]


def test_outbox_metadata_cleanup_failure_does_not_escape_committed_transaction(
    monkeypatch: pytest.MonkeyPatch,
):
    engine = _event_engine()
    session = Session(engine)
    real_rollback = Session.rollback
    real_close = Session.close

    def fail_record(*_args, **_kwargs):
        raise RuntimeError("metadata write failed")

    def rollback_then_raise(outbox_session):
        real_rollback(outbox_session)
        if outbox_session is not session:
            raise RuntimeError("rollback cleanup failed")

    def close_then_raise(outbox_session):
        real_close(outbox_session)
        if outbox_session is not session:
            raise RuntimeError("close cleanup failed")

    monkeypatch.setattr(domain_events, "publish_domain_event", _successful_publisher([]))
    monkeypatch.setattr(domain_events, "_record_outbox_attempt", fail_record)
    monkeypatch.setattr(Session, "rollback", rollback_then_raise)
    monkeypatch.setattr(Session, "close", close_then_raise)

    try:
        session.execute(text("SELECT 1"))
        domain_events.queue_domain_change(
            session,
            hotel_id=42,
            domain="rooms",
            event_type="rooms.changed",
            payload={"room_id": 1},
        )
        session.commit()
    finally:
        real_close(session)
        engine.dispose()


def test_queued_domain_change_is_discarded_on_rollback(monkeypatch: pytest.MonkeyPatch):
    published: list[dict] = []
    monkeypatch.setattr(domain_events, "publish_domain_event", _successful_publisher(published))
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
    monkeypatch.setattr(domain_events, "publish_domain_event", _successful_publisher(published))
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
    monkeypatch.setattr(domain_events, "publish_domain_event", _successful_publisher(published))
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
    monkeypatch.setattr(domain_events, "publish_domain_event", _successful_publisher(published))
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
    monkeypatch.setattr(domain_events, "publish_domain_event", _successful_publisher(published))
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
    monkeypatch.setattr(domain_events, "publish_domain_event", _successful_publisher(published))
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
    request = SimpleNamespace(is_disconnected=lambda: _not_disconnected())
    response = events.stream_domain_events(
        request,
        AuthContext(hotel_id=42, user_id=9, user_role="owner", is_verified=True),
        db,
    )
    assert response.media_type == "text/event-stream"
    assert response.headers["cache-control"] == "no-cache, no-store"
    assert db.closed is True
    async def read_first_frame():
        return await response.body_iterator.__anext__()

    async def _not_disconnected():
        return False

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


def test_redis_stream_uses_one_second_internal_ticks_and_sends_only_real_heartbeats(monkeypatch):
    class FakeClock:
        now = 0.0

        def monotonic(self):
            return self.now

    clock = FakeClock()

    class FakePubSub:
        timeouts = []

        def subscribe(self, _channel):
            pass

        def get_message(self, timeout):
            self.timeouts.append(timeout)
            clock.now += timeout
            return None

        def close(self):
            pass

    fake = FakeRedis()
    pubsub = FakePubSub()
    fake.pubsub = lambda **kwargs: pubsub
    monkeypatch.setattr(domain_events.time, "monotonic", clock.monotonic)

    stream = domain_events.iter_event_stream(42, fake, heartbeat_seconds=5)
    assert "event: ready" in next(stream)
    assert next(stream) == ""
    assert [next(stream) for _ in range(3)] == ["", "", ""]
    assert next(stream) == ": heartbeat\n\n"
    assert pubsub.timeouts == [1.0] * 5
    stream.close()


def test_stream_endpoint_uses_postgres_transport_when_redis_is_unavailable(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(events, "get_realtime_client", lambda: None)
    monkeypatch.setattr(
        events,
        "get_settings",
        lambda: _settings(REALTIME_EVENTS_FALLBACK_POLL_SECONDS=1),
    )
    async def fake_async_stream(*args, **kwargs):
        yield 'event: ready\ndata: {"transport": "postgres-outbox"}\n\n'

    monkeypatch.setattr(events, "aiter_postgres_event_stream", fake_async_stream)

    async def always_connected():
        return False

    class ClosableDb:
        closed = False

        def close(self):
            self.closed = True

    db = ClosableDb()
    response = events.stream_domain_events(
        SimpleNamespace(is_disconnected=always_connected),
        AuthContext(hotel_id=42, user_id=9, user_role="owner", is_verified=True),
        db,
    )
    assert response.headers["x-realtime-transport"] == "postgres-outbox"
    assert db.closed is True

    async def read_one_chunk():
        iterator = response.body_iterator
        chunk = await iterator.__anext__()
        await iterator.aclose()
        return chunk

    assert asyncio.run(read_one_chunk()).startswith("event: ready")


def test_stream_adapter_closes_sync_iterator_when_client_disconnects():
    closed = False

    def sync_stream():
        nonlocal closed
        try:
            yield "event: ready\ndata: {}\n\n"
            while True:
                yield ""
        finally:
            closed = True

    class DisconnectAfterTwoReads:
        reads = 0

        async def is_disconnected(self):
            self.reads += 1
            return self.reads > 2

    async def collect():
        return [chunk async for chunk in events._until_disconnect(DisconnectAfterTwoReads(), sync_stream())]

    chunks = asyncio.run(collect())
    assert chunks == ["event: ready\ndata: {}\n\n"]
    assert closed is True


def test_stream_adapter_closes_async_iterator_when_client_disconnects():
    closed = False

    async def async_stream():
        nonlocal closed
        try:
            yield "event: ready\ndata: {}\n\n"
            yield "event: later\ndata: {}\n\n"
        finally:
            closed = True

    class DisconnectAfterOneRead:
        reads = 0

        async def is_disconnected(self):
            self.reads += 1
            return self.reads > 1

    async def collect():
        return [chunk async for chunk in events._until_disconnect(DisconnectAfterOneRead(), async_stream())]

    chunks = asyncio.run(collect())
    assert chunks == ["event: ready\ndata: {}\n\n"]
    assert closed is True


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


def test_async_postgres_fallback_preserves_cursor_payload_and_tenant_isolation():
    engine = _thread_safe_event_engine()
    factory = sessionmaker(bind=engine)
    session = factory()
    session.add_all(
        [
            DomainEventOutbox(
                event_id="00000000-0000-0000-0000-000000000044",
                hotel_id=42,
                domain="reservations",
                event_type="reservation.updated",
                payload={"reservation_id": 44, "guest_name": "must not stream"},
                schema_version=1,
                stream_cursor=17,
                revision=4,
                occurred_at=datetime.now(timezone.utc),
                status="pending",
            ),
            DomainEventOutbox(
                event_id="00000000-0000-0000-0000-000000000045",
                hotel_id=43,
                domain="reservations",
                event_type="reservation.updated",
                payload={"reservation_id": 45},
                schema_version=1,
                stream_cursor=99,
                revision=5,
                occurred_at=datetime.now(timezone.utc),
                status="pending",
            ),
        ]
    )
    session.commit()
    session.close()

    async def read_frames():
        latest_stream = domain_events.aiter_postgres_event_stream(
            42,
            poll_seconds=1,
            session_factory=factory,
        )
        latest_ready = await latest_stream.__anext__()
        await latest_stream.aclose()

        replay_stream = domain_events.aiter_postgres_event_stream(
            42,
            after_cursor=0,
            poll_seconds=1,
            session_factory=factory,
        )
        replay_ready = await replay_stream.__anext__()
        event_frame = await replay_stream.__anext__()
        await replay_stream.aclose()
        return latest_ready, replay_ready, event_frame

    try:
        latest_ready, replay_ready, event_frame = asyncio.run(read_frames())
    finally:
        engine.dispose()

    assert '"cursor": 17' in latest_ready
    assert '"cursor": 0' in replay_ready
    assert "id: 17\n" in event_frame
    assert '"cursor": 17' in event_frame
    assert '"hotel_id": 42' in event_frame
    assert '"event_type": "reservation.updated"' in event_frame
    assert '"payload": {}' in event_frame
    assert "must not stream" not in event_frame
    assert '"hotel_id": 43' not in event_frame
    assert "00000000-0000-0000-0000-000000000045" not in event_frame


@pytest.mark.asyncio
async def test_async_postgres_fallback_idle_wait_keeps_loop_responsive_and_cancels():
    engine = _thread_safe_event_engine()
    closed_sessions = 0

    class TrackingSession(Session):
        def close(self):
            nonlocal closed_sessions
            closed_sessions += 1
            super().close()

    factory = sessionmaker(bind=engine, class_=TrackingSession)
    stream = domain_events.aiter_postgres_event_stream(
        42,
        after_cursor=0,
        poll_seconds=5,
        session_factory=factory,
    )
    try:
        assert "event: ready" in await stream.__anext__()
        assert await stream.__anext__() == ": heartbeat\n\n"

        waiting_poll = asyncio.create_task(stream.__anext__())
        await asyncio.sleep(0)
        loop = asyncio.get_running_loop()
        tick_started = loop.time()
        await asyncio.sleep(0.02)
        assert loop.time() - tick_started < 0.5
        assert not waiting_poll.done()

        waiting_poll.cancel()
        with pytest.raises(asyncio.CancelledError):
            await waiting_poll
        await stream.aclose()
        assert closed_sessions == 1
    finally:
        engine.dispose()


@pytest.mark.asyncio
async def test_async_postgres_fallback_revalidates_membership_and_emits_control():
    engine = _thread_safe_event_engine()
    factory = sessionmaker(bind=engine)
    checks: list[int] = []

    def revoked_membership() -> bool:
        checks.append(1)
        return False

    stream = domain_events.aiter_postgres_event_stream(
        42,
        after_cursor=0,
        poll_seconds=1,
        authorization_check=revoked_membership,
        authorization_revalidate_seconds=1,
        session_factory=factory,
    )
    try:
        assert "event: ready" in await stream.__anext__()
        assert await stream.__anext__() == ": heartbeat\n\n"
        control = await asyncio.wait_for(stream.__anext__(), timeout=2.0)
    finally:
        await stream.aclose()
        engine.dispose()

    assert "event: control" in control
    assert '"event_type": "authorization_lost"' in control
    assert checks == [1]
