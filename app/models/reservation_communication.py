"""Auditable guest communications initiated from a reservation."""

from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)

from app.database import Base


class ReservationEmailKindEnum(str, enum.Enum):
    CONFIRMATION = "confirmation"
    VOUCHER = "voucher"


class ReservationEmailStatusEnum(str, enum.Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    FAILED = "failed"
    UNKNOWN = "unknown"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ReservationEmailDelivery(Base):
    """One attempted reservation email, scoped to the owning hotel.

    ``accepted`` means Gmail accepted the message for processing. It does not
    claim final delivery. ``unknown`` is deliberately terminal for automatic
    retries: an operator must choose an explicit resend after an uncertain
    provider result.
    """

    __tablename__ = "reservation_email_deliveries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False)
    reservation_id = Column(Integer, nullable=False)
    kind = Column(
        Enum(
            ReservationEmailKindEnum,
            name="reservation_email_kind_enum",
            native_enum=False,
            create_constraint=True,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
    )
    status = Column(
        Enum(
            ReservationEmailStatusEnum,
            name="reservation_email_status_enum",
            native_enum=False,
            create_constraint=True,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        default=ReservationEmailStatusEnum.PENDING,
    )
    recipient_email = Column(String(320), nullable=False)
    subject = Column(String(255), nullable=False)
    provider_message_id = Column(String(255), nullable=True)
    attempt_count = Column(Integer, nullable=False, default=1, server_default="1")
    is_resend = Column(Boolean, nullable=False, default=False, server_default="0")
    requested_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    last_error = Column(String(300), nullable=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    updated_at = Column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)
    accepted_at = Column(DateTime, nullable=True)

    __table_args__ = (
        ForeignKeyConstraint(
            ["hotel_id", "reservation_id"],
            ["reservations.hotel_id", "reservations.id"],
            name="fk_reservation_email_deliveries_hotel_reservation",
            ondelete="CASCADE",
        ),
        UniqueConstraint("hotel_id", "id", name="uq_reservation_email_deliveries_hotel_id_id"),
        Index(
            "ix_reservation_email_deliveries_hotel_reservation_created",
            "hotel_id",
            "reservation_id",
            "created_at",
        ),
    )
