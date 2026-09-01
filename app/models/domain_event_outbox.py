"""Durable, tenant-scoped outbox for realtime domain invalidations.

The row is committed together with the business mutation.  Redis/Valkey is
only the delivery transport, so a worker can replay rows that were still
pending when the web process stopped after its database commit.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Index, Integer, JSON, String, func
from sqlalchemy.dialects.postgresql import JSONB

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


_PAYLOAD_TYPE = JSON().with_variant(JSONB(), "postgresql")


class DomainEventOutbox(Base):
    """One durable delivery attempt for one hotel/domain invalidation."""

    __tablename__ = "domain_event_outbox"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(
        Integer,
        ForeignKey("hotel_configuration.id", ondelete="CASCADE"),
        nullable=False,
    )
    domain = Column(String(50), nullable=False)
    event_type = Column(String(100), nullable=False)
    payload = Column(_PAYLOAD_TYPE, nullable=False)

    # Zero means the row has not received a Redis revision yet.  A worker or
    # the after_commit fast path fills it immediately after Redis accepts the
    # event; keeping the durable row insert independent of Redis is the point
    # of this outbox.
    revision = Column(Integer, nullable=False, default=0, server_default="0")
    occurred_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
    )
    published_at = Column(DateTime(timezone=True), nullable=True)
    attempts = Column(Integer, nullable=False, default=0, server_default="0")
    # Only a bounded error code/type is stored.  Provider messages can contain
    # connection details or other sensitive operational data.
    last_error = Column(String(120), nullable=True)

    __table_args__ = (
        Index("ix_domain_event_outbox_pending", "hotel_id", "published_at", "id"),
        CheckConstraint("revision >= 0", name="ck_domain_event_outbox_revision_nonnegative"),
        CheckConstraint("attempts >= 0", name="ck_domain_event_outbox_attempts_nonnegative"),
    )
