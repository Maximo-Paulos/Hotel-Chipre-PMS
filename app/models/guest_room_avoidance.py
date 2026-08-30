"""Tenant-scoped room rejections recorded for an individual guest."""
from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Text,
    UniqueConstraint,
)

from app.database import Base


class GuestRoomAvoidanceStatusEnum(str, enum.Enum):
    ACTIVE = "active"
    RESOLVED = "resolved"


class GuestRoomAvoidance(Base):
    """A guest's active or resolved rejection of one physical room.

    ``RoomMoveEvent`` remains immutable audit history. This lifecycle record
    merely references the event that most recently opened (or re-opened) the
    rejection, so resolving it never rewrites the movement event.
    """

    __tablename__ = "guest_room_avoidance"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False)
    guest_id = Column(Integer, nullable=False)
    room_id = Column(Integer, nullable=False)
    status = Column(
        Enum(
            GuestRoomAvoidanceStatusEnum,
            name="guest_room_avoidance_status_enum",
            create_constraint=True,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
        default=GuestRoomAvoidanceStatusEnum.ACTIVE,
    )
    source_move_event_id = Column(
        Integer,
        ForeignKey("room_move_events.id", ondelete="SET NULL"),
        nullable=True,
    )
    reason = Column(Text, nullable=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    resolved_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    resolution_note = Column(Text, nullable=True)

    __table_args__ = (
        ForeignKeyConstraint(
            ["hotel_id", "guest_id"],
            ["guests.hotel_id", "guests.id"],
            name="fk_guest_room_avoidance_hotel_guest",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["hotel_id", "room_id"],
            ["rooms.hotel_id", "rooms.id"],
            name="fk_guest_room_avoidance_hotel_room",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "hotel_id",
            "guest_id",
            "room_id",
            name="uq_guest_room_avoidance_hotel_guest_room",
        ),
        Index("ix_guest_room_avoidance_hotel_guest_status", "hotel_id", "guest_id", "status"),
    )

    def __repr__(self) -> str:
        return (
            "<GuestRoomAvoidance("
            f"id={self.id}, guest_id={self.guest_id}, room_id={self.room_id}, status={self.status})>"
        )
