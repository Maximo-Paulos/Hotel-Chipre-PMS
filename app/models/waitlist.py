"""
Waitlist / overbooking list model — v72 §9.

When the hotel is at capacity for a category+date range, guests can be placed
on a waitlist. If a cancellation opens up, the service layer promotes the
highest-priority waiting entry and notifies the guest.

Distinct from normal reservations so that availability queries never count
waitlisted guests as occupying a room.
"""
from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    Column,
    Date,
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


class WaitlistStatusEnum(str, enum.Enum):
    WAITING = "waiting"
    PROMOTED = "promoted"      # converted to a real reservation
    CANCELLED = "cancelled"    # guest withdrew
    EXPIRED = "expired"        # dates passed without a slot opening


class WaitlistEntry(Base):
    """
    Single guest waiting for a room in a given category for a date range.
    Priority is determined by the `priority` field (lower = higher priority)
    and `created_at` for ties.
    """
    __tablename__ = "waitlist_entries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(
        Integer,
        ForeignKey("hotel_configuration.id", ondelete="CASCADE"),
        nullable=False,
    )
    guest_id = Column(
        Integer,
        ForeignKey("guests.id", ondelete="CASCADE"),
        nullable=False,
    )
    category_id = Column(
        Integer,
        ForeignKey("room_categories.id", ondelete="CASCADE"),
        nullable=False,
    )
    promoted_reservation_id = Column(
        Integer,
        ForeignKey("reservations.id", ondelete="SET NULL"),
        nullable=True,
    )

    check_in_date = Column(Date, nullable=False)
    check_out_date = Column(Date, nullable=False)
    num_adults = Column(Integer, nullable=False, default=1)
    num_children = Column(Integer, nullable=False, default=0)

    status = Column(
        Enum(
            WaitlistStatusEnum,
            name="waitlist_status_enum",
            create_constraint=True,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
        default=WaitlistStatusEnum.WAITING,
    )

    priority = Column(Integer, nullable=False, default=100)
    notes = Column(Text, nullable=True)
    contact_phone = Column(String(50), nullable=True)

    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    promoted_at = Column(DateTime, nullable=True)
    expired_at = Column(DateTime, nullable=True)

    guest = relationship("Guest", lazy="joined")
    category = relationship("RoomCategory", lazy="joined")
    promoted_reservation = relationship("Reservation", lazy="select")

    __table_args__ = (
        CheckConstraint("check_out_date > check_in_date", name="ck_waitlist_dates"),
        CheckConstraint("num_adults > 0", name="ck_waitlist_adults_positive"),
        CheckConstraint("priority >= 0", name="ck_waitlist_priority_nonneg"),
        Index("ix_waitlist_hotel_status", "hotel_id", "status"),
        Index("ix_waitlist_hotel_category_dates", "hotel_id", "category_id", "check_in_date", "check_out_date"),
    )

    def __repr__(self) -> str:
        return (
            f"<WaitlistEntry(id={self.id}, hotel={self.hotel_id}, guest={self.guest_id}, "
            f"category={self.category_id}, status={self.status})>"
        )
