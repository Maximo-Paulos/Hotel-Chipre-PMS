"""
Tiny in‑memory rate limiter for login attempts.

We keep per‑key counters within a sliding window. Good enough for the demo;
swap for Redis in production.
"""
from collections import defaultdict
from datetime import datetime, timedelta
from threading import Lock


class SimpleRateLimiter:
    def __init__(self, limit: int = 5, window_seconds: int = 900):
        self.limit = limit
        self.window = timedelta(seconds=window_seconds)
        self._buckets: dict[str, list[datetime]] = defaultdict(list)
        self._lock = Lock()

    def allow(self, key: str) -> bool:
        now = datetime.utcnow()
        with self._lock:
            bucket = self._buckets[key]
            cutoff = now - self.window
            # drop old attempts
            while bucket and bucket[0] < cutoff:
                bucket.pop(0)
            if len(bucket) >= self.limit:
                return False
            bucket.append(now)
            return True

    def reset(self, key: str) -> None:
        with self._lock:
            if key in self._buckets:
                self._buckets.pop(key, None)


# default limiter used by auth endpoints
login_limiter = SimpleRateLimiter()
# rate limiter for password reset requests (per email)
reset_request_limiter = SimpleRateLimiter(limit=3, window_seconds=15 * 60)
# rate limiter for invitations (per inviter user)
invite_limiter = SimpleRateLimiter(limit=5, window_seconds=60 * 60)
