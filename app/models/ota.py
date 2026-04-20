"""
OTA (Online Travel Agency) reservation mapping.
Tracks the link between external OTA bookings and internal reservations.
"""
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Enum, Boolean, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import enum

from app.database import Base


class OTASyncStatusEnum(str, enum.Enum):
    PENDING = "pending"
    SYNCED = "synced"
    FAILED = "failed"
    CONFLICT = "conflict"


class OTAReservationMapping(Base):
    """
    Maps an external OTA reservation to an internal reservation.
    Stores the raw payload and sync status for audit and debugging.
    """
    __tablename__ = "ota_reservation_mappings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False)
    reservation_id = Column(Integer, ForeignKey("reservations.id", ondelete="SET NULL"), nullable=True)

    ota_name = Column(String(50), nullable=False)          # "booking", "expedia"
    ota_reservation_id = Column(String(100), nullable=False)  # External booking code
    ota_guest_name = Column(String(250), nullable=True)

    raw_payload = Column(Text, nullable=True)  # Full JSON payload from OTA

    sync_status = Column(
        Enum(
            OTASyncStatusEnum,
            name="ota_sync_status_enum",
            create_constraint=True,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
        default=OTASyncStatusEnum.PENDING,
    )
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime, nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    hotel = relationship("HotelConfiguration", lazy="joined")
    reservation = relationship("Reservation", lazy="joined")

    __table_args__ = (
        UniqueConstraint("hotel_id", "ota_name", "ota_reservation_id", name="uq_ota_mapping_hotel_provider_reservation"),
        Index("ix_ota_reservation_mappings_hotel_id", "hotel_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<OTAReservationMapping(ota='{self.ota_name}', "
            f"ota_id='{self.ota_reservation_id}', status={self.sync_status})>"
        )


class OTAWebhookCredential(Base):
    """
    Per-hotel OTA webhook credential. The secret is stored as a hash so the
    raw token can be embedded in the webhook URL without being persisted in cleartext.
    """

    __tablename__ = "ota_webhook_credentials"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False)
    provider = Column(String(50), nullable=False)
    webhook_secret_hash = Column(String(128), nullable=False)
    external_property_id = Column(String(120), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    hotel = relationship("HotelConfiguration", lazy="joined")

    __table_args__ = (
        UniqueConstraint("hotel_id", "provider", name="uq_ota_webhook_credential_hotel_provider"),
        Index("ix_ota_webhook_credentials_hotel_id", "hotel_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<OTAWebhookCredential(hotel_id={self.hotel_id}, provider='{self.provider}', "
            f"active={self.is_active})>"
        )
