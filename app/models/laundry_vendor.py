"""
Laundry vendor, pricing and remito (delivery note) models.

An outsourced laundry ("vendor") gets its own StockLocation, so a remito is
just a transfer of StockMovement pairs between the hotel's "clean" location
and the vendor's location -- see app/services/laundry_vendor_service.py. This
is deliberately separate from the legacy app/models/laundry.py
LaundryBatch/LaundryItem models, which stay in the code as read-only history
(see memory checkpoint 20260725-235929: no open batches in production).

Cross-table references use composite (hotel_id, id) foreign keys, matching
the tenant-hardening convention already used by StockMovement (see
app/models/stock.py) and enforced by tests/test_tenant_rls_contract.py: a
scalar FK across two hotel-scoped tables can point at a row belonging to a
different hotel, a composite FK cannot.
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
)
from sqlalchemy.orm import relationship

from app.database import Base


class LaundryVendor(Base):
    __tablename__ = "laundry_vendors"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", name="fk_laundry_vendors_hotel_id"), nullable=False)
    name = Column(String(150), nullable=False)
    stock_location_id = Column(Integer, nullable=False)
    contact_phone = Column(String(40), nullable=True)
    contact_email = Column(String(150), nullable=True)
    active = Column(Boolean, nullable=False, server_default="1")
    deleted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    stock_location = relationship(
        "StockLocation",
        primaryjoin="foreign(LaundryVendor.stock_location_id) == StockLocation.id",
        viewonly=True,
        lazy="joined",
    )
    prices = relationship(
        "LaundryVendorPrice", back_populates="vendor", cascade="all, delete-orphan", lazy="selectin"
    )

    __table_args__ = (
        UniqueConstraint("hotel_id", "name", name="uq_laundry_vendors_hotel_name"),
        UniqueConstraint("hotel_id", "id", name="uq_laundry_vendors_hotel_id_id"),
        ForeignKeyConstraint(
            ["hotel_id", "stock_location_id"],
            ["stock_locations.hotel_id", "stock_locations.id"],
            name="fk_laundry_vendors_hotel_stock_location",
        ),
        Index("ix_laundry_vendors_hotel_id", "hotel_id"),
    )


class LaundryVendorPrice(Base):
    __tablename__ = "laundry_vendor_prices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", name="fk_laundry_vendor_prices_hotel_id"), nullable=False)
    vendor_id = Column(Integer, nullable=False)
    stock_item_id = Column(Integer, nullable=False)
    unit_price = Column(Numeric(12, 2), nullable=False)
    currency_code = Column(String(3), nullable=False, server_default="ARS")
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    vendor = relationship("LaundryVendor", back_populates="prices")

    __table_args__ = (
        UniqueConstraint("vendor_id", "stock_item_id", name="uq_laundry_vendor_prices_vendor_item"),
        CheckConstraint("unit_price >= 0", name="ck_laundry_vendor_prices_unit_price_non_negative"),
        ForeignKeyConstraint(
            ["hotel_id", "vendor_id"],
            ["laundry_vendors.hotel_id", "laundry_vendors.id"],
            name="fk_laundry_vendor_prices_hotel_vendor",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["hotel_id", "stock_item_id"],
            ["stock_items.hotel_id", "stock_items.id"],
            name="fk_laundry_vendor_prices_hotel_stock_item",
        ),
        Index("ix_laundry_vendor_prices_hotel_id", "hotel_id"),
    )


class LaundryRemito(Base):
    __tablename__ = "laundry_remitos"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", name="fk_laundry_remitos_hotel_id"), nullable=False)
    vendor_id = Column(Integer, nullable=False)
    direction = Column(String(10), nullable=False)
    # The number the laundry writes on its own paper slip -- not globally
    # unique, can repeat across different vendors (see plan D1).
    remito_number = Column(String(60), nullable=False)
    remito_date = Column(DateTime, nullable=False)
    notes = Column(Text, nullable=True)
    created_by_user_id = Column(
        Integer, ForeignKey("users.id", ondelete="SET NULL", name="fk_laundry_remitos_created_by_user_id"), nullable=True
    )
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    vendor = relationship(
        "LaundryVendor",
        primaryjoin="foreign(LaundryRemito.vendor_id) == LaundryVendor.id",
        viewonly=True,
        lazy="joined",
    )
    lines = relationship(
        "LaundryRemitoLine", back_populates="remito", cascade="all, delete-orphan", lazy="selectin"
    )

    __table_args__ = (
        CheckConstraint("direction IN ('outbound', 'inbound')", name="ck_laundry_remitos_direction_valid"),
        UniqueConstraint("hotel_id", "id", name="uq_laundry_remitos_hotel_id_id"),
        ForeignKeyConstraint(
            ["hotel_id", "vendor_id"],
            ["laundry_vendors.hotel_id", "laundry_vendors.id"],
            name="fk_laundry_remitos_hotel_vendor",
        ),
        Index("ix_laundry_remitos_hotel_id", "hotel_id"),
        Index("ix_laundry_remitos_vendor_id", "vendor_id"),
    )


class LaundryRemitoLine(Base):
    __tablename__ = "laundry_remito_lines"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", name="fk_laundry_remito_lines_hotel_id"), nullable=False)
    remito_id = Column(Integer, nullable=False)
    stock_item_id = Column(Integer, nullable=False)
    quantity = Column(Numeric(12, 2), nullable=False)
    # Copied from LaundryVendorPrice at creation time so historical cost does
    # not change if the vendor's price is updated later. Null when no price
    # was configured for this (vendor, item) yet -- the API surfaces a
    # warning for that case instead of blocking remito creation.
    unit_price_snapshot = Column(Numeric(12, 2), nullable=True)

    remito = relationship("LaundryRemito", back_populates="lines")
    stock_item = relationship(
        "StockItem",
        primaryjoin="foreign(LaundryRemitoLine.stock_item_id) == StockItem.id",
        viewonly=True,
        lazy="joined",
    )

    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_laundry_remito_lines_quantity_positive"),
        ForeignKeyConstraint(
            ["hotel_id", "remito_id"],
            ["laundry_remitos.hotel_id", "laundry_remitos.id"],
            name="fk_laundry_remito_lines_hotel_remito",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["hotel_id", "stock_item_id"],
            ["stock_items.hotel_id", "stock_items.id"],
            name="fk_laundry_remito_lines_hotel_stock_item",
        ),
        Index("ix_laundry_remito_lines_hotel_id", "hotel_id"),
        Index("ix_laundry_remito_lines_remito_id", "remito_id"),
    )
