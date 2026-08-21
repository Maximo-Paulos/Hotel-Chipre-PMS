"""
Rate limiter with DB-backed persistence for security-sensitive endpoints.

When a DB session is provided, throttling events are stored in the database so
limits survive process restarts and multiple workers. We keep an in-memory
fallback for utility code that does not pass a session.
"""
from collections import defaultdict
from datetime import datetime, timedelta, timezone
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

    def allow(self, key: str, db: Session | None = None, limit: int | None = None) -> bool:
        normalized_key = self._normalize_key(key)
        effective_limit = self.limit if limit is None else limit
        if db is not None:
            return self._allow_db(normalized_key, db, effective_limit)

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        with self._lock:
            bucket = self._buckets[normalized_key]
            cutoff = now - self.window
            while bucket and bucket[0] < cutoff:
                bucket.pop(0)
            if len(bucket) >= effective_limit:
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

    def _allow_db(self, key: str, db: Session, limit: int) -> bool:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        cutoff = now - self.window
        db.query(RateLimitEvent).filter(
            RateLimitEvent.scope == self.scope,
            RateLimitEvent.subject_key == key,
            RateLimitEvent.created_at < cutoff,
        ).delete(synchronize_session=False)
        db.add(RateLimitEvent(scope=self.scope, subject_key=key))
        db.flush()
        # Insert-first narrows the race window; under READ COMMITTED, perfectly
        # simultaneous transactions can still miss each other's uncommitted rows.
        active_count = (
            db.query(RateLimitEvent)
            .filter(
                RateLimitEvent.scope == self.scope,
                RateLimitEvent.subject_key == key,
                RateLimitEvent.created_at >= cutoff,
            )
            .count()
        )
        return active_count <= limit

    @staticmethod
    def _normalize_key(key: str) -> str:
        return (key or "").strip().lower()


login_limiter = SimpleRateLimiter("login")
register_limiter = SimpleRateLimiter("register", limit=5, window_seconds=15 * 60)
verify_request_limiter = SimpleRateLimiter("email_verification_request", limit=3, window_seconds=15 * 60)
reset_request_limiter = SimpleRateLimiter("password_reset", limit=3, window_seconds=15 * 60)
# The neutral no-account email path is intentionally still bounded by source.
# The per-email limits above prevent code abuse; these limits prevent an actor
# from spraying arbitrary recipient addresses to force outbound mail.
verify_request_source_limiter = SimpleRateLimiter(
    "email_verification_request_source", limit=5, window_seconds=15 * 60
)
reset_request_source_limiter = SimpleRateLimiter(
    "password_reset_source", limit=5, window_seconds=15 * 60
)
invite_limiter = SimpleRateLimiter("invite_user", limit=5, window_seconds=60 * 60)
invitation_preview_limiter = SimpleRateLimiter("invitation_preview", limit=30, window_seconds=15 * 60)
invitation_accept_limiter = SimpleRateLimiter("invitation_accept", limit=10, window_seconds=15 * 60)

# Throttles guesses of the 6-digit one-time codes themselves (as opposed to
# how often a new code can be requested). Without this, /verify-email,
# /validate-reset and /reset-password had no attempt limit at all, so a code
# could be brute-forced within its TTL. Keyed by "{token_type}:{email}" so
# validate-reset and reset-password share a budget against the same code.
code_guess_limiter = SimpleRateLimiter("code_guess", limit=8, window_seconds=15 * 60)
mfa_code_guess_limiter = SimpleRateLimiter("mfa_code_guess", limit=8, window_seconds=15 * 60)
