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
    # ARS (same currency convention as the rest of Stock -- unlike laundry's
    # per-vendor LaundryVendorPrice, general supplies have a single cost, not
    # a price negotiated per counterparty). Nullable: most items never need
    # it tracked.
    unit_cost = Column(Numeric(12, 2), nullable=True)
    deleted_at = Column(DateTime, nullable=True)
    deleted_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    # Incremented while the item row is locked for every successful ledger
    # movement. A physical count records this version and must be repeated if
    # any movement occurs before an authorized person confirms the count.
    movement_version = Column(Integer, nullable=False, default=0, server_default="0")

    movements = relationship("StockMovement", back_populates="item", lazy="selectin")

    __table_args__ = (
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
    # Retried "register movement" requests (e.g. a flaky connection resends
    # the same POST) send the same client-generated key so the second attempt
    # returns the first attempt's row instead of double-counting stock. NULL
    # for movements that don't opt in -- NULLs never collide with each other
    # or with a real key in a unique constraint (same convention as
    # payment_links.idempotency_key, see 20260812_external_effect_payment_links).
    idempotency_key = Column(String(100), nullable=True)
    # Both ledger rows for one physical location-to-location transfer share
    # this opaque reference so the pair is auditable and excluded from
    # consumption totals. It is nullable for ordinary stock movements.
    transfer_reference = Column(String(36), nullable=True)

    item = relationship("StockItem", back_populates="movements", lazy="joined")
    location = relationship("StockLocation", back_populates="movements", lazy="joined")

    __table_args__ = (
        CheckConstraint(
            "movement_type IN ('in', 'out', 'adjustment', 'adjustment_out')",
            name="ck_stock_movements_type_valid",
        ),
        CheckConstraint("quantity > 0", name="ck_stock_movements_quantity_positive"),
        CheckConstraint(
            "transfer_reference IS NULL OR movement_type IN ('in', 'out')",
            name="ck_stock_movements_transfer_direction_valid",
        ),
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
        UniqueConstraint(
            "hotel_id", "idempotency_key", name="uq_stock_movement_idempotency_per_hotel"
        ),
        Index(
            "uq_stock_movement_transfer_direction",
            "hotel_id",
            "transfer_reference",
            "movement_type",
            unique=True,
            sqlite_where=text("transfer_reference IS NOT NULL"),
            postgresql_where=text("transfer_reference IS NOT NULL"),
        ),
        Index("ix_stock_movements_hotel_id", "hotel_id"),
    )


class StockCountSession(Base):
    """Hotel-scoped physical count awaiting authorized confirmation."""

    __tablename__ = "stock_count_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False)
    status = Column(String(20), nullable=False, default="open", server_default="open")
    reason = Column(Text, nullable=False)
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    counter_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    confirmed_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    confirmation_reason = Column(Text, nullable=True)
    confirmed_at = Column(DateTime, nullable=True)
    self_approved = Column(Boolean, nullable=False, default=False, server_default=text("false"))
    cancelled_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    cancellation_reason = Column(Text, nullable=True)
    cancelled_at = Column(DateTime, nullable=True)

    counts = relationship(
        "StockCountLine",
        back_populates="session",
        cascade="all, delete-orphan",
        lazy="select",
        order_by="StockCountLine.id",
        overlaps="item,location",
    )

    __table_args__ = (
        CheckConstraint("status IN ('open', 'confirmed', 'cancelled')", name="ck_stock_count_session_status"),
        UniqueConstraint("hotel_id", "id", name="uq_stock_count_sessions_hotel_id_id"),
        Index("ix_stock_count_sessions_hotel_created", "hotel_id", "created_at", "id"),
    )


class StockCountLine(Base):
    """One observed quantity for an item, either hotel-wide or by location."""

    __tablename__ = "stock_count_lines"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, nullable=False)
    session_id = Column(Integer, nullable=False)
    item_id = Column(Integer, nullable=False)
    location_id = Column(Integer, nullable=True)
    system_quantity_at_count = Column(Numeric(12, 2), nullable=False)
    counted_quantity = Column(Numeric(12, 2), nullable=False)
    movement_version = Column(Integer, nullable=False)
    counted_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    counted_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    applied_adjustment = Column(Numeric(12, 2), nullable=True)
    adjusted_at = Column(DateTime, nullable=True)

    session = relationship("StockCountSession", back_populates="counts", lazy="select", overlaps="item,location")
    item = relationship("StockItem", lazy="joined", overlaps="counts,session,location")
    location = relationship("StockLocation", lazy="joined", overlaps="counts,item,session")

    __table_args__ = (
        CheckConstraint("system_quantity_at_count >= 0", name="ck_stock_count_line_system_nonnegative"),
        CheckConstraint("counted_quantity >= 0", name="ck_stock_count_line_counted_nonnegative"),
        ForeignKeyConstraint(
            ["hotel_id", "session_id"],
            ["stock_count_sessions.hotel_id", "stock_count_sessions.id"],
            name="fk_stock_count_line_hotel_session",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["hotel_id", "item_id"],
            ["stock_items.hotel_id", "stock_items.id"],
            name="fk_stock_count_line_hotel_item",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["hotel_id", "location_id"],
            ["stock_locations.hotel_id", "stock_locations.id"],
            name="fk_stock_count_line_hotel_location",
            ondelete="RESTRICT",
        ),
        # NULL location_id means a whole-hotel count; the partial index keeps
        # it unique too, which ordinary nullable UNIQUE constraints do not do
        # on PostgreSQL or SQLite.
        UniqueConstraint(
            "hotel_id", "session_id", "item_id", "location_id",
            name="uq_stock_count_line_location",
        ),
        Index(
            "uq_stock_count_line_unlocated",
            "hotel_id", "session_id", "item_id",
            unique=True,
            sqlite_where=text("location_id IS NULL"),
            postgresql_where=text("location_id IS NULL"),
        ),
        Index("ix_stock_count_lines_hotel_session", "hotel_id", "session_id", "id"),
    )
