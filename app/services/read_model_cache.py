from __future__ import annotations

import json
import logging
from datetime import date
from typing import Any, Callable, TypeVar

import redis
from fastapi.encoders import jsonable_encoder

from app.config import get_settings
from app.services.domain_events import RealtimeEventsUnavailable, publish_domain_event


logger = logging.getLogger(__name__)
T = TypeVar("T")


def _publish_cache_event(*, hotel_id: int, event_type: str, family: str) -> None:
    """Best-effort invalidation signal; never turn a committed OLTP write into a false 500."""

    try:
        publish_domain_event(
            hotel_id=hotel_id,
            domain="analytics",
            event_type=event_type,
            payload={"family": family},
        )
    except RealtimeEventsUnavailable:
        logger.error(
            "read_model_cache.realtime_event_unavailable",
            extra={"hotel_id": hotel_id, "family": family},
        )


def _settings():
    return get_settings()


def _cache_enabled() -> bool:
    return bool(_settings().READ_MODEL_CACHE_ENABLED)


def _get_redis_client() -> redis.Redis | None:
    if not _cache_enabled():
        return None
    try:
        return redis.Redis.from_url(_settings().REDIS_URL, decode_responses=True)
    except Exception as exc:  # pragma: no cover - defensive runtime fallback
        logger.warning("read_model_cache.redis_unavailable", extra={"error_type": type(exc).__name__})
        return None


def _load_json(raw_value: str | None) -> Any | None:
    if not raw_value:
        return None
    try:
        return json.loads(raw_value)
    except json.JSONDecodeError:
        return None


def _store_json(key: str, payload: Any, ttl_seconds: int) -> None:
    client = _get_redis_client()
    if client is None:
        return
    try:
        client.setex(key, ttl_seconds, json.dumps(jsonable_encoder(payload), ensure_ascii=True, sort_keys=True))
    except Exception as exc:  # pragma: no cover - defensive runtime fallback
        logger.warning("read_model_cache.store_failed", extra={"key": key, "error_type": type(exc).__name__})


def _get_cached_or_compute(key: str, ttl_seconds: int, producer: Callable[[], T]) -> T:
    client = _get_redis_client()
    if client is not None:
        try:
            cached = _load_json(client.get(key))
            if cached is not None:
                return cached
        except Exception as exc:  # pragma: no cover - defensive runtime fallback
            logger.warning("read_model_cache.read_failed", extra={"key": key, "error_type": type(exc).__name__})

    payload = producer()
    _store_json(key, payload, ttl_seconds)
    return payload


def _date_token(value: date | None) -> str:
    return value.isoformat() if value else "none"


def _availability_key(hotel_id: int, category_id: int, check_in: date, check_out: date) -> str:
    return (
        f"hotel:{hotel_id}:availability:"
        f"category:{category_id}:checkin:{check_in.isoformat()}:checkout:{check_out.isoformat()}"
    )


def _analytics_starter_key(hotel_id: int, date_from: date | None, date_to: date | None) -> str:
    return f"hotel:{hotel_id}:analytics:starter:from:{_date_token(date_from)}:to:{_date_token(date_to)}"


def _analytics_home_key(
    hotel_id: int,
    date_from: date | None,
    date_to: date | None,
    currency_display: str,
    compare_previous: bool,
    compare_yoy: bool,
) -> str:
    return (
        f"hotel:{hotel_id}:analytics:home:from:{_date_token(date_from)}:to:{_date_token(date_to)}:"
        f"currency:{currency_display.upper()}:previous:{int(compare_previous)}:yoy:{int(compare_yoy)}"
    )


def get_cached_availability_payload(
    *,
    hotel_id: int,
    category_id: int,
    check_in: date,
    check_out: date,
    producer: Callable[[], T],
) -> T:
    return _get_cached_or_compute(
        _availability_key(hotel_id, category_id, check_in, check_out),
        _settings().READ_MODEL_AVAILABILITY_TTL_SECONDS,
        producer,
    )


def get_cached_starter_summary_payload(
    *,
    hotel_id: int,
    date_from: date | None,
    date_to: date | None,
    producer: Callable[[], T],
) -> T:
    return _get_cached_or_compute(
        _analytics_starter_key(hotel_id, date_from, date_to),
        _settings().READ_MODEL_ANALYTICS_TTL_SECONDS,
        producer,
    )


def get_cached_home_payload(
    *,
    hotel_id: int,
    date_from: date | None,
    date_to: date | None,
    currency_display: str,
    compare_previous: bool,
    compare_yoy: bool,
    producer: Callable[[], T],
) -> T:
    return _get_cached_or_compute(
        _analytics_home_key(
            hotel_id,
            date_from,
            date_to,
            currency_display,
            compare_previous,
            compare_yoy,
        ),
        _settings().READ_MODEL_ANALYTICS_TTL_SECONDS,
        producer,
    )


def invalidate_hotel_operational_caches(hotel_id: int) -> None:
    _invalidate_hotel_cache_prefixes(
        hotel_id,
        ("availability", "analytics"),
    )
    _publish_cache_event(
        hotel_id=hotel_id,
        event_type="operational.read_model_invalidated",
        family="availability",
    )


def invalidate_hotel_analytics_cache(hotel_id: int) -> None:
    _invalidate_hotel_cache_prefixes(hotel_id, ("analytics",))
    _publish_cache_event(
        hotel_id=hotel_id,
        event_type="analytics.invalidated",
        family="analytics",
    )


def _invalidate_hotel_cache_prefixes(hotel_id: int, families: tuple[str, ...]) -> None:
    client = _get_redis_client()
    if client is None:
        return
    try:
        keys: list[str] = []
        for family in families:
            keys.extend(list(client.scan_iter(match=f"hotel:{hotel_id}:{family}:*")))
        if keys:
            client.delete(*keys)
    except Exception as exc:  # pragma: no cover - defensive runtime fallback
        logger.warning(
            "read_model_cache.invalidate_failed",
            extra={"hotel_id": hotel_id, "families": ",".join(families), "error_type": type(exc).__name__},
        )
