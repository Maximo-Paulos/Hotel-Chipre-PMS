"""
Naive in-memory token store for verification/reset codes (dev/stage).
Replace with persistent store (DB/Redis) in production.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, Tuple


class TokenStore:
    def __init__(self):
        self._tokens: Dict[str, Tuple[str, datetime]] = {}

    def get(self, email: str) -> str | None:
        """Return code if still valid (without consuming), else None."""
        key = email.lower()
        entry = self._tokens.get(key)
        if not entry:
            return None
        code, expires = entry
        if datetime.utcnow() > expires:
            self._tokens.pop(key, None)
            return None
        return code

    def set(self, email: str, code: str, ttl_minutes: int = 15) -> None:
        self._tokens[email.lower()] = (code, datetime.utcnow() + timedelta(minutes=ttl_minutes))

    def verify(self, email: str, code: str) -> bool:
        key = email.lower()
        entry = self._tokens.get(key)
        if not entry:
            return False
        stored, expires = entry
        if datetime.utcnow() > expires:
            self._tokens.pop(key, None)
            return False
        if stored != code:
            return False
        self._tokens.pop(key, None)
        return True


token_store = TokenStore()
