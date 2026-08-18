"""Unit coverage for the notification outbox/service: dedupe, permission
filtering, preference filtering, retry/expiry, redaction, tenant isolation,
and daily-report DST/timezone correctness."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import Session

from app.models.hotel_config import HotelConfiguration
from app.models.hotel_membership import HotelMembership
from app.models.notification import (
    DailyReportSchedule,
    Notification,
    NotificationChannelEnum,
    NotificationOutbox,
    NotificationOutboxStatusEnum,
)
from app.models.user import User
from app.services import notification_service as svc


def _hotel(db: Session, hotel_id: int, timezone_name: str = "America/Argentina/Buenos_Aires") -> HotelConfiguration:
    config = HotelConfiguration(id=hotel_id, subscription_active=True, hotel_timezone=timezone_name)
    db.add(config)
    db.flush()
    return config


def _member(db: Session, *, hotel_id: int, user_id: int, role: str, email: str | None = None) -> User:
    user = db.query(User).filter(User.id == user_id).one_or_none()
    if user is None:
        user = User(id=user_id, email=email or f"user{user_id}@example.test", password_hash="x", is_verified=True)
        db.add(user)
    db.add(HotelMembership(hotel_id=hotel_id, user_id=user_id, role=role, status="active"))
    db.flush()
    return user


# ── Dedupe ───────────────────────────────────────────────────────────────


def test_enqueue_dedupes_same_event_recipient_channel(db: Session):
    _hotel(db, 1)
    _member(db, hotel_id=1, user_id=10, role="owner")

    first = svc.enqueue_notifications_for_event(
        db, hotel_id=1, event_type="reservation.created", dedupe_key="reservation:1:created",
        title="New reservation", recipient_user_ids=[10],
    )
    second = svc.enqueue_notifications_for_event(
        db, hotel_id=1, event_type="reservation.created", dedupe_key="reservation:1:created",
        title="New reservation", recipient_user_ids=[10],
    )
    db.flush()

    rows = db.query(NotificationOutbox).filter(NotificationOutbox.hotel_id == 1).all()
    # in_app + push are enabled by preference default; email is opt-in/off.
    by_channel = {row.channel for row in rows}
    assert NotificationChannelEnum.EMAIL not in by_channel
    assert len(rows) == len({(r.channel, r.recipient_user_id) for r in rows})
    assert len(first) == len(second) == len(rows)


def test_enqueue_same_dedupe_key_isolated_per_hotel(db: Session):
    _hotel(db, 1)
    _hotel(db, 2)
    _member(db, hotel_id=1, user_id=10, role="owner")
    _member(db, hotel_id=2, user_id=20, role="owner")

    svc.enqueue_notifications_for_event(
        db, hotel_id=1, event_type="reservation.created", dedupe_key="reservation:1:created",
        title="New reservation", recipient_user_ids=[10],
    )
    svc.enqueue_notifications_for_event(
        db, hotel_id=2, event_type="reservation.created", dedupe_key="reservation:1:created",
        title="New reservation", recipient_user_ids=[20],
    )
    db.flush()

    hotel1_rows = db.query(NotificationOutbox).filter(NotificationOutbox.hotel_id == 1).all()
    hotel2_rows = db.query(NotificationOutbox).filter(NotificationOutbox.hotel_id == 2).all()
    assert hotel1_rows and all(r.recipient_user_id == 10 for r in hotel1_rows)
    assert hotel2_rows and all(r.recipient_user_id == 20 for r in hotel2_rows)


# ── Permission filtering ─────────────────────────────────────────────────


def test_enqueue_skips_recipient_without_entity_read_permission(db: Session):
    _hotel(db, 1)
    _member(db, hotel_id=1, user_id=10, role="receptionist")  # has reservation:read
    _member(db, hotel_id=1, user_id=11, role="housekeeping")  # does not

    svc.enqueue_notifications_for_event(
        db, hotel_id=1, event_type="reservation.created", dedupe_key="reservation:9:created",
        title="New reservation", entity_type="reservation", entity_id=9,
        recipient_user_ids=[10, 11],
    )
    db.flush()

    recipients = {row.recipient_user_id for row in db.query(NotificationOutbox).filter(NotificationOutbox.hotel_id == 1).all()}
    assert 10 in recipients
    assert 11 not in recipients


def test_enqueue_skips_recipient_without_active_membership(db: Session):
    _hotel(db, 1)
    _member(db, hotel_id=1, user_id=10, role="owner")
    # user 99 exists but has no membership in hotel 1 at all.
    db.add(User(id=99, email="stray@example.test", password_hash="x", is_verified=True))
    db.flush()

    svc.enqueue_notifications_for_event(
        db, hotel_id=1, event_type="stock.low", dedupe_key="stock.low:1:2026-01-01",
        title="Low stock", recipient_user_ids=[10, 99],
    )
    db.flush()

    recipients = {row.recipient_user_id for row in db.query(NotificationOutbox).filter(NotificationOutbox.hotel_id == 1).all()}
    assert 10 in recipients
    assert 99 not in recipients


def test_enqueue_role_based_fanout(db: Session):
    _hotel(db, 1)
    _member(db, hotel_id=1, user_id=10, role="owner")
    _member(db, hotel_id=1, user_id=11, role="manager")
    _member(db, hotel_id=1, user_id=12, role="housekeeping")

    svc.enqueue_notifications_for_event(
        db, hotel_id=1, event_type="reservation.created", dedupe_key="reservation:5:created",
        title="New reservation", entity_type="reservation", entity_id=5,
        recipient_roles=["owner", "manager", "housekeeping"],
    )
    db.flush()
    recipients = {row.recipient_user_id for row in db.query(NotificationOutbox).filter(NotificationOutbox.hotel_id == 1).all()}
    assert recipients == {10, 11}  # housekeeping has no reservation:read


# ── Preference filtering ─────────────────────────────────────────────────


def test_enqueue_respects_channel_preference(db: Session):
    _hotel(db, 1)
    _member(db, hotel_id=1, user_id=10, role="owner")
    svc.set_notification_preference(db, hotel_id=1, user_id=10, event_type="", push_enabled=False, email_enabled=True)

    svc.enqueue_notifications_for_event(
        db, hotel_id=1, event_type="reservation.created", dedupe_key="reservation:1:created",
        title="New reservation", recipient_user_ids=[10],
    )
    db.flush()

    channels = {row.channel for row in db.query(NotificationOutbox).filter(NotificationOutbox.hotel_id == 1).all()}
    assert NotificationChannelEnum.PUSH not in channels
    assert NotificationChannelEnum.IN_APP in channels
    assert NotificationChannelEnum.EMAIL in channels


def test_event_specific_preference_overrides_default(db: Session):
    _hotel(db, 1)
    _member(db, hotel_id=1, user_id=10, role="owner")
    svc.set_notification_preference(db, hotel_id=1, user_id=10, event_type="", in_app_enabled=True)
    svc.set_notification_preference(db, hotel_id=1, user_id=10, event_type="stock.low", in_app_enabled=False)

    resolved_default = svc.get_effective_notification_preference(db, hotel_id=1, user_id=10, event_type="reservation.created")
    resolved_specific = svc.get_effective_notification_preference(db, hotel_id=1, user_id=10, event_type="stock.low")
    assert resolved_default["in_app_enabled"] is True
    assert resolved_specific["in_app_enabled"] is False


# ── Retry / expiry / redaction ───────────────────────────────────────────


def test_process_pending_outbox_expires_without_retry(db: Session, monkeypatch):
    _hotel(db, 1)
    _member(db, hotel_id=1, user_id=10, role="owner")
    row = NotificationOutbox(
        hotel_id=1, event_type="reservation.created", dedupe_key="k1",
        channel=NotificationChannelEnum.IN_APP, recipient_user_id=10, title="t",
        expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
    )
    db.add(row)
    db.flush()

    counts = svc.process_pending_outbox(db)
    db.flush()

    assert counts["expired"] == 1
    assert row.status == NotificationOutboxStatusEnum.EXPIRED
    assert row.attempt_count == 0
    assert db.query(Notification).filter(Notification.outbox_id == row.id).one_or_none() is None


def test_process_pending_outbox_retries_then_permanently_fails(db: Session, monkeypatch):
    _hotel(db, 1)
    _member(db, hotel_id=1, user_id=10, role="owner")
    row = NotificationOutbox(
        hotel_id=1, event_type="reservation.created", dedupe_key="k2",
        channel=NotificationChannelEnum.EMAIL, recipient_user_id=10, title="t",
    )
    db.add(row)
    db.flush()

    def _boom(*args, **kwargs):
        raise RuntimeError("SMTP relay exploded with a very long provider-internal stack trace that must never be persisted verbatim into last_error because it could leak internal infrastructure details")

    monkeypatch.setattr(svc, "_deliver_email", lambda db, row: _boom())

    now = datetime.now(timezone.utc)
    for attempt in range(1, svc.MAX_OUTBOX_ATTEMPTS + 1):
        svc.process_pending_outbox(db, now=now)
        db.flush()
        if attempt < svc.MAX_OUTBOX_ATTEMPTS:
            assert row.status == NotificationOutboxStatusEnum.PENDING
            assert row.attempt_count == attempt
            assert row.next_retry_at is not None
            now = row.next_retry_at + timedelta(seconds=1)

    assert row.status == NotificationOutboxStatusEnum.FAILED
    assert row.attempt_count == svc.MAX_OUTBOX_ATTEMPTS
    assert row.next_retry_at is None
    # Redacted: short, no multi-line stack trace persisted.
    assert row.last_error is not None
    assert len(row.last_error) <= 300
    assert "\n" not in row.last_error


def test_process_pending_outbox_in_app_delivery_is_idempotent(db: Session):
    _hotel(db, 1)
    _member(db, hotel_id=1, user_id=10, role="owner")
    row = NotificationOutbox(
        hotel_id=1, event_type="reservation.created", dedupe_key="k3",
        channel=NotificationChannelEnum.IN_APP, recipient_user_id=10, title="Hello",
    )
    db.add(row)
    db.flush()

    svc.process_pending_outbox(db)
    db.flush()
    assert row.status == NotificationOutboxStatusEnum.SENT
    first_count = db.query(Notification).filter(Notification.outbox_id == row.id).count()
    assert first_count == 1

    # Re-running processing (e.g. a stuck worker retried a already-sent
    # batch) must not create a second Notification for the same outbox row.
    row.status = NotificationOutboxStatusEnum.PENDING
    db.flush()
    svc.process_pending_outbox(db)
    db.flush()
    assert db.query(Notification).filter(Notification.outbox_id == row.id).count() == 1


def test_push_channel_without_subscription_fails_immediately(db: Session):
    _hotel(db, 1)
    _member(db, hotel_id=1, user_id=10, role="owner")
    row = NotificationOutbox(
        hotel_id=1, event_type="reservation.created", dedupe_key="k5",
        channel=NotificationChannelEnum.PUSH, recipient_user_id=10, title="t",
    )
    db.add(row)
    db.flush()

    counts = svc.process_pending_outbox(db)
    db.flush()

    assert counts["failed"] == 1
    assert row.status == NotificationOutboxStatusEnum.FAILED
    assert row.attempt_count == 0
    assert row.last_error == "no_active_push_subscription"


def test_push_channel_expires_invalid_subscription_and_retries(db: Session):
    from app.models.notification import PushSubscription
    from app.services import push_adapter as pa

    _hotel(db, 1)
    _member(db, hotel_id=1, user_id=10, role="owner")
    subscription = PushSubscription(hotel_id=1, user_id=10, endpoint="https://push.example/x", p256dh="k", auth="a")
    db.add(subscription)
    row = NotificationOutbox(
        hotel_id=1, event_type="reservation.created", dedupe_key="k6",
        channel=NotificationChannelEnum.PUSH, recipient_user_id=10, title="t",
    )
    db.add(row)
    db.flush()

    class _InvalidAdapter(pa.WebPushAdapter):
        def send(self, subscription, *, title, body, url=None):
            raise pa.WebPushSubscriptionInvalid("410 gone")

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(pa, "get_web_push_adapter", lambda: _InvalidAdapter())
        counts = svc.process_pending_outbox(db)
    db.flush()

    assert subscription.expired_at is not None
    # No active subscriptions were actually sent to -> the row still fails,
    # but not the subscriber's fault of a delivery error -- it just retries
    # (a future subscription may be registered before the next attempt).
    assert counts["retried"] == 1
    assert row.status == NotificationOutboxStatusEnum.PENDING


def test_quiet_hours_defer_push_and_email_but_not_in_app(db: Session):
    _hotel(db, 1, timezone_name="America/Argentina/Buenos_Aires")
    _member(db, hotel_id=1, user_id=10, role="owner")
    # Quiet 22:00-08:00 local (UTC-3): 02:00 UTC is 23:00 local -- inside quiet hours.
    svc.set_notification_preference(db, hotel_id=1, user_id=10, event_type="", quiet_hours_start=22, quiet_hours_end=8)

    in_app = NotificationOutbox(
        hotel_id=1, event_type="reservation.created", dedupe_key="q1",
        channel=NotificationChannelEnum.IN_APP, recipient_user_id=10, title="t",
    )
    push = NotificationOutbox(
        hotel_id=1, event_type="reservation.created", dedupe_key="q2",
        channel=NotificationChannelEnum.PUSH, recipient_user_id=10, title="t",
    )
    db.add_all([in_app, push])
    db.flush()

    now = datetime(2026, 1, 1, 2, 0, tzinfo=timezone.utc)
    counts = svc.process_pending_outbox(db, now=now)
    db.flush()

    assert counts["deferred"] == 1
    assert push.status == NotificationOutboxStatusEnum.PENDING
    assert push.next_retry_at is not None
    assert push.attempt_count == 0
    assert in_app.status == NotificationOutboxStatusEnum.SENT


def test_email_channel_disabled_fails_immediately_without_retry(db: Session):
    _hotel(db, 1)
    _member(db, hotel_id=1, user_id=10, role="owner")
    row = NotificationOutbox(
        hotel_id=1, event_type="reservation.created", dedupe_key="k4",
        channel=NotificationChannelEnum.EMAIL, recipient_user_id=10, title="t",
    )
    db.add(row)
    db.flush()

    counts = svc.process_pending_outbox(db)
    db.flush()

    assert counts["failed"] == 1
    assert row.status == NotificationOutboxStatusEnum.FAILED
    assert row.attempt_count == 0  # config-gap, not a transient failure -- no retry burned
    assert row.last_error == "notification_email_disabled"


# ── Inbox ────────────────────────────────────────────────────────────────


def test_mark_read_and_unread_count(db: Session):
    _hotel(db, 1)
    _member(db, hotel_id=1, user_id=10, role="owner")
    n1 = Notification(hotel_id=1, recipient_user_id=10, event_type="x", title="a")
    n2 = Notification(hotel_id=1, recipient_user_id=10, event_type="x", title="b")
    db.add_all([n1, n2])
    db.flush()

    assert svc.unread_notification_count(db, hotel_id=1, user_id=10) == 2
    svc.mark_notification_read(db, hotel_id=1, user_id=10, notification_id=n1.id)
    assert svc.unread_notification_count(db, hotel_id=1, user_id=10) == 1

    with pytest.raises(svc.NotificationServiceError):
        svc.mark_notification_read(db, hotel_id=999, user_id=10, notification_id=n1.id)


# ── Daily report scheduling: DST / timezone correctness ──────────────────


def test_daily_report_uses_hotel_local_hour_not_utc(db: Session):
    """Buenos Aires currently observes UTC-3 year-round (Argentina abolished
    DST in 2009) -- verify the schedule fires on the LOCAL hour, which is
    NOT the same as the UTC hour, proving conversion isn't a no-op."""
    _hotel(db, 1, timezone_name="America/Argentina/Buenos_Aires")
    _member(db, hotel_id=1, user_id=10, role="owner")
    svc.upsert_daily_report_schedule(db, hotel_id=1, hour=7, recipient_user_ids=[10], channels=["in_app"])
    db.flush()

    # 07:00 local (UTC-3) == 10:00 UTC.
    results = svc.generate_due_daily_reports(db, now_utc=datetime(2026, 3, 10, 10, 0, tzinfo=timezone.utc))
    assert len(results) == 1
    assert results[0]["hotel_id"] == 1

    # 07:00 UTC is 04:00 local -- must NOT fire.
    schedule = svc.get_daily_report_schedule(db, hotel_id=1)
    schedule.last_sent_date_local = None
    db.flush()
    results = svc.generate_due_daily_reports(db, now_utc=datetime(2026, 3, 11, 7, 0, tzinfo=timezone.utc))
    assert results == []


def test_daily_report_dst_transition_shifts_the_utc_trigger_hour(db: Session):
    """A DST-observing timezone (America/New_York) must fire at a different
    UTC instant in winter (EST, UTC-5) vs summer (EDT, UTC-4) for the SAME
    configured local hour -- this is the real DST edge case ZoneInfo exists
    to handle (Argentina itself no longer observes DST, so this scenario
    isn't reachable with America/Argentina/Buenos_Aires)."""
    _hotel(db, 1, timezone_name="America/New_York")
    _member(db, hotel_id=1, user_id=10, role="owner")
    svc.upsert_daily_report_schedule(db, hotel_id=1, hour=7, recipient_user_ids=[10], channels=["in_app"])
    db.flush()

    # Winter (EST, UTC-5): 07:00 local == 12:00 UTC.
    winter_results = svc.generate_due_daily_reports(db, now_utc=datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc))
    assert len(winter_results) == 1

    schedule = svc.get_daily_report_schedule(db, hotel_id=1)
    schedule.last_sent_date_local = None
    db.flush()

    # Same 12:00 UTC in summer (EDT, UTC-4) is 08:00 local -- must NOT fire.
    summer_no_fire = svc.generate_due_daily_reports(db, now_utc=datetime(2026, 7, 15, 12, 0, tzinfo=timezone.utc))
    assert summer_no_fire == []

    # 11:00 UTC in summer (EDT, UTC-4) IS 07:00 local -- must fire.
    summer_fire = svc.generate_due_daily_reports(db, now_utc=datetime(2026, 7, 15, 11, 0, tzinfo=timezone.utc))
    assert len(summer_fire) == 1


def test_daily_report_does_not_resend_same_local_date(db: Session):
    _hotel(db, 1, timezone_name="America/Argentina/Buenos_Aires")
    _member(db, hotel_id=1, user_id=10, role="owner")
    svc.upsert_daily_report_schedule(db, hotel_id=1, hour=7, recipient_user_ids=[10], channels=["in_app"])
    db.flush()

    now = datetime(2026, 3, 10, 10, 0, tzinfo=timezone.utc)  # 07:00 local
    first = svc.generate_due_daily_reports(db, now_utc=now)
    second = svc.generate_due_daily_reports(db, now_utc=now + timedelta(minutes=10))  # still 07:xx local
    assert len(first) == 1
    assert second == []
