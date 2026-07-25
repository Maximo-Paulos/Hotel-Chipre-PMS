"""Small Redis/Valkey lease used to serialize cross-worker critical paths."""

from __future__ import annotations

import hashlib
import logging
import secrets
from contextlib import contextmanager
from functools import wraps
from inspect import signature
from typing import Callable, Iterator, ParamSpec, TypeVar

import redis
from sqlalchemy import text

from app.config import get_settings


logger = logging.getLogger(__name__)
P = ParamSpec("P")
R = TypeVar("R")

_RELEASE_SCRIPT = "if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('del', KEYS[1]) else return 0 end"


class DistributedLockBusy(RuntimeError):
    """Raised when another worker currently owns the lease."""


class DistributedLockUnavailable(RuntimeError):
    """Raised when a required lock backend cannot be reached."""


def _settings():
    return get_settings()


def _get_redis_client() -> redis.Redis | None:
    if not _settings().DISTRIBUTED_LOCK_ENABLED:
        return None
    try:
        return redis.Redis.from_url(_settings().REDIS_URL, decode_responses=True)
    except Exception as exc:  # pragma: no cover - defensive configuration fallback
        logger.warning("distributed_lock.redis_unavailable", extra={"error": str(exc)})
        return None


def _required() -> bool:
    return bool(_settings().DISTRIBUTED_LOCK_REQUIRED)


def _try_postgres_advisory_lock(db: object | None, key: str) -> bool | None:
    """Acquire a transaction-scoped PostgreSQL advisory lock when available.

    ``True`` means the current transaction owns the lock, ``False`` means
    another transaction owns it, and ``None`` means PostgreSQL locking cannot
    be used. Transaction-scoped locks are released by the API transaction's
    commit or rollback, so no best-effort release can unlock another worker.
    """

    if db is None:
        return None

    try:
        bind = db.get_bind()  # type: ignore[attr-defined]
        if getattr(getattr(bind, "dialect", None), "name", None) != "postgresql":
            return None
        lock_id = int.from_bytes(hashlib.blake2b(key.encode("utf-8"), digest_size=8).digest(), "big", signed=True)
        return bool(
            db.execute(  # type: ignore[attr-defined]
                text("SELECT pg_try_advisory_xact_lock(:lock_id)"),
                {"lock_id": lock_id},
            ).scalar_one()
        )
    except Exception as exc:  # pragma: no cover - defensive provider fallback
        logger.warning("distributed_lock.postgres_advisory_unavailable", extra={"lock_key": key, "error": str(exc)})
        return None


@contextmanager
def distributed_lock(key: str, *, db: object | None = None, ttl_seconds: int | None = None) -> Iterator[None]:
    """Acquire a short lease and release it only if this worker owns it.

    Redis/Valkey is the primary lease backend. A PostgreSQL transaction-scoped
    advisory lock keeps critical operations serialized when the current
    database transaction is PostgreSQL and Redis is unavailable. Otherwise an
    optional backend degrades only in non-required mode; production fails
    closed rather than pretending an operation is serialized.
    """

    if not key or any(character.isspace() for character in key):
        raise ValueError("Distributed lock keys must be non-empty and contain no whitespace")

    client = _get_redis_client()
    if client is None:
        postgres_acquired = _try_postgres_advisory_lock(db, key)
        if postgres_acquired:
            yield
            return
        if postgres_acquired is False:
            raise DistributedLockBusy(f"Distributed lock is already held: {key}")
        if _required():
            raise DistributedLockUnavailable("Distributed lock backend is unavailable")
        yield
        return

    ttl = ttl_seconds or _settings().DISTRIBUTED_LOCK_DEFAULT_TTL_SECONDS
    if ttl <= 0:
        raise ValueError("Distributed lock TTL must be positive")

    token = secrets.token_urlsafe(24)
    try:
        acquired = bool(client.set(key, token, nx=True, ex=ttl))
    except Exception as exc:
        postgres_acquired = _try_postgres_advisory_lock(db, key)
        if postgres_acquired:
            yield
            return
        if postgres_acquired is False:
            raise DistributedLockBusy(f"Distributed lock is already held: {key}")
        if _required():
            raise DistributedLockUnavailable("Distributed lock backend is unavailable") from exc
        logger.warning("distributed_lock.acquire_degraded", extra={"lock_key": key, "error": str(exc)})
        yield
        return

    if not acquired:
        raise DistributedLockBusy(f"Distributed lock is already held: {key}")

    try:
        yield
    finally:
        try:
            client.eval(_RELEASE_SCRIPT, 1, key, token)
        except Exception as exc:  # pragma: no cover - lock TTL remains the recovery mechanism
            logger.warning("distributed_lock.release_failed", extra={"lock_key": key, "error": str(exc)})


def with_distributed_lock(
    family: str,
    *parameter_names: str,
    ttl_seconds: int | None = None,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorate a service operation with a deterministic hotel-scoped lease."""

    if not family or not parameter_names:
        raise ValueError("A lock family and at least one parameter are required")

    def decorator(function: Callable[P, R]) -> Callable[P, R]:
        parameters = signature(function)

        @wraps(function)
        def wrapped(*args: P.args, **kwargs: P.kwargs) -> R:
            bound = parameters.bind(*args, **kwargs)
            lock_values = ":".join(str(bound.arguments[name]) for name in parameter_names)
            with distributed_lock(
                f"lock:{family}:{lock_values}",
                db=bound.arguments.get("db"),
                ttl_seconds=ttl_seconds,
            ):
                return function(*args, **kwargs)

        return wrapped

    return decorator
