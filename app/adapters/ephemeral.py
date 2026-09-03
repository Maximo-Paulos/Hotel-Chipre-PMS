"""Ports for infrastructure that is safe to lose and rebuild.

These protocols deliberately contain no business authority. PostgreSQL owns
transactions, idempotency and audit; implementations here are cache,
publication and short-lived coordination only.
"""
from __future__ import annotations

from typing import Any, Protocol


class CacheStore(Protocol):
    def get(self, key: str) -> str | None: ...
    def setex(self, key: str, ttl_seconds: int, value: str) -> Any: ...
    def delete(self, *keys: str) -> Any: ...


class EventBus(Protocol):
    def publish(self, channel: str, message: str) -> Any: ...


class LockManager(Protocol):
    def acquire(self, key: str, *, ttl_seconds: int) -> bool: ...
    def release(self, key: str, token: str) -> Any: ...

