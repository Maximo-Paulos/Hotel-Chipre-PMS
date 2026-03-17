"""
OTA (Online Travel Agency) reservation mapping.
Tracks the link between external OTA bookings and internal reservations.
"""
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Enum
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
    reservation_id = Column(Integer, ForeignKey("reservations.id", ondelete="SET NULL"), nullable=True)

    ota_name = Column(String(50), nullable=False)          # "booking", "expedia"
    ota_reservation_id = Column(String(100), nullable=False)  # External booking code
    ota_guest_name = Column(String(250), nullable=True)

    raw_payload = Column(Text, nullable=True)  # Full JSON payload from OTA

    sync_status = Column(
        Enum(OTASyncStatusEnum, name="ota_sync_status_enum", create_constraint=True),
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
    reservation = relationship("Reservation", lazy="joined")

    def __repr__(self) -> str:
        return (
            f"<OTAReservationMapping(ota='{self.ota_name}', "
            f"ota_id='{self.ota_reservation_id}', status={self.sync_status})>"
        )
