"""
Operational reservation models for adjustments, room moves and audit history.
"""
from __future__ import annotations

from datetime import datetime, timezone
import enum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
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
        Enum(
            ReservationAdjustmentKindEnum,
            name="reservation_adjustment_kind_enum",
            create_constraint=True,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
    )
    status = Column(
        Enum(
            ReservationAdjustmentStatusEnum,
            name="reservation_adjustment_status_enum",
            create_constraint=True,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
        default=ReservationAdjustmentStatusEnum.DRAFT,
    )
    reason_code = Column(String(50), nullable=True)
    request_source = Column(String(50), nullable=True)
    notes = Column(Text, nullable=True)
    amount_delta = Column(Numeric(12, 2), nullable=True)
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


class RoomMovementGroup(Base):
    """
    Groups multiple RoomMoveEvents triggered by the same cause (v72 §5.4).
    Supports batch revert by owner/co-owner/manager.
    """
    __tablename__ = "room_movement_groups"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False)
    trigger_reason = Column(String(100), nullable=False)   # e.g. "overbooking_resolution_2026-08-01"
    notes = Column(Text, nullable=True)
    is_reverted = Column(Boolean, nullable=False, default=False)
    reverted_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reverted_at = Column(DateTime, nullable=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    move_events = relationship("RoomMoveEvent", back_populates="movement_group", lazy="selectin")

    __table_args__ = (
        Index("ix_room_movement_groups_hotel_id", "hotel_id"),
    )

    def __repr__(self) -> str:
        return f"<RoomMovementGroup(id={self.id}, hotel_id={self.hotel_id}, reverted={self.is_reverted})>"


class RoomMoveEvent(Base):
    __tablename__ = "room_move_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False)
    reservation_id = Column(Integer, ForeignKey("reservations.id", ondelete="CASCADE"), nullable=False)
    movement_group_id = Column(Integer, ForeignKey("room_movement_groups.id", ondelete="SET NULL"), nullable=True)
    from_room_id = Column(Integer, ForeignKey("rooms.id", ondelete="SET NULL"), nullable=True)
    to_room_id = Column(Integer, ForeignKey("rooms.id", ondelete="SET NULL"), nullable=True)
    move_type = Column(
        Enum(
            RoomMoveTypeEnum,
            name="room_move_type_enum",
            create_constraint=True,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
        default=RoomMoveTypeEnum.MANUAL_MOVE,
    )
    reason_code = Column(String(50), nullable=True)
    reason_note = Column(Text, nullable=True)           # v72 §5.3: motivo obligatorio para movimiento manual
    trigger_event = Column(String(100), nullable=True)  # v72 §5.5: e.g. "new_reservation", "block_created"
    state_before = Column(String(50), nullable=True)    # v72 §5.5: reservation/room state before move
    state_after = Column(String(50), nullable=True)     # v72 §5.5: reservation/room state after move
    # For an occupied-stay move the operator must explicitly decide what
    # happens to the vacated room. These remain nullable for historical and
    # system-generated moves; legacy rows must not be backfilled by inference.
    origin_room_disposition = Column(String(20), nullable=True)
    origin_room_disposition_note = Column(Text, nullable=True)
    origin_room_status_before = Column(String(30), nullable=True)
    origin_room_status_after = Column(String(30), nullable=True)
    notes = Column(Text, nullable=True)
    occurred_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    reservation = relationship("Reservation", lazy="joined")
    movement_group = relationship("RoomMovementGroup", back_populates="move_events", lazy="joined")
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
        Index("ix_room_move_events_hotel_occurred_at", "hotel_id", "occurred_at", "id"),
        Index("ix_room_move_events_hotel_rooms", "hotel_id", "from_room_id", "to_room_id"),
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
        Enum(
            BillingAdjustmentTypeEnum,
            name="billing_adjustment_type_enum",
            create_constraint=True,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
    )
    amount = Column(Numeric(12, 2), nullable=False)
    currency_code = Column(String(3), nullable=False, default="ARS")
    tax_amount = Column(Numeric(12, 2), nullable=True)
    total_amount = Column(Numeric(12, 2), nullable=False)
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
        Index("ix_reservation_status_history_hotel_changed_actor", "hotel_id", "changed_at", "changed_by_user_id"),
    )
