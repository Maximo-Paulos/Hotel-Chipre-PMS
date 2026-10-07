"""Short-lived singleflight cache for PostgreSQL event-outbox polling.

The PostgreSQL SSE fallback is opened once per browser tab, but all streams in
one process usually poll the same hotel and cursor. Sharing each bounded poll
result avoids one identical database round-trip per connected tab. The cache
only stores invalidation metadata for at most one poll interval; PostgreSQL
remains authoritative and a recovered stream always catches up from its own
cursor.
"""
from __future__ import annotations

import logging
import math
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Callable, Generic, Hashable, TypeVar


logger = logging.getLogger(__name__)
T = TypeVar("T")


@dataclass(frozen=True)
class _CachedFailure:
    error_type: str


@dataclass(frozen=True)
class _PollEntry(Generic[T]):
    created_at: float
    ttl_seconds: float
    value: tuple[T, ...] | _CachedFailure


class CachedOutboxPollFailure(RuntimeError):
    """A same-window poll failed already; wait for the next bounded retry."""

    def __init__(self, error_type: str) -> None:
        self.error_type = error_type
        super().__init__(error_type)


class OutboxPollBatchCache(Generic[T]):
    """Deduplicate concurrent per-process polls without extending freshness."""

    def __init__(
        self,
        *,
        max_entries: int = 1024,
        monotonic: Callable[[], float] = time.monotonic,
        summary_interval_seconds: float = 60.0,
    ) -> None:
        self._max_entries = max(1, int(max_entries))
        self._clock = monotonic
        self._summary_interval_seconds = max(float(summary_interval_seconds), 1.0)
        self._guard = threading.RLock()
        self._entries: OrderedDict[Hashable, _PollEntry[T]] = OrderedDict()
        self._key_locks: OrderedDict[Hashable, threading.Lock] = OrderedDict()
        self._key_lock_users: dict[Hashable, int] = {}
        self._window_started_at = self._clock()
        self._lookups = 0
        self._database_polls = 0
        self._cache_hits = 0
        self._rows = 0
        self._errors = 0
        self._database_duration_ms = 0.0

    def get(
        self,
        key: Hashable,
        *,
        ttl_seconds: float,
        loader: Callable[[], list[T]],
    ) -> list[T]:
        ttl = self._bounded_ttl(ttl_seconds)
        with self._guard:
            self._lookups += 1
            key_lock = self._lock_for(key)
            self._key_lock_users[key] = self._key_lock_users.get(key, 0) + 1

        try:
            with key_lock:
                return self._get_locked(key, ttl, loader)
        finally:
            with self._guard:
                users = self._key_lock_users.get(key, 0)
                if users <= 1:
                    self._key_lock_users.pop(key, None)
                else:
                    self._key_lock_users[key] = users - 1
                self._prune_key_locks()

    def _get_locked(self, key: Hashable, ttl: float, loader: Callable[[], list[T]]) -> list[T]:
        now = self._clock()
        with self._guard:
            entry = self._entries.get(key)
            if entry is not None and now - entry.created_at < min(entry.ttl_seconds, ttl):
                self._entries.move_to_end(key)
                self._cache_hits += 1
                self._maybe_log_window(now)
                cached_value = entry.value
            else:
                if entry is not None:
                    self._entries.pop(key, None)
                cached_value = None

        if isinstance(cached_value, _CachedFailure):
            raise CachedOutboxPollFailure(cached_value.error_type) from None
        if cached_value is not None:
            return list(cached_value)

        started_at = self._clock()
        try:
            loaded = tuple(loader())
        except Exception as exc:
            finished_at = self._clock()
            with self._guard:
                self._database_polls += 1
                self._errors += 1
                self._database_duration_ms += max(finished_at - started_at, 0.0) * 1000.0
                if ttl > 0:
                    self._store(key, _PollEntry(finished_at, ttl, _CachedFailure(type(exc).__name__)))
                self._maybe_log_window(finished_at)
            raise

        finished_at = self._clock()
        with self._guard:
            self._database_polls += 1
            self._rows += len(loaded)
            self._database_duration_ms += max(finished_at - started_at, 0.0) * 1000.0
            if ttl > 0:
                self._store(key, _PollEntry(finished_at, ttl, loaded))
            self._maybe_log_window(finished_at)
        return list(loaded)

    @staticmethod
    def _bounded_ttl(ttl_seconds: float) -> float:
        try:
            ttl = float(ttl_seconds)
        except (TypeError, ValueError):
            return 0.0
        return ttl if math.isfinite(ttl) and ttl > 0 else 0.0

    def _lock_for(self, key: Hashable) -> threading.Lock:
        lock = self._key_locks.get(key)
        if lock is None:
            lock = threading.Lock()
            self._key_locks[key] = lock
        self._key_locks.move_to_end(key)

        return lock

    def _prune_key_locks(self) -> None:
        while len(self._key_locks) > self._max_entries:
            removable = next(
                (
                    candidate for candidate in self._key_locks if self._key_lock_users.get(candidate, 0) == 0
                ),
                None,
            )
            if removable is None:
                break
            self._key_locks.pop(removable, None)

    def _store(self, key: Hashable, entry: _PollEntry[T]) -> None:
        self._entries[key] = entry
        self._entries.move_to_end(key)
        while len(self._entries) > self._max_entries:
            self._entries.popitem(last=False)

    def _maybe_log_window(self, now: float) -> None:
        elapsed = now - self._window_started_at
        if elapsed < self._summary_interval_seconds or self._lookups == 0:
            return
        logger.info(
            "realtime_events.postgres_poll_window interval_seconds=%.1f poll_lookups=%s database_polls=%s cache_hits=%s rows=%s errors=%s database_duration_ms=%.2f",
            elapsed,
            self._lookups,
            self._database_polls,
            self._cache_hits,
            self._rows,
            self._errors,
            self._database_duration_ms,
        )
        self._window_started_at = now
        self._lookups = 0
        self._database_polls = 0
        self._cache_hits = 0
        self._rows = 0
        self._errors = 0
        self._database_duration_ms = 0.0
