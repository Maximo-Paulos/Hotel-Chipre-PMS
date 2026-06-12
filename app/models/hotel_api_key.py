"""
Hotel API key model — v72 §16.

Each hotel can have multiple named API credentials used by:
  - WhatsApp bot integration
  - Web booking engine
  - External channel managers (beyond standard OTA connectors)

The secret is stored hashed (bcrypt / SHA-256 hex); the plain-text value is
only returned once at creation time and never stored in cleartext.
"""
from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)

from app.database import Base


class APIKeyPurposeEnum(str, enum.Enum):
    WHATSAPP_BOT = "whatsapp_bot"
    WEB_ENGINE = "web_engine"
    CHANNEL_MANAGER = "channel_manager"
    REPORTING = "reporting"
    OTHER = "other"


class HotelAPIKey(Base):
    """
    Per-hotel API credential. `key_hash` stores a hashed version of the secret;
    `key_prefix` stores the first 8 chars of the raw key for identification.
    """
    __tablename__ = "hotel_api_keys"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(
        Integer,
        ForeignKey("hotel_configuration.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_by_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    name = Column(String(100), nullable=False)
    purpose = Column(
        Enum(
            APIKeyPurposeEnum,
            name="api_key_purpose_enum",
            create_constraint=True,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
        default=APIKeyPurposeEnum.OTHER,
    )

    key_prefix = Column(String(8), nullable=False)
    key_hash = Column(String(128), nullable=False)

    is_active = Column(Boolean, nullable=False, default=True)
    last_used_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    revoked_at = Column(DateTime, nullable=True)
    revoked_by_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    __table_args__ = (
        UniqueConstraint("hotel_id", "name", name="uq_hotel_api_key_name"),
        Index("ix_hotel_api_keys_hotel_id", "hotel_id"),
    )

    def __repr__(self) -> str:
        return f"<HotelAPIKey(id={self.id}, hotel={self.hotel_id}, name={self.name!r}, purpose={self.purpose})>"
