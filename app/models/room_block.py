"""
RoomBlock — date-ranged blocks on a specific room (v72 §14).
Blocks affect availability: a blocked room cannot be assigned or reserved.
Releasing a block triggers reoptimization of pending allocations.
"""
from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, Column, Date, DateTime, ForeignKey, Index, Integer, String, Text,
    CheckConstraint, Enum,
)
from sqlalchemy.orm import relationship

from app.database import Base


class RoomBlockReasonEnum(str, enum.Enum):
    MAINTENANCE = "maintenance"       # Scheduled maintenance
    DEEP_CLEANING = "deep_cleaning"   # Deep cleaning / refurbishment
    OWNER_USE = "owner_use"           # Owner/partner personal use
    VIP_HOLD = "vip_hold"             # Held for VIP guest pending confirmation
    OVERBOOKING_BUFFER = "overbooking_buffer"  # Soft buffer for overbooking mgmt
    OTHER = "other"


class RoomBlock(Base):
    """
    Date-ranged block on a room. NULL ends_at means indefinite.
    resolved_at populated when block is lifted; triggers allocation reoptimization.
    """
    __tablename__ = "room_blocks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False)
    room_id = Column(Integer, ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False)

    reason_code = Column(
        Enum(
            RoomBlockReasonEnum,
            name="room_block_reason_enum",
            create_constraint=True,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
        default=RoomBlockReasonEnum.OTHER,
    )
    reason_note = Column(String(500), nullable=True)

    starts_at = Column(Date, nullable=False)
    ends_at = Column(Date, nullable=True)       # NULL = indefinite
    is_indefinite = Column(Boolean, nullable=False, default=False)

    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    resolved_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    resolved_at = Column(DateTime, nullable=True)   # when the block was lifted

    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime, nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    room = relationship("Room", lazy="joined")

    __table_args__ = (
        CheckConstraint(
            "ends_at IS NULL OR ends_at > starts_at",
            name="ck_room_block_dates",
        ),
        CheckConstraint(
            # Cross-dialect: SQLite stores booleans as integers; PG rejects boolean = integer
            "(is_indefinite AND ends_at IS NULL) OR (NOT is_indefinite)",
            name="ck_room_block_indefinite_consistency",
        ),
        Index("ix_room_blocks_hotel_room", "hotel_id", "room_id"),
        Index("ix_room_blocks_hotel_dates", "hotel_id", "starts_at", "ends_at"),
    )

    @property
    def is_active(self) -> bool:
        return self.resolved_at is None

    def __repr__(self) -> str:
        return (
            f"<RoomBlock(id={self.id}, room_id={self.room_id}, "
            f"starts_at={self.starts_at}, ends_at={self.ends_at})>"
        )
