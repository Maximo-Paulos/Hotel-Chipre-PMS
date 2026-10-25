"""PostgreSQL-backed delivery-state regression coverage for Web Push."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.models.hotel_config import HotelConfiguration
from app.models.hotel_membership import HotelMembership
from app.models.notification import (
    NotificationChannelEnum,
    NotificationOutbox,
    NotificationOutboxStatusEnum,
    PushSubscription,
)
from app.models.user import User
from app.services import notification_service as svc
from app.services import push_adapter as pa
from app.services.tenant_context import set_tenant_hotel_context


def _pending_push(db):
    hotel_id = 1_000_000_000 + uuid4().int % 100_000_000
    user_id = 2_000_000_000 + uuid4().int % 100_000_000
    now = datetime(2026, 1, 1, tzinfo=UTC)

    db.add(HotelConfiguration(id=hotel_id, subscription_active=True))
    db.add(User(id=user_id, email=f"push-{user_id}@example.test", password_hash="x", is_verified=True))
    db.flush()
    db.add(HotelMembership(hotel_id=hotel_id, user_id=user_id, role="owner", status="active"))
    db.flush()
    subscription = PushSubscription(
        hotel_id=hotel_id,
        user_id=user_id,
        endpoint=f"https://push.example/{uuid4()}",
        p256dh="synthetic-key",
        auth="synthetic-auth",
    )
    row = NotificationOutbox(
        hotel_id=hotel_id,
        event_type="reservation.created",
        dedupe_key=f"postgres-push-{uuid4()}",
        channel=NotificationChannelEnum.PUSH,
        recipient_user_id=user_id,
        title="Synthetic notification",
    )
    db.add_all([subscription, row])
    db.flush()
    set_tenant_hotel_context(db, hotel_id)
    return now, subscription, row


@pytest.mark.parametrize(
    ("web_push_enabled", "external_connections_enabled"),
    [(False, True), (True, False), (True, True)],
    ids=["feature-disabled", "external-connections-disabled", "implementation-missing"],
)
def test_permanently_unavailable_push_is_terminal_on_postgres(
    pg_session,
    monkeypatch,
    web_push_enabled: bool,
    external_connections_enabled: bool,
):
    now, subscription, row = _pending_push(pg_session)
    monkeypatch.setattr(pa, "get_settings", lambda: SimpleNamespace(WEB_PUSH_ENABLED=web_push_enabled))

    def _gate_external_connections(effect, settings):
        if not external_connections_enabled:
            raise pa.ExternalEffectsDisabled("external connections are disabled")

    monkeypatch.setattr(pa, "require_external_connections", _gate_external_connections)

    counts = svc.process_pending_outbox(pg_session, now=now)
    pg_session.flush()

    assert counts["failed"] == 1
    assert counts["retried"] == 0
    assert row.status == NotificationOutboxStatusEnum.FAILED
    assert row.attempt_count == 0
    assert row.next_retry_at is None
    assert row.last_error == "web_push_unavailable"
    assert subscription.expired_at is None


def test_transient_push_error_keeps_retry_on_postgres(pg_session, monkeypatch):
    now, _subscription, row = _pending_push(pg_session)

    class _TransientAdapter(pa.WebPushAdapter):
        def send(self, subscription, *, title, body, url=None):
            raise pa.WebPushSendError("temporary provider failure")

    monkeypatch.setattr(pa, "get_web_push_adapter", lambda: _TransientAdapter())

    counts = svc.process_pending_outbox(pg_session, now=now)
    pg_session.flush()

    assert counts["retried"] == 1
    assert counts["failed"] == 0
    assert row.status == NotificationOutboxStatusEnum.PENDING
    assert row.attempt_count == 1
    assert row.next_retry_at == now + timedelta(minutes=5)
    assert row.last_error == "temporary provider failure"
