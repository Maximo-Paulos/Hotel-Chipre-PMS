"""
Stock and inventory movement models.
"""
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


class StockItem(Base):
    __tablename__ = "stock_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", name="fk_stock_items_hotel_id"), nullable=False)
    name = Column(String(150), nullable=False)
    sku = Column(String(80), nullable=True)
    unit = Column(String(40), nullable=False)
    min_quantity = Column(Numeric(12, 2), nullable=True)
    active = Column(Boolean, nullable=False, server_default="1")
    deleted_at = Column(DateTime, nullable=True)
    deleted_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    movements = relationship("StockMovement", back_populates="item", lazy="selectin")

    __table_args__ = (
        UniqueConstraint("hotel_id", "name", name="uq_stock_items_hotel_name"),
        Index("ix_stock_items_hotel_id", "hotel_id"),
    )


class StockLocation(Base):
    __tablename__ = "stock_locations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", name="fk_stock_locations_hotel_id"), nullable=False)
    name = Column(String(150), nullable=False)
    deleted_at = Column(DateTime, nullable=True)
    deleted_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    movements = relationship("StockMovement", back_populates="location", lazy="selectin")

    __table_args__ = (
        UniqueConstraint("hotel_id", "name", name="uq_stock_locations_hotel_name"),
        Index("ix_stock_locations_hotel_id", "hotel_id"),
    )


class StockMovement(Base):
    __tablename__ = "stock_movements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", name="fk_stock_movements_hotel_id"), nullable=False)
    item_id = Column(Integer, ForeignKey("stock_items.id", ondelete="CASCADE", name="fk_stock_movements_item_id"), nullable=False)
    location_id = Column(Integer, ForeignKey("stock_locations.id", ondelete="SET NULL", name="fk_stock_movements_location_id"), nullable=True)
    movement_type = Column(String(20), nullable=False)
    quantity = Column(Numeric(12, 2), nullable=False)
    reason = Column(Text, nullable=True)
    reservation_id = Column(Integer, ForeignKey("reservations.id", ondelete="SET NULL", name="fk_stock_movements_reservation_id"), nullable=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL", name="fk_stock_movements_created_by_user_id"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    item = relationship("StockItem", back_populates="movements", lazy="joined")
    location = relationship("StockLocation", back_populates="movements", lazy="joined")

    __table_args__ = (
        CheckConstraint("movement_type IN ('in', 'out', 'adjustment')", name="ck_stock_movements_type_valid"),
        CheckConstraint("quantity > 0", name="ck_stock_movements_quantity_positive"),
        Index("ix_stock_movements_hotel_id", "hotel_id"),
    )
