"""Shared Redis/Valkey client construction.

Redis is a best-effort layer in this application. The module centralizes
timeouts, environment namespace handling and one client per process while
callers remain responsible for deciding whether a failed operation is a miss,
degraded publication, or a closed critical path.
"""
from __future__ import annotations

import logging
from threading import RLock
from typing import Any

import redis
import redis.asyncio as redis_async

from app.config import get_settings

logger = logging.getLogger(__name__)
_lock = RLock()
_sync_client: redis.Redis | None = None
_sync_signature: tuple[str, float, float, int] | None = None
_async_client: redis_async.Redis | None = None
_async_signature: tuple[str, float, float, int] | None = None


def redis_namespace() -> str:
    settings = get_settings()
    configured = str(getattr(settings, "REDIS_NAMESPACE", "") or "").strip().strip(":")
    if configured:
        return configured
    # Empty is retained as a compatibility mode for existing local test
    # doubles. Deployments should set REDIS_NAMESPACE explicitly.
    return ""


def namespaced_key(key: str) -> str:
    if not isinstance(key, str) or not key:
        raise ValueError("Redis keys must be non-empty strings")
    namespace = redis_namespace()
    return f"{namespace}:{key}" if namespace else key


def _client_signature() -> tuple[str, float, float, int]:
    settings = get_settings()
    url = str(settings.REDIS_URL or "").strip()
    connect_timeout = max(float(getattr(settings, "REDIS_CONNECT_TIMEOUT_SECONDS", 1.0)), 0.1)
    socket_timeout = max(float(getattr(settings, "REDIS_SOCKET_TIMEOUT_SECONDS", 1.0)), 0.1)
    # Keep test doubles and hot-reloaded workers from retaining a client built
    # by a previous constructor while preserving one client per process for
    # the normal production factory.
    return url, connect_timeout, socket_timeout, id(redis.Redis.from_url)


def get_sync_redis_client(*, capability: str = "general") -> redis.Redis | None:
    """Return one sync client per process, or None for empty configuration."""
    del capability  # retained for caller diagnostics without multiplying pools
    global _sync_client, _sync_signature
    signature = _client_signature()
    if not signature[0]:
        return None
    with _lock:
        if _sync_signature != signature:
            _sync_client = None
            _sync_signature = signature
        if _sync_client is None:
            try:
                _sync_client = redis.Redis.from_url(
                    signature[0],
                    decode_responses=True,
                    socket_connect_timeout=signature[1],
                    socket_timeout=signature[2],
                )
            except Exception as exc:  # pragma: no cover - defensive config path
                logger.warning("redis_backend.client_creation_failed", extra={"error_type": type(exc).__name__})
                return None
        return _sync_client


def get_async_redis_client(*, capability: str = "general") -> redis_async.Redis | None:
    """Return one async client per process for async transports."""
    del capability
    global _async_client, _async_signature
    signature = _client_signature()
    if not signature[0]:
        return None
    with _lock:
        if _async_signature != signature:
            _async_client = None
            _async_signature = signature
        if _async_client is None:
            try:
                _async_client = redis_async.from_url(
                    signature[0],
                    decode_responses=True,
                    socket_connect_timeout=signature[1],
                    socket_timeout=signature[2],
                )
            except Exception as exc:  # pragma: no cover - defensive config path
                logger.warning("redis_backend.async_client_creation_failed", extra={"error_type": type(exc).__name__})
                return None
        return _async_client


def reset_clients() -> None:
    """Clear process clients for tests and orderly shutdown."""
    global _sync_client, _sync_signature, _async_client, _async_signature
    with _lock:
        _sync_client = None
        _sync_signature = None
        _async_client = None
        _async_signature = None
