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


class StockItem(Base):
    __tablename__ = "stock_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", name="fk_stock_items_hotel_id"), nullable=False)
    name = Column(String(150), nullable=False)
    sku = Column(String(80), nullable=True)
    unit = Column(String(40), nullable=False)
    min_quantity = Column(Numeric(12, 2), nullable=True)
    active = Column(Boolean, nullable=False, server_default="1")
    # "supply" (bolsas, detergentes, jabon -- StockPage) vs "linen" (ropa
    # blanca administrada desde LaundryPage/laundry_vendor_prices). Same
    # table on purpose (both are still stock items with movements/locations),
    # separated only by which screen lists/creates them -- see
    # app/api/stock.py list_items(kind=) and migration
    # 20260727_stock_item_kind_and_soft_delete_unique_fix.
    kind = Column(String(20), nullable=False, server_default="supply")
    deleted_at = Column(DateTime, nullable=True)
    deleted_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    movements = relationship("StockMovement", back_populates="item", lazy="selectin")

    __table_args__ = (
        CheckConstraint("kind IN ('supply', 'linen')", name="ck_stock_items_kind_valid"),
        # Partial (not plain) unique index: a soft-deleted item must not keep
        # blocking the name forever -- otherwise "delete a discontinued
        # product, then add its replacement under the same name" (the
        # owner's exact reported use case) fails with an unhandled 500 on
        # the *create* call, which looks indistinguishable from "delete is
        # broken". See migration 20260727_stock_item_kind_and_soft_delete_unique_fix.
        Index(
            "uq_stock_items_hotel_name_active",
            "hotel_id",
            "name",
            unique=True,
            sqlite_where=text("deleted_at IS NULL"),
            postgresql_where=text("deleted_at IS NULL"),
        ),
        UniqueConstraint("hotel_id", "id", name="uq_stock_items_hotel_id_id"),
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
        # Same soft-delete-aware uniqueness fix as StockItem above.
        Index(
            "uq_stock_locations_hotel_name_active",
            "hotel_id",
            "name",
            unique=True,
            sqlite_where=text("deleted_at IS NULL"),
            postgresql_where=text("deleted_at IS NULL"),
        ),
        UniqueConstraint("hotel_id", "id", name="uq_stock_locations_hotel_id_id"),
        Index("ix_stock_locations_hotel_id", "hotel_id"),
    )


class StockMovement(Base):
    __tablename__ = "stock_movements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", name="fk_stock_movements_hotel_id"), nullable=False)
    item_id = Column(Integer, nullable=False)
    location_id = Column(Integer, nullable=True)
    movement_type = Column(String(20), nullable=False)
    quantity = Column(Numeric(12, 2), nullable=False)
    reason = Column(Text, nullable=True)
    reservation_id = Column(Integer, nullable=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL", name="fk_stock_movements_created_by_user_id"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    item = relationship("StockItem", back_populates="movements", lazy="joined")
    location = relationship("StockLocation", back_populates="movements", lazy="joined")

    __table_args__ = (
        CheckConstraint(
            "movement_type IN ('in', 'out', 'adjustment', 'adjustment_out')",
            name="ck_stock_movements_type_valid",
        ),
        CheckConstraint("quantity > 0", name="ck_stock_movements_quantity_positive"),
        ForeignKeyConstraint(
            ["hotel_id", "item_id"], ["stock_items.hotel_id", "stock_items.id"],
            name="fk_stock_movements_hotel_item", ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["hotel_id", "location_id"], ["stock_locations.hotel_id", "stock_locations.id"],
            name="fk_stock_movements_hotel_location",
        ),
        ForeignKeyConstraint(
            ["hotel_id", "reservation_id"], ["reservations.hotel_id", "reservations.id"],
            name="fk_stock_movements_hotel_reservation",
        ),
        Index("ix_stock_movements_hotel_id", "hotel_id"),
    )
