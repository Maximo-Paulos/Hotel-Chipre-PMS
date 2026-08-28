"""Public marketing inquiries submitted through the website."""
from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Enum, Index, Integer, String, Text

from app.database import Base


class PublicInquiryNotificationStatus(str, enum.Enum):
    NOT_CONFIGURED = "not_configured"
    SENT = "sent"
    FAILED = "failed"


class PublicInquiry(Base):
    """A contact request captured by the public marketing site.

    The table is intentionally not tenant-scoped: public marketing inquiries
    belong to the platform sales channel, not to a hotel account.
    """

    __tablename__ = "public_inquiries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(120), nullable=False)
    email = Column(String(320), nullable=False)
    company_name = Column(String(160), nullable=True)
    phone = Column(String(50), nullable=True)
    message = Column(Text, nullable=False)
    source_path = Column(String(200), nullable=False, default="/contacto")
    privacy_consent_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    notification_status = Column(
        Enum(
            PublicInquiryNotificationStatus,
            name="public_inquiry_notification_status",
            create_constraint=True,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        default=PublicInquiryNotificationStatus.NOT_CONFIGURED,
    )
    notified_at = Column(DateTime, nullable=True)
    notification_error_type = Column(String(80), nullable=True)

    __table_args__ = (Index("ix_public_inquiries_created_at", "created_at"),)
