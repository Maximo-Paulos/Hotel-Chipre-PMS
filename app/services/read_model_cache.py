from __future__ import annotations

import json
import logging
import time
from concurrent.futures import Future
from datetime import date
from threading import RLock
from typing import Any, Callable, TypeVar

import redis
from fastapi.encoders import jsonable_encoder

from app.config import get_settings
logger = logging.getLogger(__name__)
T = TypeVar("T")

_redis_client: redis.Redis | None = None
_redis_client_url: str | None = None
_redis_unavailable_until = 0.0
_redis_was_unavailable = False
_redis_availability_known = False
_redis_state_lock = RLock()
_LOCAL_READ_MODEL_TTL_SECONDS = 2.0
_LOCAL_READ_MODEL_MAX_ENTRIES = 128
_local_read_model_cache: dict[str, tuple[float, Any]] = {}
_local_read_model_inflight: dict[str, Future[Any]] = {}
_local_read_model_lock = RLock()


def _settings():
    return get_settings()


def _cache_enabled() -> bool:
    return bool(_settings().READ_MODEL_CACHE_ENABLED)


def _redis_failure_cooldown_seconds() -> float:
    try:
        return max(float(_settings().READ_MODEL_CACHE_FAILURE_COOLDOWN_SECONDS), 0.0)
    except (AttributeError, TypeError, ValueError):
        return 30.0


def _redis_timeout_seconds(settings: Any, setting_name: str) -> float:
    """Use the shared Redis client's bounded timeout defaults for cache I/O."""
    try:
        return max(float(getattr(settings, setting_name, 1.0)), 0.1)
    except (TypeError, ValueError):
        return 1.0


def _mark_redis_unavailable(exc: Exception | None = None) -> None:
    global _redis_unavailable_until, _redis_was_unavailable

    now = time.monotonic()
    with _redis_state_lock:
        was_in_cooldown = _redis_unavailable_until > now
        _redis_unavailable_until = now + _redis_failure_cooldown_seconds()
        if not was_in_cooldown:
            logger.warning(
                "read_model_cache.redis_unavailable",
                extra={
                    "error_type": type(exc).__name__ if exc else "unknown",
                    "cooldown_seconds": _redis_failure_cooldown_seconds(),
                },
            )
        _redis_was_unavailable = True


def _mark_redis_available() -> None:
    global _redis_unavailable_until, _redis_was_unavailable, _redis_availability_known

    with _redis_state_lock:
        _redis_unavailable_until = 0.0
        if not _redis_availability_known or _redis_was_unavailable:
            logger.info("read_model_cache.redis_available")
        _redis_availability_known = True
        _redis_was_unavailable = False


def _get_redis_client() -> redis.Redis | None:
    global _redis_client, _redis_client_url, _redis_unavailable_until, _redis_was_unavailable, _redis_availability_known

    if not _cache_enabled():
        return None

    settings = _settings()
    redis_url = settings.REDIS_URL
    now = time.monotonic()
    with _redis_state_lock:
        if _redis_client_url != redis_url:
            _redis_client = None
            _redis_client_url = redis_url
            _redis_unavailable_until = 0.0
            _redis_was_unavailable = False
            _redis_availability_known = False
        if _redis_unavailable_until > now:
            return None
        if _redis_client is not None:
            return _redis_client
        try:
            _redis_client = redis.Redis.from_url(
                redis_url,
                decode_responses=True,
                socket_connect_timeout=_redis_timeout_seconds(settings, "REDIS_CONNECT_TIMEOUT_SECONDS"),
                socket_timeout=_redis_timeout_seconds(settings, "REDIS_SOCKET_TIMEOUT_SECONDS"),
            )
        except Exception as exc:  # pragma: no cover - defensive runtime fallback
            _mark_redis_unavailable(exc)
            return None
        return _redis_client


def _load_json(raw_value: str | None) -> Any | None:
    if not raw_value:
        return None
    try:
        return json.loads(raw_value)
    except json.JSONDecodeError:
        return None


def _store_json(key: str, payload: Any, ttl_seconds: int, *, client: redis.Redis | None = None) -> None:
    if client is None:
        client = _get_redis_client()
    if client is None:
        return
    try:
        client.setex(key, ttl_seconds, json.dumps(jsonable_encoder(payload), ensure_ascii=True, sort_keys=True))
        _mark_redis_available()
    except Exception as exc:  # pragma: no cover - defensive runtime fallback
        _mark_redis_unavailable(exc)


def _get_local_cached_or_compute(key: str, producer: Callable[[], T]) -> T:
    now = time.monotonic()
    with _local_read_model_lock:
        cached = _local_read_model_cache.get(key)
        if cached is not None:
            expires_at, payload = cached
            if expires_at > now:
                return payload
            _local_read_model_cache.pop(key, None)

        pending = _local_read_model_inflight.get(key)
        is_producer = pending is None
        if pending is None:
            pending = Future()
            _local_read_model_inflight[key] = pending

    if not is_producer:
        return pending.result()

    try:
        payload = producer()
    except BaseException as exc:
        with _local_read_model_lock:
            if _local_read_model_inflight.get(key) is pending:
                _local_read_model_inflight.pop(key, None)
        pending.set_exception(exc)
        raise

    cached_at = time.monotonic()
    with _local_read_model_lock:
        expired_keys = [
            cached_key
            for cached_key, (expires_at, _cached_payload) in _local_read_model_cache.items()
            if expires_at <= now
        ]
        for cached_key in expired_keys:
            _local_read_model_cache.pop(cached_key, None)
        while len(_local_read_model_cache) >= _LOCAL_READ_MODEL_MAX_ENTRIES:
            _local_read_model_cache.pop(next(iter(_local_read_model_cache)))
        _local_read_model_cache[key] = (cached_at + _LOCAL_READ_MODEL_TTL_SECONDS, payload)
        if _local_read_model_inflight.get(key) is pending:
            _local_read_model_inflight.pop(key, None)
    pending.set_result(payload)
    return payload


def _get_cached_or_compute(
    key: str,
    ttl_seconds: int,
    producer: Callable[[], T],
    *,
    local_fallback: bool = False,
) -> T:
    if not _cache_enabled():
        return _get_local_cached_or_compute(key, producer) if local_fallback else producer()

    client = _get_redis_client()
    if client is None:
        return _get_local_cached_or_compute(key, producer) if local_fallback else producer()

    try:
        cached = _load_json(client.get(key))
        _mark_redis_available()
        if cached is not None:
            return cached
    except Exception as exc:  # pragma: no cover - defensive runtime fallback
        _mark_redis_unavailable(exc)
        return _get_local_cached_or_compute(key, producer) if local_fallback else producer()

    payload = producer()
    _store_json(key, payload, ttl_seconds, client=client)
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


def _rate_calendar_key(hotel_id: int, category_id: int, date_from: date, date_to: date) -> str:
    return (
        f"hotel:{hotel_id}:rate_calendar:category:{category_id}:"
        f"from:{date_from.isoformat()}:to:{date_to.isoformat()}"
    )


def _daily_report_key(hotel_id: int, report_date: date, pending_page: int, pending_page_size: int) -> str:
    return (
        f"hotel:{hotel_id}:daily_report:date:{report_date.isoformat()}:"
        f"pending_page:{pending_page}:page_size:{pending_page_size}"
    )


def _occupancy_grid_key(hotel_id: int, date_from: date, date_to: date, role: str) -> str:
    # The grid applies role visibility windows before returning reservations;
    # include the role so one role's projection cannot populate another's.
    return (
        f"hotel:{hotel_id}:occupancy_grid:from:{date_from.isoformat()}:"
        f"to:{date_to.isoformat()}:role:{role}"
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
        local_fallback=True,
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
        local_fallback=True,
    )


def get_cached_rate_calendar_payload(
    *,
    hotel_id: int,
    category_id: int,
    date_from: date,
    date_to: date,
    producer: Callable[[], T],
) -> T:
    return _get_cached_or_compute(
        _rate_calendar_key(hotel_id, category_id, date_from, date_to),
        _settings().READ_MODEL_AVAILABILITY_TTL_SECONDS,
        producer,
    )


def get_cached_daily_report_payload(
    *,
    hotel_id: int,
    report_date: date,
    pending_page: int = 1,
    pending_page_size: int = 50,
    producer: Callable[[], T],
) -> T:
    return _get_cached_or_compute(
        _daily_report_key(hotel_id, report_date, pending_page, pending_page_size),
        _settings().READ_MODEL_ANALYTICS_TTL_SECONDS,
        producer,
        local_fallback=True,
    )


def get_cached_occupancy_grid_payload(
    *,
    hotel_id: int,
    date_from: date,
    date_to: date,
    role: str,
    producer: Callable[[], T],
) -> T:
    return _get_cached_or_compute(
        _occupancy_grid_key(hotel_id, date_from, date_to, role),
        _settings().READ_MODEL_AVAILABILITY_TTL_SECONDS,
        producer,
    )


def invalidate_hotel_operational_caches(hotel_id: int) -> None:
    _invalidate_hotel_cache_prefixes(
        hotel_id,
        (
            "availability",
            "analytics",
            "rate_calendar",
            "daily_report",
            "occupancy_grid",
        ),
    )


def invalidate_hotel_analytics_cache(hotel_id: int) -> None:
    _invalidate_hotel_cache_prefixes(hotel_id, ("analytics",))


def _invalidate_hotel_cache_prefixes(hotel_id: int, families: tuple[str, ...]) -> None:
    prefixes = tuple(f"hotel:{hotel_id}:{family}:" for family in families)
    with _local_read_model_lock:
        for key in tuple(_local_read_model_cache):
            if key.startswith(prefixes):
                _local_read_model_cache.pop(key, None)

    client = _get_redis_client()
    if client is None:
        return
    try:
        keys: list[str] = []
        for family in families:
            keys.extend(list(client.scan_iter(match=f"hotel:{hotel_id}:{family}:*")))
        if keys:
            client.delete(*keys)
        _mark_redis_available()
    except Exception as exc:  # pragma: no cover - defensive runtime fallback
        _mark_redis_unavailable(exc)
