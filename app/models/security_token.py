"""
Persisted one-time security tokens for email verification and password reset.
"""
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String, Text, Index

from app.database import Base


class SecurityToken(Base):
    __tablename__ = "security_tokens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    token_type = Column(String(50), nullable=False, index=True)
    subject_key = Column(String(255), nullable=False, index=True)
    code_hash = Column(Text, nullable=False)
    expires_at = Column(DateTime, nullable=False, index=True)
    consumed_at = Column(DateTime, nullable=True, index=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("ix_security_tokens_lookup", "token_type", "subject_key", "consumed_at"),
    )
