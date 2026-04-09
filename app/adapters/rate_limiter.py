"""
Rate limiter with DB-backed persistence for security-sensitive endpoints.

When a DB session is provided, throttling events are stored in the database so
limits survive process restarts and multiple workers. We keep an in-memory
fallback for utility code that does not pass a session.
"""
from collections import defaultdict
from datetime import datetime, timedelta
from threading import Lock

from sqlalchemy.orm import Session

from app.models.rate_limit_event import RateLimitEvent


class SimpleRateLimiter:
    def __init__(self, scope: str, limit: int = 5, window_seconds: int = 900):
        self.scope = scope
        self.limit = limit
        self.window = timedelta(seconds=window_seconds)
        self._buckets: dict[str, list[datetime]] = defaultdict(list)
        self._lock = Lock()

    def allow(self, key: str, db: Session | None = None) -> bool:
        normalized_key = self._normalize_key(key)
        if db is not None:
            return self._allow_db(normalized_key, db)

        now = datetime.utcnow()
        with self._lock:
            bucket = self._buckets[normalized_key]
            cutoff = now - self.window
            while bucket and bucket[0] < cutoff:
                bucket.pop(0)
            if len(bucket) >= self.limit:
                return False
            bucket.append(now)
            return True

    def reset(self, key: str, db: Session | None = None) -> None:
        normalized_key = self._normalize_key(key)
        if db is not None:
            db.query(RateLimitEvent).filter(
                RateLimitEvent.scope == self.scope,
                RateLimitEvent.subject_key == normalized_key,
            ).delete(synchronize_session=False)
            db.flush()
            return

        with self._lock:
            if normalized_key in self._buckets:
                self._buckets.pop(normalized_key, None)

    def _allow_db(self, key: str, db: Session) -> bool:
        now = datetime.utcnow()
        cutoff = now - self.window
        db.query(RateLimitEvent).filter(
            RateLimitEvent.scope == self.scope,
            RateLimitEvent.subject_key == key,
            RateLimitEvent.created_at < cutoff,
        ).delete(synchronize_session=False)
        active_count = (
            db.query(RateLimitEvent)
            .filter(
                RateLimitEvent.scope == self.scope,
                RateLimitEvent.subject_key == key,
                RateLimitEvent.created_at >= cutoff,
            )
            .count()
        )
        if active_count >= self.limit:
            return False
        db.add(RateLimitEvent(scope=self.scope, subject_key=key))
        db.flush()
        return True

    @staticmethod
    def _normalize_key(key: str) -> str:
        return (key or "").strip().lower()


login_limiter = SimpleRateLimiter("login")
verify_request_limiter = SimpleRateLimiter("email_verification_request", limit=3, window_seconds=15 * 60)
reset_request_limiter = SimpleRateLimiter("password_reset", limit=3, window_seconds=15 * 60)
invite_limiter = SimpleRateLimiter("invite_user", limit=5, window_seconds=60 * 60)
