"""
Linen (ropa blanca) inventory models -- physically separate tables from
app/models/stock.py's general-supplies tables (StockItem/StockLocation/
StockMovement), per the owner's explicit rejection of a shared
``StockItem.kind`` flag: "no son lo mismo, son totalmente separados...
dos tablas separadas, dos datos distintos."

Same shape as the stock tables (see app/services/linen_service.py for the
movement/balance primitives, mirroring stock_service.py without sharing a
table), used exclusively by the outsourced-laundry domain
(app/models/laundry_vendor.py, app/services/laundry_vendor_service.py).
"""
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import relationship

from app.database import Base


class LinenItem(Base):
    __tablename__ = "linen_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", name="fk_linen_items_hotel_id"), nullable=False)
    name = Column(String(150), nullable=False)
    unit = Column(String(40), nullable=False)
    min_quantity = Column(Numeric(12, 2), nullable=True)
    active = Column(Boolean, nullable=False, server_default="1")
    deleted_at = Column(DateTime, nullable=True)
    deleted_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    movements = relationship("LinenMovement", back_populates="item", lazy="selectin")

    __table_args__ = (
        # Soft-delete-aware uniqueness, same pattern as StockItem (see
        # migration 20260727_stock_item_kind_and_soft_delete_unique_fix):
        # deleting a linen type must not permanently reserve its name.
        Index(
            "uq_linen_items_hotel_name_active",
            "hotel_id",
            "name",
            unique=True,
            sqlite_where=text("deleted_at IS NULL"),
            postgresql_where=text("deleted_at IS NULL"),
        ),
        UniqueConstraint("hotel_id", "id", name="uq_linen_items_hotel_id_id"),
        Index("ix_linen_items_hotel_id", "hotel_id"),
    )


class LinenLocation(Base):
    __tablename__ = "linen_locations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", name="fk_linen_locations_hotel_id"), nullable=False)
    name = Column(String(150), nullable=False)
    deleted_at = Column(DateTime, nullable=True)
    deleted_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    movements = relationship("LinenMovement", back_populates="location", lazy="selectin")

    __table_args__ = (
        Index(
            "uq_linen_locations_hotel_name_active",
            "hotel_id",
            "name",
            unique=True,
            sqlite_where=text("deleted_at IS NULL"),
            postgresql_where=text("deleted_at IS NULL"),
        ),
        UniqueConstraint("hotel_id", "id", name="uq_linen_locations_hotel_id_id"),
        Index("ix_linen_locations_hotel_id", "hotel_id"),
    )


class LinenMovement(Base):
    __tablename__ = "linen_movements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", name="fk_linen_movements_hotel_id"), nullable=False)
    item_id = Column(Integer, nullable=False)
    location_id = Column(Integer, nullable=True)
    movement_type = Column(String(20), nullable=False)
    quantity = Column(Numeric(12, 2), nullable=False)
    reason = Column(Text, nullable=True)
    reservation_id = Column(Integer, nullable=True)
    created_by_user_id = Column(
        Integer, ForeignKey("users.id", ondelete="SET NULL", name="fk_linen_movements_created_by_user_id"), nullable=True
    )
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    item = relationship("LinenItem", back_populates="movements", lazy="joined")
    location = relationship("LinenLocation", back_populates="movements", lazy="joined")

    __table_args__ = (
        CheckConstraint(
            "movement_type IN ('in', 'out', 'adjustment', 'adjustment_out')",
            name="ck_linen_movements_type_valid",
        ),
        CheckConstraint("quantity > 0", name="ck_linen_movements_quantity_positive"),
        ForeignKeyConstraint(
            ["hotel_id", "item_id"], ["linen_items.hotel_id", "linen_items.id"],
            name="fk_linen_movements_hotel_item", ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["hotel_id", "location_id"], ["linen_locations.hotel_id", "linen_locations.id"],
            name="fk_linen_movements_hotel_location",
        ),
        ForeignKeyConstraint(
            ["hotel_id", "reservation_id"], ["reservations.hotel_id", "reservations.id"],
            name="fk_linen_movements_hotel_reservation",
        ),
        Index("ix_linen_movements_hotel_id", "hotel_id"),
    )
