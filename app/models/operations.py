"""
Operational reservation models for adjustments, room moves and audit history.
"""
from __future__ import annotations

from datetime import datetime, timezone
import enum

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.database import Base


class ReservationAdjustmentKindEnum(str, enum.Enum):
    UPGRADE = "upgrade"
    DOWNGRADE = "downgrade"
    DATE_CHANGE = "date_change"
    OTA_CANCEL_AND_REBOOK = "ota_cancel_and_rebook"
    MANUAL_RATE_OVERRIDE = "manual_rate_override"
    REFUND = "refund"
    OTHER = "other"


class ReservationAdjustmentStatusEnum(str, enum.Enum):
    DRAFT = "draft"
    PENDING = "pending"
    APPLIED = "applied"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RoomMoveTypeEnum(str, enum.Enum):
    AUTO_ASSIGNMENT = "auto_assignment"
    MANUAL_MOVE = "manual_move"
    UPGRADE = "upgrade"
    DOWNGRADE = "downgrade"
    OVERBOOKING_RESOLUTION = "overbooking_resolution"
    MAINTENANCE_RELOCATION = "maintenance_relocation"


class BillingAdjustmentTypeEnum(str, enum.Enum):
    CHARGE = "charge"
    CREDIT = "credit"
    REFUND = "refund"
    COMMISSION = "commission"
    TAX_CORRECTION = "tax_correction"
    FX_CORRECTION = "fx_correction"


class ReservationAdjustment(Base):
    __tablename__ = "reservation_adjustments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False)
    reservation_id = Column(Integer, ForeignKey("reservations.id", ondelete="CASCADE"), nullable=False)
    resulting_reservation_id = Column(Integer, ForeignKey("reservations.id", ondelete="SET NULL"), nullable=True)
    ota_reservation_link_id = Column(Integer, ForeignKey("ota_reservation_links.id", ondelete="SET NULL"), nullable=True)
    kind = Column(
        Enum(ReservationAdjustmentKindEnum, name="reservation_adjustment_kind_enum", create_constraint=True),
        nullable=False,
    )
    status = Column(
        Enum(ReservationAdjustmentStatusEnum, name="reservation_adjustment_status_enum", create_constraint=True),
        nullable=False,
        default=ReservationAdjustmentStatusEnum.DRAFT,
    )
    reason_code = Column(String(50), nullable=True)
    request_source = Column(String(50), nullable=True)
    notes = Column(Text, nullable=True)
    amount_delta = Column(Float, nullable=True)
    currency_code = Column(String(3), nullable=True)
    external_resolution_status = Column(String(50), nullable=True)
    requested_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    approved_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    reservation = relationship("Reservation", foreign_keys=[reservation_id], lazy="joined")
    resulting_reservation = relationship("Reservation", foreign_keys=[resulting_reservation_id], lazy="joined")
    ota_reservation_link = relationship("OTAReservationLink", lazy="joined")
    created_by = relationship("User", lazy="joined")

    __table_args__ = (
        Index("ix_reservation_adjustments_hotel_id", "hotel_id"),
        Index("ix_reservation_adjustments_reservation_id", "reservation_id"),
    )


class RoomMoveEvent(Base):
    __tablename__ = "room_move_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False)
    reservation_id = Column(Integer, ForeignKey("reservations.id", ondelete="CASCADE"), nullable=False)
    from_room_id = Column(Integer, ForeignKey("rooms.id", ondelete="SET NULL"), nullable=True)
    to_room_id = Column(Integer, ForeignKey("rooms.id", ondelete="SET NULL"), nullable=True)
    move_type = Column(
        Enum(RoomMoveTypeEnum, name="room_move_type_enum", create_constraint=True),
        nullable=False,
        default=RoomMoveTypeEnum.MANUAL_MOVE,
    )
    reason_code = Column(String(50), nullable=True)
    notes = Column(Text, nullable=True)
    occurred_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    reservation = relationship("Reservation", lazy="joined")
    from_room = relationship("Room", foreign_keys=[from_room_id], lazy="joined")
    to_room = relationship("Room", foreign_keys=[to_room_id], lazy="joined")
    created_by = relationship("User", lazy="joined")

    __table_args__ = (
        CheckConstraint(
            "from_room_id IS NOT NULL OR to_room_id IS NOT NULL",
            name="ck_room_move_events_requires_room",
        ),
        Index("ix_room_move_events_hotel_id", "hotel_id"),
        Index("ix_room_move_events_reservation_id", "reservation_id"),
    )


class BillingAdjustment(Base):
    __tablename__ = "billing_adjustments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False)
    reservation_id = Column(Integer, ForeignKey("reservations.id", ondelete="CASCADE"), nullable=False)
    reservation_adjustment_id = Column(
        Integer,
        ForeignKey("reservation_adjustments.id", ondelete="SET NULL"),
        nullable=True,
    )
    adjustment_type = Column(
        Enum(BillingAdjustmentTypeEnum, name="billing_adjustment_type_enum", create_constraint=True),
        nullable=False,
    )
    amount = Column(Float, nullable=False)
    currency_code = Column(String(3), nullable=False, default="ARS")
    tax_amount = Column(Float, nullable=True)
    total_amount = Column(Float, nullable=False)
    effective_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    notes = Column(Text, nullable=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    reservation = relationship("Reservation", lazy="joined")
    reservation_adjustment = relationship("ReservationAdjustment", lazy="joined")
    created_by = relationship("User", lazy="joined")

    __table_args__ = (
        CheckConstraint("total_amount != 0", name="ck_billing_adjustments_total_nonzero"),
        Index("ix_billing_adjustments_hotel_id", "hotel_id"),
        Index("ix_billing_adjustments_reservation_id", "reservation_id"),
    )


class ReservationStatusHistory(Base):
    __tablename__ = "reservation_status_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False)
    reservation_id = Column(Integer, ForeignKey("reservations.id", ondelete="CASCADE"), nullable=False)
    from_status = Column(String(50), nullable=True)
    to_status = Column(String(50), nullable=False)
    reason_code = Column(String(50), nullable=True)
    notes = Column(Text, nullable=True)
    changed_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    changed_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    reservation = relationship("Reservation", lazy="joined")
    changed_by = relationship("User", lazy="joined")

    __table_args__ = (
        Index("ix_reservation_status_history_hotel_id", "hotel_id"),
        Index("ix_reservation_status_history_reservation_id", "reservation_id"),
    )
