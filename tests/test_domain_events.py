from __future__ import annotations

import asyncio
import json

import pytest

from app.api import events
from app.config import Settings
from app.dependencies.auth import AuthContext
from app.services import domain_events


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

    response = events.stream_domain_events(AuthContext(hotel_id=42, user_id=9, user_role="owner", is_verified=True))
    assert response.media_type == "text/event-stream"
    assert response.headers["cache-control"] == "no-cache, no-store"
    async def read_first_frame():
        return await response.body_iterator.__anext__()

    first_frame = asyncio.run(read_first_frame())
    assert '"hotel_id": 42' in first_frame
