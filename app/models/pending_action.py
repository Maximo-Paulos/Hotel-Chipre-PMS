"""
PendingOperationalAction — the "pending_actions" table referenced throughout the
master plan (master-plan-pilot-to-public.md §A1–A2).

Created whenever the system can't safely auto-resolve a situation:
  - OTA conflict (cancel post-checkin, duplicate, modify with availability gap)
  - Allocation manual_review (solver can't assign without human decision)
  - Refund manual_review (neither gateway nor voucher resolved it)
  - Settlement discrepancy
  - Other operational follow-up

An action is resolved when a human user explicitly marks it resolved (with an
optional note). It can also be dismissed (not an error but not actionable either).

Unlike ReservationAdjustment (which tracks what changed), this tracks what NEEDS
to happen and who is responsible for making the call.
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
    Text,
)
from sqlalchemy.orm import relationship

from app.database import Base


class PendingActionTypeEnum(str, enum.Enum):
    MANUAL_REVIEW_REQUIRED = "manual_review_required"
    OTA_CONFLICT = "ota_conflict"
    ROOM_MOVE_NEEDED = "room_move_needed"
    REFUND_PENDING = "refund_pending"
    SETTLEMENT_REVIEW = "settlement_review"
    ALLOCATION_CONFLICT = "allocation_conflict"
    PAYMENT_DISCREPANCY = "payment_discrepancy"
    OTHER = "other"


class PendingActionStatusEnum(str, enum.Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class PendingActionPriorityEnum(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class PendingOperationalAction(Base):
    """
    A follow-up item that requires a human decision before the operation can proceed.
    Created by the system; resolved (or dismissed) by staff.
    """
    __tablename__ = "pending_operational_actions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(
        Integer,
        ForeignKey("hotel_configuration.id", ondelete="CASCADE"),
        nullable=False,
    )
    reservation_id = Column(
        Integer,
        ForeignKey("reservations.id", ondelete="SET NULL"),
        nullable=True,
    )

    action_type = Column(
        Enum(
            PendingActionTypeEnum,
            name="pending_action_type_enum",
            create_constraint=True,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
    )
    status = Column(
        Enum(
            PendingActionStatusEnum,
            name="pending_action_status_enum",
            create_constraint=True,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
        default=PendingActionStatusEnum.OPEN,
    )
    priority = Column(
        Enum(
            PendingActionPriorityEnum,
            name="pending_action_priority_enum",
            create_constraint=True,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
        default=PendingActionPriorityEnum.MEDIUM,
    )

    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)

    # The entity that originated this action (e.g. allocation_run, ota_reservation_link)
    source_entity_type = Column(String(100), nullable=True)
    source_entity_id = Column(Integer, nullable=True)

    is_system_generated = Column(Boolean, nullable=False, default=True)

    assigned_to_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    resolved_at = Column(DateTime, nullable=True)
    resolved_by_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    resolution_note = Column(Text, nullable=True)

    hotel = relationship("HotelConfiguration", lazy="select")
    reservation = relationship("Reservation", lazy="select")
    assigned_to = relationship("User", foreign_keys=[assigned_to_user_id], lazy="select")
    resolved_by = relationship("User", foreign_keys=[resolved_by_user_id], lazy="select")

    __table_args__ = (
        Index("ix_pending_actions_hotel_status", "hotel_id", "status"),
        Index("ix_pending_actions_hotel_reservation", "hotel_id", "reservation_id"),
        Index("ix_pending_actions_hotel_type_status", "hotel_id", "action_type", "status"),
    )

    def __repr__(self) -> str:
        return (
            f"<PendingOperationalAction(id={self.id}, hotel={self.hotel_id}, "
            f"type={self.action_type}, status={self.status}, priority={self.priority})>"
        )
