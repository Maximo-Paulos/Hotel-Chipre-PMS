"""Tenant-scoped realtime domain events backed by Redis/Valkey pub/sub.

Postgres remains the source of truth. These events are only invalidation
signals: consumers must refetch the authoritative API representation.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

import redis

from app.config import get_settings


logger = logging.getLogger(__name__)

EVENT_CHANNEL_TEMPLATE = "hotel:{hotel_id}:events"
REVISION_KEY_TEMPLATE = "hotel:{hotel_id}:revision:{domain}"
EVENT_NAME = "domain_change"
SUPPORTED_DOMAINS = frozenset(
    {
        "analytics",
        "cash",
        "guests",
        "onboarding",
        "payments",
        "reservations",
        "rooms",
        "settings",
        "stock",
        "users",
    }
)

# Event payloads are deliberately identifiers and operational metadata only.
# Guest contact data, credentials, tokens, and payment proofs never belong in
# Redis pub/sub messages.
SAFE_PAYLOAD_KEYS = frozenset(
    {
        "category_id",
        "family",
        "group_id",
        "item_id",
        "location_id",
        "payment_id",
        "reservation_id",
        "room_id",
        "source",
        "status",
        "user_id",
    }
)


class RealtimeEventsUnavailable(RuntimeError):
    """Raised when a required Redis/Valkey realtime backend is unavailable."""


@dataclass(frozen=True)
class DomainEvent:
    hotel_id: int
    domain: str
    event_type: str
    revision: int
    occurred_at: str
    payload: dict[str, Any]

    @property
    def channel(self) -> str:
        return channel_for_hotel(self.hotel_id)

    def as_payload(self) -> dict[str, Any]:
        return {
            "version": 1,
            "hotel_id": self.hotel_id,
            "domain": self.domain,
            "event_type": self.event_type,
            "revision": self.revision,
            "occurred_at": self.occurred_at,
            "payload": dict(self.payload),
        }


def _settings():
    return get_settings()


def channel_for_hotel(hotel_id: int) -> str:
    _validate_hotel_id(hotel_id)
    return EVENT_CHANNEL_TEMPLATE.format(hotel_id=hotel_id)


def revision_key_for_hotel(hotel_id: int, domain: str) -> str:
    _validate_hotel_id(hotel_id)
    if domain not in SUPPORTED_DOMAINS:
        raise ValueError("Unsupported domain")
    return REVISION_KEY_TEMPLATE.format(hotel_id=hotel_id, domain=domain)


def validate_event_input(
    *,
    hotel_id: int,
    domain: str,
    event_type: str,
    payload: Mapping[str, Any] | None,
) -> dict[str, Any]:
    _validate_hotel_id(hotel_id)
    normalized_domain = str(domain or "").strip().lower()
    if normalized_domain not in SUPPORTED_DOMAINS:
        raise ValueError("Unsupported domain")
    normalized_type = str(event_type or "").strip()
    if not normalized_type or len(normalized_type) > 100 or any(char.isspace() for char in normalized_type):
        raise ValueError("Event type must be non-empty and contain no whitespace")

    normalized_payload = dict(payload or {})
    unknown_keys = set(normalized_payload) - SAFE_PAYLOAD_KEYS
    if unknown_keys:
        raise ValueError("Unsupported payload key: " + ", ".join(sorted(unknown_keys)))
    for key, value in normalized_payload.items():
        if isinstance(value, (dict, list, tuple, set)):
            raise ValueError(f"Payload value for {key} must be scalar")
        if value is not None and not isinstance(value, (str, int, float, bool)):
            raise ValueError(f"Payload value for {key} must be JSON scalar")
    json.dumps(normalized_payload, ensure_ascii=True, allow_nan=False)
    return normalized_payload


def _validate_hotel_id(hotel_id: int) -> None:
    if not isinstance(hotel_id, int) or hotel_id <= 0:
        raise ValueError("hotel_id must be a positive integer")


def _get_redis_client() -> redis.Redis | None:
    settings = _settings()
    if not bool(getattr(settings, "REALTIME_EVENTS_ENABLED", True)):
        return None
    try:
        return redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
    except Exception as exc:  # pragma: no cover - defensive config fallback
        logger.warning("realtime_events.redis_unavailable", extra={"error": str(exc)})
        return None


def _required() -> bool:
    return bool(_settings().DISTRIBUTED_LOCK_REQUIRED)


def _unavailable(message: str, exc: Exception | None = None):
    if _required():
        raise RealtimeEventsUnavailable(message) from exc
    logger.warning("realtime_events.degraded", extra={"error": message})


def publish_domain_event(
    *,
    hotel_id: int,
    domain: str,
    event_type: str,
    payload: Mapping[str, Any] | None = None,
    client: redis.Redis | None = None,
) -> DomainEvent | None:
    normalized_payload = validate_event_input(
        hotel_id=hotel_id,
        domain=domain,
        event_type=event_type,
        payload=payload,
    )
    if not bool(getattr(_settings(), "REALTIME_EVENTS_ENABLED", True)):
        return None
    redis_client = client or _get_redis_client()
    if redis_client is None:
        _unavailable("Redis/Valkey realtime backend is unavailable")
        return None

    try:
        revision = int(redis_client.incr(revision_key_for_hotel(hotel_id, domain)))
        event = DomainEvent(
            hotel_id=hotel_id,
            domain=domain.strip().lower(),
            event_type=event_type.strip(),
            revision=revision,
            occurred_at=datetime.now(timezone.utc).isoformat(),
            payload=normalized_payload,
        )
        redis_client.publish(event.channel, json.dumps(event.as_payload(), ensure_ascii=True, allow_nan=False))
        return event
    except Exception as exc:
        _unavailable("Redis/Valkey realtime publish failed", exc)
        return None


def get_realtime_client() -> redis.Redis | None:
    """Return a configured client after a bounded connectivity check."""

    if not bool(getattr(_settings(), "REALTIME_EVENTS_ENABLED", True)):
        return None
    client = _get_redis_client()
    if client is None:
        _unavailable("Redis/Valkey realtime backend is unavailable")
        return None
    try:
        client.ping()
    except Exception as exc:
        _unavailable("Redis/Valkey realtime backend is unavailable", exc)
        return None
    return client


def format_sse(payload: Mapping[str, Any], *, event_name: str = EVENT_NAME) -> str:
    return f"event: {event_name}\ndata: {json.dumps(dict(payload), ensure_ascii=True, allow_nan=False)}\n\n"


def iter_event_stream(hotel_id: int, client: redis.Redis, *, heartbeat_seconds: int = 15) -> Iterable[str]:
    """Yield a tenant-scoped SSE stream; sync iteration runs in Starlette's worker."""

    pubsub = client.pubsub(ignore_subscribe_messages=True)
    pubsub.subscribe(channel_for_hotel(hotel_id))
    try:
        yield format_sse({"version": 1, "hotel_id": hotel_id, "status": "ready"}, event_name="ready")
        while True:
            message = pubsub.get_message(timeout=heartbeat_seconds)
            if message and message.get("type") == "message":
                raw_data = message.get("data")
                if isinstance(raw_data, bytes):
                    raw_data = raw_data.decode("utf-8")
                try:
                    payload = json.loads(raw_data)
                except (TypeError, json.JSONDecodeError):
                    logger.warning("realtime_events.invalid_message", extra={"hotel_id": hotel_id})
                    continue
                if isinstance(payload, dict) and payload.get("hotel_id") == hotel_id:
                    yield format_sse(payload)
            else:
                yield ": heartbeat\n\n"
    finally:
        try:
            pubsub.close()
        except Exception:  # pragma: no cover - best effort cleanup
            logger.debug("realtime_events.pubsub_close_failed", exc_info=True)
