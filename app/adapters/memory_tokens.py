"""
Persisted one-time token store for email verification and password reset.

The file name is kept for compatibility, but the implementation now stores
tokens in the database instead of process memory.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.database import get_session_factory
from app.models.security_token import SecurityToken
from app.services.security import hash_password, verify_password


class TokenStore:
    def issue(
        self,
        db: Session,
        token_type: str,
        subject_key: str,
        code: str,
        ttl_minutes: int = 15,
    ) -> str:
        normalized_subject = self._normalize_subject(subject_key)
        now = self._utcnow()
        expires_at = now + timedelta(minutes=ttl_minutes)

        db.query(SecurityToken).filter(
            SecurityToken.token_type == token_type,
            SecurityToken.subject_key == normalized_subject,
            SecurityToken.consumed_at.is_(None),
        ).delete(synchronize_session=False)

        db.add(
            SecurityToken(
                token_type=token_type,
                subject_key=normalized_subject,
                code_hash=hash_password(code),
                expires_at=expires_at,
            )
        )
        db.flush()
        return code

    def verify(
        self,
        db: Session,
        token_type: str,
        subject_key: str,
        code: str,
        consume: bool = True,
    ) -> bool:
        normalized_subject = self._normalize_subject(subject_key)
        token = self._get_active_token(db, token_type, normalized_subject)
        if not token:
            return False
        now = self._utcnow()
        expires_at = self._coerce_utc(token.expires_at)
        if expires_at <= now:
            token.consumed_at = now
            db.flush()
            return False
        if not verify_password(code, token.code_hash):
            return False
        if consume:
            token.consumed_at = now
        db.flush()
        return True

    def cleanup(self, db: Optional[Session] = None) -> int:
        owns_session = False
        if db is None:
            factory = get_session_factory()
            db = factory()
            owns_session = True

        try:
            now = self._utcnow()
            deleted = (
                db.query(SecurityToken)
                .filter(
                    (SecurityToken.expires_at <= now) | (SecurityToken.consumed_at.is_not(None))
                )
                .delete(synchronize_session=False)
            )
            db.commit()
            return int(deleted or 0)
        finally:
            if owns_session:
                db.close()

    def _get_active_token(self, db: Session, token_type: str, subject_key: str) -> Optional[SecurityToken]:
        return (
            db.query(SecurityToken)
            .filter(
                SecurityToken.token_type == token_type,
                SecurityToken.subject_key == subject_key,
                SecurityToken.consumed_at.is_(None),
            )
            .order_by(SecurityToken.created_at.desc())
            .first()
        )

    @staticmethod
    def _normalize_subject(subject_key: str) -> str:
        return (subject_key or "").strip().lower()

    @staticmethod
    def _utcnow() -> datetime:
        return datetime.now(timezone.utc).replace(tzinfo=None)

    @staticmethod
    def _coerce_utc(value: datetime) -> datetime:
        if value is None:
            return datetime.min
        if value.tzinfo is not None:
            return value.astimezone(timezone.utc).replace(tzinfo=None)
        return value


token_store = TokenStore()
