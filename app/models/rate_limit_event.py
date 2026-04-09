"""
Persistent rate-limit events for security-sensitive endpoints.
"""
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Index, Integer, String

from app.database import Base


class RateLimitEvent(Base):
    __tablename__ = "rate_limit_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    scope = Column(String(50), nullable=False, index=True)
    subject_key = Column(String(255), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), index=True)

    __table_args__ = (
        Index("ix_rate_limit_scope_subject_created", "scope", "subject_key", "created_at"),
    )
