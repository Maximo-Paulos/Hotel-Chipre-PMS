"""Tenant-scoped cursor watermarks used by outbox retention cleanup."""
from datetime import datetime, timezone

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, PrimaryKeyConstraint, String, func

from app.database import Base


class DomainEventRetentionWatermark(Base):
    __tablename__ = "domain_event_outbox_retention_watermarks"

    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False)
    domain = Column(String(50), nullable=False)
    watermark = Column(BigInteger, nullable=False, default=0, server_default="0")
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )

    __table_args__ = (
        PrimaryKeyConstraint("hotel_id", "domain", name="pk_domain_event_retention_watermark"),
    )
