"""
Notification backend: outbox enqueue/dedupe, preference + permission
filtering, bounded-retry processing, in-app inbox, push subscriptions, and
daily-report scheduling.

Integration point for domain events: services that already call
`app.services.domain_events.publish_domain_event` (the realtime/ephemeral
Redis signal) call `enqueue_notifications_for_event` alongside it to create
the durable, per-recipient outbox rows this module then delivers. The two
are deliberately separate -- Redis pub/sub has no durability or replay, so
"what should notify whom" is decided synchronously at the call site, not by
consuming the Redis stream later.

Non-disclosure discipline matches GuestRestriction: `payload` is restricted
to `app.services.domain_events.SAFE_PAYLOAD_KEYS` (identifiers only, never
guest contact data, credentials, or free-text reasons/details).
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime, time, timedelta, timezone
from typing import Iterable
from zoneinfo import ZoneInfo

from sqlalchemy import or_
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.models.hotel_config import HotelConfiguration
from app.models.hotel_membership import HotelMembership
from app.models.notification import (
    DailyReportSchedule,
    Notification,
    NotificationChannelEnum,
    NotificationOutbox,
    NotificationOutboxStatusEnum,
    NotificationPreference,
    NotificationSeverityEnum,
    PushSubscription,
)
from app.models.user import User
from app.services.domain_events import SAFE_PAYLOAD_KEYS, queue_domain_change
from app.services.permission_service import (
    PERMISSION_GUEST_PROHIBITION_READ,
    PERMISSION_RESERVATION_READ,
    PERMISSION_STOCK_READ,
    resolve as resolve_permission,
)

logger = logging.getLogger(__name__)

MAX_OUTBOX_ATTEMPTS = 3
_BACKOFF_MINUTES = (5, 30, 120)  # index by (attempt_count - 1), clamped

ALL_CHANNELS = (NotificationChannelEnum.IN_APP, NotificationChannelEnum.PUSH, NotificationChannelEnum.EMAIL)

# entity_type -> permission code a recipient must hold to be notified about
# it at all. An event with no entity_type skips this filter (e.g. a
# hotel-wide alert with no single underlying record).
ENTITY_READ_PERMISSIONS: dict[str, str] = {
    "reservation": PERMISSION_RESERVATION_READ,
    "guest_restriction": PERMISSION_GUEST_PROHIBITION_READ,
    "stock_item": PERMISSION_STOCK_READ,
}


class NotificationServiceError(ValueError):
    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _validate_payload(payload: dict | None) -> dict:
    normalized = dict(payload or {})
    unknown = set(normalized) - SAFE_PAYLOAD_KEYS
    if unknown:
        raise NotificationServiceError("Unsupported payload key: " + ", ".join(sorted(unknown)))
    for key, value in normalized.items():
        if isinstance(value, (dict, list, tuple, set)):
            raise NotificationServiceError(f"Payload value for {key} must be scalar")
        if value is not None and not isinstance(value, (str, int, float, bool)):
            raise NotificationServiceError(f"Payload value for {key} must be a JSON scalar")
    return normalized


def _insert_ignore(db: Session, table, values: list[dict], conflict_columns: list[str]) -> None:
    if not values:
        return
    dialect = db.get_bind().dialect.name
    if dialect == "sqlite":
        statement = sqlite_insert(table).values(values).on_conflict_do_nothing(index_elements=conflict_columns)
    elif dialect == "postgresql":
        statement = postgresql_insert(table).values(values).on_conflict_do_nothing(index_elements=conflict_columns)
    else:
        raise RuntimeError(f"Unsupported database dialect for notification outbox insert: {dialect}")
    db.execute(statement)


def _redact(message: str, limit: int = 300) -> str:
    """Short, provider-agnostic failure reason -- never the raw provider
    response body or the notification payload."""
    text = str(message or "").strip().splitlines()[0] if message else ""
    return text[:limit]


# ── Recipient resolution ──────────────────────────────────────────────────


def _role_recipient_ids(db: Session, hotel_id: int, roles: Iterable[str]) -> set[int]:
    roles = list(roles)
    if not roles:
        return set()
    rows = (
        db.query(HotelMembership.user_id)
        .filter(
            HotelMembership.hotel_id == hotel_id,
            HotelMembership.status == "active",
            HotelMembership.role.in_(roles),
        )
        .all()
    )
    return {row[0] for row in rows}


def _actor_role(db: Session, hotel_id: int, user_id: int) -> str | None:
    membership = (
        db.query(HotelMembership)
        .filter(HotelMembership.hotel_id == hotel_id, HotelMembership.user_id == user_id, HotelMembership.status == "active")
        .one_or_none()
    )
    return membership.role if membership else None


# ── Preferences ────────────────────────────────────────────────────────────


_PREFERENCE_DEFAULTS = {"in_app_enabled": True, "push_enabled": True, "email_enabled": False,
                         "quiet_hours_start": None, "quiet_hours_end": None}


def get_effective_notification_preference(db: Session, *, hotel_id: int, user_id: int, event_type: str) -> dict:
    """Resolve a user's channel toggles/quiet-hours for one event_type:
    an exact-event_type row wins, else the user's default ("") row, else the
    hardcoded defaults above."""
    rows = {
        row.event_type: row
        for row in db.query(NotificationPreference)
        .filter(
            NotificationPreference.hotel_id == hotel_id,
            NotificationPreference.user_id == user_id,
            NotificationPreference.event_type.in_([event_type, ""]),
        )
        .all()
    }
    row = rows.get(event_type) or rows.get("")
    if row is None:
        return dict(_PREFERENCE_DEFAULTS)
    return {
        "in_app_enabled": bool(row.in_app_enabled),
        "push_enabled": bool(row.push_enabled),
        "email_enabled": bool(row.email_enabled),
        "quiet_hours_start": row.quiet_hours_start,
        "quiet_hours_end": row.quiet_hours_end,
    }


def list_notification_preferences(db: Session, *, hotel_id: int, user_id: int) -> list[NotificationPreference]:
    return (
        db.query(NotificationPreference)
        .filter(NotificationPreference.hotel_id == hotel_id, NotificationPreference.user_id == user_id)
        .order_by(NotificationPreference.event_type.asc())
        .all()
    )


def set_notification_preference(
    db: Session,
    *,
    hotel_id: int,
    user_id: int,
    event_type: str = "",
    in_app_enabled: bool | None = None,
    push_enabled: bool | None = None,
    email_enabled: bool | None = None,
    quiet_hours_start: int | None = None,
    quiet_hours_end: int | None = None,
    clear_quiet_hours: bool = False,
) -> NotificationPreference:
    row = (
        db.query(NotificationPreference)
        .filter(
            NotificationPreference.hotel_id == hotel_id,
            NotificationPreference.user_id == user_id,
            NotificationPreference.event_type == event_type,
        )
        .one_or_none()
    )
    if row is None:
        row = NotificationPreference(hotel_id=hotel_id, user_id=user_id, event_type=event_type)
        db.add(row)
    if in_app_enabled is not None:
        row.in_app_enabled = in_app_enabled
    if push_enabled is not None:
        row.push_enabled = push_enabled
    if email_enabled is not None:
        row.email_enabled = email_enabled
    if clear_quiet_hours:
        row.quiet_hours_start = None
        row.quiet_hours_end = None
    else:
        if quiet_hours_start is not None:
            row.quiet_hours_start = quiet_hours_start
        if quiet_hours_end is not None:
            row.quiet_hours_end = quiet_hours_end
    db.flush()
    return row


def _in_quiet_hours(*, hotel_timezone: str, quiet_start: int | None, quiet_end: int | None, now_utc: datetime | None = None) -> bool:
    if quiet_start is None or quiet_end is None:
        return False
    local_hour = (now_utc or _utcnow()).astimezone(ZoneInfo(hotel_timezone)).hour
    if quiet_start == quiet_end:
        return False
    if quiet_start < quiet_end:
        return quiet_start <= local_hour < quiet_end
    return local_hour >= quiet_start or local_hour < quiet_end  # wraps past midnight


# ── Push subscriptions ──────────────────────────────────────────────────────


def register_push_subscription(
    db: Session, *, hotel_id: int, user_id: int, endpoint: str, p256dh: str, auth: str,
) -> PushSubscription:
    if not endpoint or not p256dh or not auth:
        raise NotificationServiceError("endpoint, p256dh and auth are required")
    row = (
        db.query(PushSubscription)
        .filter(PushSubscription.hotel_id == hotel_id, PushSubscription.user_id == user_id, PushSubscription.endpoint == endpoint)
        .one_or_none()
    )
    if row is None:
        row = PushSubscription(hotel_id=hotel_id, user_id=user_id, endpoint=endpoint, p256dh=p256dh, auth=auth)
        db.add(row)
    else:
        row.p256dh = p256dh
        row.auth = auth
        row.expired_at = None
    row.last_seen_at = _utcnow()
    db.flush()
    return row


def unregister_push_subscription(db: Session, *, hotel_id: int, user_id: int, endpoint: str) -> bool:
    row = (
        db.query(PushSubscription)
        .filter(PushSubscription.hotel_id == hotel_id, PushSubscription.user_id == user_id, PushSubscription.endpoint == endpoint)
        .one_or_none()
    )
    if row is None:
        return False
    db.delete(row)
    db.flush()
    return True


def _active_push_subscriptions(db: Session, *, hotel_id: int, user_id: int) -> list[PushSubscription]:
    return (
        db.query(PushSubscription)
        .filter(
            PushSubscription.hotel_id == hotel_id,
            PushSubscription.user_id == user_id,
            PushSubscription.expired_at.is_(None),
        )
        .all()
    )


# ── Outbox enqueue ───────────────────────────────────────────────────────────


def enqueue_notifications_for_event(
    db: Session,
    *,
    hotel_id: int,
    event_type: str,
    dedupe_key: str,
    title: str,
    body: str | None = None,
    severity: NotificationSeverityEnum = NotificationSeverityEnum.INFO,
    entity_type: str | None = None,
    entity_id: int | None = None,
    payload: dict | None = None,
    recipient_user_ids: Iterable[int] | None = None,
    recipient_roles: Iterable[str] | None = None,
    expires_at: datetime | None = None,
    channels: Iterable[NotificationChannelEnum] | None = None,
) -> list[NotificationOutbox]:
    """Fan out one logical event to every eligible (recipient, channel) pair
    and insert-or-ignore the resulting NotificationOutbox rows.

    A recipient is skipped entirely (all channels) when `entity_type` maps to
    a read permission they don't hold -- notifications must never disclose
    the existence of a record the recipient cannot otherwise read. Per
    channel, a recipient is skipped when their NotificationPreference has
    that channel disabled for this event_type.
    """
    if not str(event_type or "").strip():
        raise NotificationServiceError("event_type is required")
    if not str(dedupe_key or "").strip():
        raise NotificationServiceError("dedupe_key is required")
    if not str(title or "").strip():
        raise NotificationServiceError("title is required")
    normalized_payload = _validate_payload(payload)

    recipients = {int(uid) for uid in (recipient_user_ids or [])}
    recipients |= _role_recipient_ids(db, hotel_id, recipient_roles or [])
    if not recipients:
        return []

    required_permission = ENTITY_READ_PERMISSIONS.get(entity_type or "")
    if required_permission:
        allowed_recipients = set()
        for user_id in recipients:
            role = _actor_role(db, hotel_id, user_id)
            if role is None:
                continue
            if resolve_permission(db, hotel_id, role, required_permission, user_id=user_id):
                allowed_recipients.add(user_id)
        recipients = allowed_recipients
    else:
        # No entity permission gate: still require an active membership so a
        # revoked/former staff member never receives a notification row.
        recipients = {uid for uid in recipients if _actor_role(db, hotel_id, uid) is not None}

    if not recipients:
        return []

    payload_json = json.dumps(normalized_payload, sort_keys=True, ensure_ascii=True) if normalized_payload else None
    eligible_channels = set(channels) if channels is not None else set(ALL_CHANNELS)

    rows_to_insert: list[dict] = []
    for user_id in sorted(recipients):
        preference = get_effective_notification_preference(db, hotel_id=hotel_id, user_id=user_id, event_type=event_type)
        for channel in eligible_channels:
            channel_enabled = {
                NotificationChannelEnum.IN_APP: preference["in_app_enabled"],
                NotificationChannelEnum.PUSH: preference["push_enabled"],
                NotificationChannelEnum.EMAIL: preference["email_enabled"],
            }[channel]
            if not channel_enabled:
                continue
            rows_to_insert.append(
                {
                    "hotel_id": hotel_id,
                    "event_type": event_type,
                    "dedupe_key": dedupe_key,
                    "channel": channel,
                    "recipient_user_id": user_id,
                    "severity": severity,
                    "title": title,
                    "body": body,
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                    "payload": payload_json,
                    "status": NotificationOutboxStatusEnum.PENDING,
                    "expires_at": expires_at,
                }
            )

    if not rows_to_insert:
        return []

    _insert_ignore(
        db, NotificationOutbox.__table__, rows_to_insert,
        ["hotel_id", "dedupe_key", "channel", "recipient_user_id"],
    )
    db.flush()
    # The outbox insert uses a dialect-specific Core statement, so the ORM
    # change collector cannot see it. Queue only a generic inbox signal; the
    # notification body and recipient data never enter Redis.
    queue_domain_change(
        db,
        hotel_id=hotel_id,
        domain="notifications",
        event_type="notifications.outbox.changed",
        payload={"family": "outbox"},
    )

    return (
        db.query(NotificationOutbox)
        .filter(
            NotificationOutbox.hotel_id == hotel_id,
            NotificationOutbox.dedupe_key == dedupe_key,
            NotificationOutbox.event_type == event_type,
        )
        .all()
    )


# ── Inbox ────────────────────────────────────────────────────────────────────


def list_notifications(
    db: Session, *, hotel_id: int, user_id: int, unread_only: bool = False, limit: int = 50, offset: int = 0,
) -> list[Notification]:
    query = db.query(Notification).filter(Notification.hotel_id == hotel_id, Notification.recipient_user_id == user_id)
    if unread_only:
        query = query.filter(Notification.is_read.is_(False))
    return query.order_by(Notification.created_at.desc(), Notification.id.desc()).offset(max(offset, 0)).limit(max(min(limit, 200), 1)).all()


def unread_notification_count(db: Session, *, hotel_id: int, user_id: int) -> int:
    return (
        db.query(Notification)
        .filter(Notification.hotel_id == hotel_id, Notification.recipient_user_id == user_id, Notification.is_read.is_(False))
        .count()
    )


def mark_notification_read(db: Session, *, hotel_id: int, user_id: int, notification_id: int, read: bool = True) -> Notification:
    notification = (
        db.query(Notification)
        .filter(Notification.id == notification_id, Notification.hotel_id == hotel_id, Notification.recipient_user_id == user_id)
        .one_or_none()
    )
    if notification is None:
        raise NotificationServiceError("Notification not found")
    notification.is_read = read
    notification.read_at = _utcnow() if read else None
    db.flush()
    return notification


def mark_all_notifications_read(db: Session, *, hotel_id: int, user_id: int) -> int:
    rows = (
        db.query(Notification)
        .filter(Notification.hotel_id == hotel_id, Notification.recipient_user_id == user_id, Notification.is_read.is_(False))
        .all()
    )
    now = _utcnow()
    for row in rows:
        row.is_read = True
        row.read_at = now
    db.flush()
    return len(rows)


# ── Outbox processing ────────────────────────────────────────────────────────


def _mark_terminal(row: NotificationOutbox, *, status: NotificationOutboxStatusEnum, reason: str) -> None:
    row.status = status
    row.last_error = _redact(reason)
    row.next_retry_at = None


def _schedule_retry(row: NotificationOutbox, *, reason: str, now: datetime) -> None:
    row.attempt_count += 1
    row.last_error = _redact(reason)
    if row.attempt_count >= MAX_OUTBOX_ATTEMPTS:
        row.status = NotificationOutboxStatusEnum.FAILED
        row.next_retry_at = None
        return
    minutes = _BACKOFF_MINUTES[min(row.attempt_count - 1, len(_BACKOFF_MINUTES) - 1)]
    row.next_retry_at = now + timedelta(minutes=minutes)


def _deliver_in_app(db: Session, row: NotificationOutbox) -> None:
    existing = db.query(Notification).filter(Notification.outbox_id == row.id).one_or_none()
    if existing is None:
        db.add(
            Notification(
                hotel_id=row.hotel_id,
                recipient_user_id=row.recipient_user_id,
                event_type=row.event_type,
                severity=row.severity,
                title=row.title,
                body=row.body,
                entity_type=row.entity_type,
                entity_id=row.entity_id,
                payload=row.payload,
                expires_at=row.expires_at,
                outbox_id=row.id,
            )
        )
    row.status = NotificationOutboxStatusEnum.SENT


def _deliver_push(db: Session, row: NotificationOutbox, *, now: datetime) -> None:
    from app.services.push_adapter import WebPushSendError, WebPushSubscriptionInvalid, get_web_push_adapter

    subscriptions = _active_push_subscriptions(db, hotel_id=row.hotel_id, user_id=row.recipient_user_id)
    if not subscriptions:
        _mark_terminal(row, status=NotificationOutboxStatusEnum.FAILED, reason="no_active_push_subscription")
        return

    adapter = get_web_push_adapter()
    sent = False
    last_reason = ""
    for subscription in subscriptions:
        try:
            adapter.send(subscription, title=row.title, body=row.body or "")
            sent = True
        except WebPushSubscriptionInvalid:
            subscription.expired_at = now
        except WebPushSendError as exc:
            last_reason = str(exc)

    if sent:
        row.status = NotificationOutboxStatusEnum.SENT
    else:
        _schedule_retry(row, reason=last_reason or "push_delivery_failed", now=now)


def _deliver_email(db: Session, row: NotificationOutbox) -> None:
    from app.config import get_settings
    from app.services.email_service import send_platform_email

    if not bool(getattr(get_settings(), "NOTIFICATION_EMAIL_ENABLED", False)):
        _mark_terminal(row, status=NotificationOutboxStatusEnum.FAILED, reason="notification_email_disabled")
        return

    recipient = db.get(User, row.recipient_user_id)
    if recipient is None or not recipient.email:
        _mark_terminal(row, status=NotificationOutboxStatusEnum.FAILED, reason="recipient_has_no_email")
        return

    send_platform_email(recipient.email, row.title, row.body or row.title)
    row.status = NotificationOutboxStatusEnum.SENT


def process_pending_outbox(db: Session, *, now: datetime | None = None, batch_size: int = 200) -> dict[str, int]:
    """Process pending NotificationOutbox rows: deliver, retry with bounded
    backoff, or expire. Callable from a script/cron entrypoint (this
    codebase's scheduled-work pattern is Celery beat; see
    app/tasks/notification_tasks.py) -- not itself async or long-running."""
    now = now or _utcnow()
    counts = {"processed": 0, "sent": 0, "failed": 0, "expired": 0, "retried": 0, "deferred": 0}

    rows = (
        db.query(NotificationOutbox)
        .filter(
            NotificationOutbox.status == NotificationOutboxStatusEnum.PENDING,
            or_(NotificationOutbox.next_retry_at.is_(None), NotificationOutbox.next_retry_at <= now),
        )
        .order_by(NotificationOutbox.created_at.asc())
        .limit(max(batch_size, 1))
        .all()
    )

    for row in rows:
        counts["processed"] += 1
        if row.expires_at is not None and row.expires_at <= now:
            _mark_terminal(row, status=NotificationOutboxStatusEnum.EXPIRED, reason="expired_before_delivery")
            counts["expired"] += 1
            db.flush()
            continue

        # Quiet hours only defer interruptive channels -- an in-app row is
        # inert until the user opens the inbox, so it delivers immediately.
        if row.channel in (NotificationChannelEnum.PUSH, NotificationChannelEnum.EMAIL):
            hotel = db.get(HotelConfiguration, row.hotel_id)
            preference = get_effective_notification_preference(
                db, hotel_id=row.hotel_id, user_id=row.recipient_user_id, event_type=row.event_type,
            )
            if _in_quiet_hours(
                hotel_timezone=(hotel.hotel_timezone if hotel else None) or "UTC",
                quiet_start=preference["quiet_hours_start"],
                quiet_end=preference["quiet_hours_end"],
                now_utc=now,
            ):
                # ponytail: a fixed 30-minute recheck instead of computing the
                # exact quiet-hours-end instant -- simpler and still correct
                # (never sends early), add precise scheduling if the recheck
                # cadence ever matters operationally.
                row.next_retry_at = now + timedelta(minutes=30)
                counts["deferred"] += 1
                db.flush()
                continue

        try:
            if row.channel == NotificationChannelEnum.IN_APP:
                _deliver_in_app(db, row)
            elif row.channel == NotificationChannelEnum.PUSH:
                _deliver_push(db, row, now=now)
            elif row.channel == NotificationChannelEnum.EMAIL:
                _deliver_email(db, row)
            else:  # pragma: no cover - defensive, enum-constrained column
                _mark_terminal(row, status=NotificationOutboxStatusEnum.FAILED, reason="unknown_channel")
        except Exception as exc:  # a single bad row must never abort the batch
            logger.warning(
                "notification_outbox.delivery_error",
                extra={"hotel_id": row.hotel_id, "outbox_id": row.id, "channel": row.channel.value},
            )
            _schedule_retry(row, reason=str(exc), now=now)

        if row.status == NotificationOutboxStatusEnum.SENT:
            counts["sent"] += 1
        elif row.status == NotificationOutboxStatusEnum.FAILED:
            counts["failed"] += 1
        elif row.status == NotificationOutboxStatusEnum.PENDING:
            counts["retried"] += 1
        db.flush()

    return counts


# ── Daily report schedule CRUD ───────────────────────────────────────────────

DEFAULT_DAILY_REPORT_SECTIONS = [
    "occupancy", "arrivals", "departures", "pending_payments", "late_arrivals",
    "room_blocks", "cash_session", "low_stock", "laundry_outbound", "critical_alerts",
]


def _safe_channel(value: str) -> NotificationChannelEnum | None:
    try:
        return NotificationChannelEnum(value)
    except ValueError:
        return None


def get_daily_report_schedule(db: Session, *, hotel_id: int) -> DailyReportSchedule | None:
    return db.query(DailyReportSchedule).filter(DailyReportSchedule.hotel_id == hotel_id).one_or_none()


def upsert_daily_report_schedule(
    db: Session,
    *,
    hotel_id: int,
    hour: int = 7,
    recipient_user_ids: list[int] | None = None,
    recipient_roles: list[str] | None = None,
    channels: list[str] | None = None,
    sections: list[str] | None = None,
    enabled: bool = True,
) -> DailyReportSchedule:
    if not (0 <= hour <= 23):
        raise NotificationServiceError("hour must be between 0 and 23")
    invalid_channels = set(channels or []) - {c.value for c in ALL_CHANNELS}
    if invalid_channels:
        raise NotificationServiceError("Invalid channel: " + ", ".join(sorted(invalid_channels)))

    row = get_daily_report_schedule(db, hotel_id=hotel_id)
    if row is None:
        row = DailyReportSchedule(hotel_id=hotel_id)
        db.add(row)
    row.hour = hour
    row.recipient_user_ids = json.dumps(sorted(set(recipient_user_ids or [])))
    row.recipient_roles = json.dumps(sorted(set(recipient_roles or [])))
    row.channels = json.dumps(channels or ["in_app"])
    row.sections = json.dumps(sections if sections is not None else DEFAULT_DAILY_REPORT_SECTIONS)
    row.enabled = enabled
    db.flush()
    return row


# ── Daily report generation ──────────────────────────────────────────────────


def _build_daily_report_body(db: Session, *, hotel_id: int, report_date: date, sections: list[str]) -> tuple[str, dict]:
    from app.models.room import Room, RoomStatusEnum
    from app.services.operational_report_service import daily_report
    from app.services.stock_service import low_stock_items

    report = daily_report(db, hotel_id, report_date)
    lines = [f"Daily operational report - {report_date.isoformat()}"]

    if "occupancy" in sections:
        total_rooms = db.query(Room).filter(Room.hotel_id == hotel_id, Room.deleted_at.is_(None)).count()
        occupied_rooms = db.query(Room).filter(
            Room.hotel_id == hotel_id, Room.deleted_at.is_(None), Room.status == RoomStatusEnum.OCCUPIED,
        ).count()
        occupancy_pct = round((occupied_rooms / total_rooms) * 100, 1) if total_rooms else 0.0
        lines.append(f"Occupancy: {occupied_rooms}/{total_rooms} rooms ({occupancy_pct}%)")
    if "arrivals" in sections:
        lines.append(f"Arrivals: {len(report.arrivals.reservations)}")
    if "departures" in sections:
        lines.append(f"Departures: {len(report.departures.reservations)}")
    if "pending_payments" in sections:
        lines.append(f"Pending payments: {len(report.pending_payments.reservations)}")
    if "late_arrivals" in sections:
        lines.append(f"Late arrivals: {len(report.late_arrivals)}")
    if "room_blocks" in sections:
        lines.append(f"Active room blocks: {len(report.active_room_blocks)}")
    if "cash_session" in sections:
        lines.append(f"Cash session: {report.cash_session.status}")
    if "low_stock" in sections:
        low_items = low_stock_items(db, hotel_id=hotel_id)
        lines.append(f"Low stock items: {len(low_items)}")
    if "laundry_outbound" in sections:
        from app.services.laundry_vendor_service import list_remitos

        window_start = datetime.combine(report_date - timedelta(days=14), time.min, tzinfo=timezone.utc)
        outbound = [r for r in list_remitos(db, hotel_id=hotel_id, date_from=window_start) if r.direction == "outbound"]
        lines.append(f"Laundry outbound remitos (last 14 days): {len(outbound)}")
    if "critical_alerts" in sections:
        critical = [a for a in report.alerts if a.severity in ("warning", "critical")]
        lines.append(f"Alerts: {len(critical)}")

    return "\n".join(lines), {}


def generate_due_daily_reports(db: Session, *, now_utc: datetime | None = None) -> list[dict]:
    """For every hotel with an enabled DailyReportSchedule whose configured
    local hour has arrived (hotel-local wall clock, DST-safe via ZoneInfo)
    and whose report has not already been sent for that local date, build
    the report and enqueue it through the outbox to the configured
    recipients/channels."""
    now_utc = now_utc or _utcnow()
    results: list[dict] = []

    schedules = db.query(DailyReportSchedule).filter(DailyReportSchedule.enabled.is_(True)).all()
    for schedule in schedules:
        hotel = db.get(HotelConfiguration, schedule.hotel_id)
        if hotel is None:
            continue
        local_now = now_utc.astimezone(ZoneInfo(hotel.hotel_timezone or "UTC"))
        if local_now.hour != schedule.hour:
            continue
        if schedule.last_sent_date_local == local_now.date():
            continue

        recipient_ids = json.loads(schedule.recipient_user_ids or "[]")
        recipient_roles = json.loads(schedule.recipient_roles or "[]")
        channels = set(json.loads(schedule.channels or '["in_app"]'))
        sections = json.loads(schedule.sections or "[]") or DEFAULT_DAILY_REPORT_SECTIONS

        if not recipient_ids and not recipient_roles:
            continue

        body, _ = _build_daily_report_body(db, hotel_id=schedule.hotel_id, report_date=local_now.date(), sections=sections)

        # Restrict fan-out to exactly the schedule's chosen channels (an
        # explicit, owner-configured choice) intersected with each
        # recipient's own channel preference (still enforced inside
        # enqueue_notifications_for_event).
        channel_enums = {c for c in (_safe_channel(value) for value in channels) if c is not None}
        outbox_rows = enqueue_notifications_for_event(
            db,
            hotel_id=schedule.hotel_id,
            event_type="report.daily",
            dedupe_key=f"daily_report:{schedule.hotel_id}:{local_now.date().isoformat()}",
            title=f"Daily operational report - {local_now.date().isoformat()}",
            body=body,
            severity=NotificationSeverityEnum.INFO,
            recipient_user_ids=recipient_ids,
            recipient_roles=recipient_roles,
            channels=channel_enums or None,
        )

        schedule.last_sent_date_local = local_now.date()
        db.flush()
        results.append({"hotel_id": schedule.hotel_id, "local_date": local_now.date().isoformat(), "outbox_rows": len(outbox_rows)})

    return results
