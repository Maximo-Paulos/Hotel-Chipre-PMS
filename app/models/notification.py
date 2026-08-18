"""
Notification backend: in-app inbox, Web Push subscriptions, per-user channel
preferences, a durable outbox (dedupe + bounded retry + expiry), and a
per-hotel daily-report schedule.

Mirrors the SecurityAuditLog / GuestRestriction conventions already in this
codebase: hotel-scoped tables, RLS installed in this migration (see
`_install_rls`/`_remove_rls` in the accompanying migration), and no PII or
secret material stored in `payload` -- only the identifiers already allowed
by `app.services.domain_events.SAFE_PAYLOAD_KEYS`.
"""
from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, CheckConstraint, Column, Date, DateTime, Enum, ForeignKey,
    ForeignKeyConstraint, Index, Integer, String, Text, UniqueConstraint,
)

from app.database import Base


class NotificationSeverityEnum(str, enum.Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class NotificationChannelEnum(str, enum.Enum):
    IN_APP = "in_app"
    PUSH = "push"
    EMAIL = "email"


class NotificationOutboxStatusEnum(str, enum.Enum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    EXPIRED = "expired"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Notification(Base):
    """A single in-app inbox item for one recipient."""

    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False)
    recipient_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    event_type = Column(String(100), nullable=False)
    severity = Column(
        Enum(NotificationSeverityEnum, name="notification_severity_enum", create_constraint=True,
             values_callable=lambda cls: [e.value for e in cls]),
        nullable=False, default=NotificationSeverityEnum.INFO,
    )
    title = Column(String(200), nullable=False)
    body = Column(Text, nullable=True)

    entity_type = Column(String(50), nullable=True)
    entity_id = Column(Integer, nullable=True)
    # JSON object restricted to app.services.domain_events.SAFE_PAYLOAD_KEYS.
    payload = Column(Text, nullable=True)

    is_read = Column(Boolean, nullable=False, default=False, server_default="0")
    read_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, nullable=False, default=_utcnow)
    expires_at = Column(DateTime, nullable=True)

    # Set only when this row was materialized from an outbox row -- lets
    # outbox processing be idempotent (a retried "create the in-app row"
    # step never creates a duplicate Notification for the same outbox id).
    outbox_id = Column(Integer, nullable=True, unique=True)

    __table_args__ = (
        # Composite, not scalar: a Notification must never reference a
        # NotificationOutbox row belonging to a different hotel (same
        # tenant-isolation discipline as GuestRestriction.legacy_guest_tag_id
        # -- see app/models/guest_restriction.py). NULL outbox_id skips the
        # check per standard multi-column FK MATCH SIMPLE semantics.
        ForeignKeyConstraint(
            ["hotel_id", "outbox_id"], ["notification_outbox.hotel_id", "notification_outbox.id"],
            name="fk_notifications_hotel_outbox", ondelete="SET NULL",
        ),
        Index("ix_notifications_hotel_recipient_created", "hotel_id", "recipient_user_id", "created_at"),
        Index("ix_notifications_hotel_recipient_unread", "hotel_id", "recipient_user_id", "is_read"),
    )


class PushSubscription(Base):
    """One Web Push registration (one browser/device) for one user."""

    __tablename__ = "push_subscriptions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    endpoint = Column(Text, nullable=False)
    # Sensitive subscription keys -- never log these in plaintext.
    p256dh = Column(String(255), nullable=False)
    auth = Column(String(255), nullable=False)

    created_at = Column(DateTime, nullable=False, default=_utcnow)
    last_seen_at = Column(DateTime, nullable=True)
    # Set once the push provider reports the endpoint is gone (404/410);
    # expired subscriptions are skipped by delivery and never retried.
    expired_at = Column(DateTime, nullable=True)

    __table_args__ = (
        # A btree unique index over `endpoint` (a URL, bounded by browser
        # implementations to a few hundred bytes) stays well under
        # PostgreSQL's ~8191 byte index-entry limit.
        UniqueConstraint("hotel_id", "user_id", "endpoint", name="uq_push_subscriptions_hotel_user_endpoint"),
        Index("ix_push_subscriptions_hotel_user", "hotel_id", "user_id"),
    )


class NotificationPreference(Base):
    """Per-user, per-event-type channel toggles and quiet hours.

    `event_type == ""` is the hotel-wide default row for that user across
    every event type not otherwise overridden. Empty string (not NULL) is
    used deliberately so the unique constraint below enforces "at most one
    default row per user" on every SQL dialect -- NULL is not equal to NULL
    in a unique index, so a NULL sentinel would silently allow duplicates.
    """

    __tablename__ = "notification_preferences"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    event_type = Column(String(100), nullable=False, default="", server_default="")

    in_app_enabled = Column(Boolean, nullable=False, default=True, server_default="1")
    push_enabled = Column(Boolean, nullable=False, default=True, server_default="1")
    # Email is opt-in: a hotel full of unconfigured preferences must not
    # start emailing every recipient the moment NOTIFICATION_EMAIL_ENABLED
    # flips on.
    email_enabled = Column(Boolean, nullable=False, default=False, server_default="0")

    quiet_hours_start = Column(Integer, nullable=True)  # local hour 0-23, inclusive
    quiet_hours_end = Column(Integer, nullable=True)  # local hour 0-23, exclusive

    created_at = Column(DateTime, nullable=False, default=_utcnow)
    updated_at = Column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)

    __table_args__ = (
        UniqueConstraint("hotel_id", "user_id", "event_type", name="uq_notification_preferences_hotel_user_event"),
        CheckConstraint(
            "quiet_hours_start IS NULL OR (quiet_hours_start >= 0 AND quiet_hours_start <= 23)",
            name="ck_notification_preferences_quiet_start_range",
        ),
        CheckConstraint(
            "quiet_hours_end IS NULL OR (quiet_hours_end >= 0 AND quiet_hours_end <= 23)",
            name="ck_notification_preferences_quiet_end_range",
        ),
    )


class NotificationOutbox(Base):
    """Durable per-recipient, per-channel delivery record.

    One row is the unit of dedupe: (hotel_id, dedupe_key, channel,
    recipient_user_id) is unique, so re-publishing the same domain event
    (e.g. a retried request) never fans out twice to the same recipient on
    the same channel.
    """

    __tablename__ = "notification_outbox"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False)

    event_type = Column(String(100), nullable=False)
    dedupe_key = Column(String(200), nullable=False)
    channel = Column(
        Enum(NotificationChannelEnum, name="notification_channel_enum", create_constraint=True,
             values_callable=lambda cls: [e.value for e in cls]),
        nullable=False,
    )
    recipient_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    severity = Column(
        Enum(NotificationSeverityEnum, name="notification_outbox_severity_enum", create_constraint=True,
             values_callable=lambda cls: [e.value for e in cls]),
        nullable=False, default=NotificationSeverityEnum.INFO,
    )
    title = Column(String(200), nullable=False)
    body = Column(Text, nullable=True)
    entity_type = Column(String(50), nullable=True)
    entity_id = Column(Integer, nullable=True)
    payload = Column(Text, nullable=True)

    status = Column(
        Enum(NotificationOutboxStatusEnum, name="notification_outbox_status_enum", create_constraint=True,
             values_callable=lambda cls: [e.value for e in cls]),
        nullable=False, default=NotificationOutboxStatusEnum.PENDING,
    )
    attempt_count = Column(Integer, nullable=False, default=0, server_default="0")
    next_retry_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    # Short, redacted failure reason only -- never the provider's raw
    # response body or the notification payload.
    last_error = Column(String(300), nullable=True)

    created_at = Column(DateTime, nullable=False, default=_utcnow)
    updated_at = Column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)

    __table_args__ = (
        UniqueConstraint(
            "hotel_id", "dedupe_key", "channel", "recipient_user_id",
            name="uq_notification_outbox_dedupe",
        ),
        # Bind target for Notification's composite (hotel_id, outbox_id) FK
        # above -- SQLite/PostgreSQL both require an explicit unique
        # constraint covering exactly the referenced columns, a scalar
        # PK(id) alone does not satisfy a composite FK target.
        UniqueConstraint("hotel_id", "id", name="uq_notification_outbox_hotel_id_id"),
        Index("ix_notification_outbox_pending", "hotel_id", "status", "next_retry_at"),
    )


class DailyReportSchedule(Base):
    """One row per hotel: when (local hour, hotel timezone), to whom, over
    which channels, and which report sections to send."""

    __tablename__ = "daily_report_schedules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False, unique=True)

    hour = Column(Integer, nullable=False, default=7, server_default="7")  # hotel-local hour, 0-23
    # JSON arrays (enable/disable lists and id lists -- not user-authored
    # logic, so plain JSON columns are proportionate here).
    recipient_user_ids = Column(Text, nullable=True)
    recipient_roles = Column(Text, nullable=True)
    channels = Column(Text, nullable=False, default='["in_app"]', server_default='["in_app"]')
    sections = Column(Text, nullable=False, default="[]", server_default="[]")
    enabled = Column(Boolean, nullable=False, default=True, server_default="1")

    # Guards against sending twice for the same hotel-local calendar date
    # when the scheduler task runs more often than once an hour.
    last_sent_date_local = Column(Date, nullable=True)

    created_at = Column(DateTime, nullable=False, default=_utcnow)
    updated_at = Column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)

    __table_args__ = (
        CheckConstraint("hour >= 0 AND hour <= 23", name="ck_daily_report_schedules_hour_range"),
    )
