"""
Laundry operations models.
"""
from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


class LaundryBatch(Base):
    __tablename__ = "laundry_batches"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", name="fk_laundry_batches_hotel_id"), nullable=False)
    batch_code = Column(String(50), nullable=False)
    status = Column(String(20), nullable=False, server_default="collected")
    sent_at = Column(DateTime, nullable=True)
    received_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL", name="fk_laundry_batches_created_by_user_id"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    items = relationship("LaundryItem", back_populates="batch", cascade="all, delete-orphan", lazy="selectin")

    __table_args__ = (
        CheckConstraint("status IN ('collected', 'sent', 'received', 'closed')", name="ck_laundry_batches_status_valid"),
        UniqueConstraint("hotel_id", "batch_code", name="uq_laundry_batches_hotel_batch_code"),
        Index("ix_laundry_batches_hotel_id", "hotel_id"),
    )


class LaundryItem(Base):
    __tablename__ = "laundry_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", name="fk_laundry_items_hotel_id"), nullable=False)
    batch_id = Column(Integer, ForeignKey("laundry_batches.id", ondelete="CASCADE", name="fk_laundry_items_batch_id"), nullable=False)
    item_type = Column(String(100), nullable=False)
    quantity = Column(Integer, nullable=False)
    room_id = Column(Integer, ForeignKey("rooms.id", ondelete="SET NULL", name="fk_laundry_items_room_id"), nullable=True)

    batch = relationship("LaundryBatch", back_populates="items", lazy="joined")

    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_laundry_items_quantity_positive"),
        Index("ix_laundry_items_hotel_id", "hotel_id"),
    )
