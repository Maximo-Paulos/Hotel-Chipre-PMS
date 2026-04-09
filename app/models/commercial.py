"""
Commercial domain models for the next reservation/OTA foundation.

These tables separate what the hotel sells from the physical inventory used
to fulfill the stay. This makes later OTA mappings, pricing rules, taxes,
currency logic and allocation strategies much easier to model cleanly.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


class SellableProduct(Base):
    __tablename__ = "sellable_products"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False)
    primary_room_category_id = Column(Integer, ForeignKey("room_categories.id"), nullable=True)
    code = Column(String(50), nullable=False)
    name = Column(String(150), nullable=False)
    description = Column(Text, nullable=True)
    min_occupancy = Column(Integer, nullable=False, default=1)
    max_occupancy = Column(Integer, nullable=False, default=1)
    bathroom_type = Column(String(40), nullable=True)
    board_type = Column(String(40), nullable=True)
    gender_policy = Column(String(40), nullable=True)
    accessibility_required = Column(Boolean, nullable=False, default=False)
    is_active = Column(Boolean, nullable=False, default=True)
    sort_order = Column(Integer, nullable=False, default=0)
    metadata_json = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    primary_room_category = relationship("RoomCategory", lazy="joined")
    compatibilities = relationship(
        "ProductRoomCompatibility",
        back_populates="sellable_product",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    rate_plans = relationship("RatePlan", back_populates="sellable_product", lazy="selectin")

    __table_args__ = (
        CheckConstraint("min_occupancy > 0", name="ck_sellable_product_min_occupancy_positive"),
        CheckConstraint("max_occupancy >= min_occupancy", name="ck_sellable_product_occupancy_range"),
        UniqueConstraint("hotel_id", "code", name="uq_sellable_product_code_hotel"),
        UniqueConstraint("hotel_id", "name", name="uq_sellable_product_name_hotel"),
        Index("ix_sellable_products_hotel_id", "hotel_id"),
    )


class ProductRoomCompatibility(Base):
    __tablename__ = "product_room_compatibility"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False)
    sellable_product_id = Column(Integer, ForeignKey("sellable_products.id", ondelete="CASCADE"), nullable=False)
    room_category_id = Column(Integer, ForeignKey("room_categories.id", ondelete="CASCADE"), nullable=False)
    compatibility_kind = Column(String(30), nullable=False, default="exact")
    priority = Column(Integer, nullable=False, default=100)
    allows_auto_assignment = Column(Boolean, nullable=False, default=True)
    price_adjustment_type = Column(String(30), nullable=True)
    price_adjustment_value = Column(Float, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    sellable_product = relationship("SellableProduct", back_populates="compatibilities", lazy="joined")
    room_category = relationship("RoomCategory", lazy="joined")

    __table_args__ = (
        UniqueConstraint(
            "hotel_id",
            "sellable_product_id",
            "room_category_id",
            name="uq_product_room_compatibility_hotel",
        ),
        Index("ix_product_room_compatibility_hotel_id", "hotel_id"),
        Index("ix_product_room_compatibility_sellable_product_id", "sellable_product_id"),
    )


class RatePlan(Base):
    __tablename__ = "rate_plans"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False)
    sellable_product_id = Column(Integer, ForeignKey("sellable_products.id", ondelete="CASCADE"), nullable=False)
    code = Column(String(50), nullable=False)
    name = Column(String(150), nullable=False)
    pricing_model = Column(String(50), nullable=False, default="fixed_per_night")
    cancellation_model = Column(String(50), nullable=False, default="flexible")
    currency_code = Column(String(3), nullable=False, default="ARS")
    is_refundable = Column(Boolean, nullable=False, default=True)
    is_active = Column(Boolean, nullable=False, default=True)
    min_nights_default = Column(Integer, nullable=False, default=1)
    max_nights_default = Column(Integer, nullable=True)
    free_cancellation_hours = Column(Integer, nullable=False, default=0)
    cancellation_penalty_type = Column(String(30), nullable=True)
    cancellation_penalty_value = Column(Float, nullable=True)
    default_commission_pct = Column(Float, nullable=True)
    default_markup_pct = Column(Float, nullable=True)
    metadata_json = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    sellable_product = relationship("SellableProduct", back_populates="rate_plans", lazy="joined")
    prices = relationship("RatePlanPrice", back_populates="rate_plan", lazy="selectin", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("min_nights_default > 0", name="ck_rate_plan_min_nights_positive"),
        CheckConstraint(
            "max_nights_default IS NULL OR max_nights_default >= min_nights_default",
            name="ck_rate_plan_max_nights_range",
        ),
        UniqueConstraint("hotel_id", "code", name="uq_rate_plan_code_hotel"),
        Index("ix_rate_plans_hotel_id", "hotel_id"),
        Index("ix_rate_plans_sellable_product_id", "sellable_product_id"),
    )


class RatePlanPrice(Base):
    __tablename__ = "rate_plan_prices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False)
    rate_plan_id = Column(Integer, ForeignKey("rate_plans.id", ondelete="CASCADE"), nullable=False)
    sales_channel_code = Column(String(50), nullable=True)
    occupancy = Column(Integer, nullable=True)
    currency_code = Column(String(3), nullable=False, default="ARS")
    base_amount = Column(Float, nullable=False)
    tax_inclusive = Column(Boolean, nullable=False, default=True)
    valid_from = Column(Date, nullable=True)
    valid_to = Column(Date, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    rate_plan = relationship("RatePlan", back_populates="prices", lazy="joined")

    __table_args__ = (
        CheckConstraint("base_amount >= 0", name="ck_rate_plan_prices_base_amount_positive"),
        CheckConstraint("occupancy IS NULL OR occupancy > 0", name="ck_rate_plan_prices_occupancy_positive"),
        CheckConstraint(
            "valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from",
            name="ck_rate_plan_prices_valid_range",
        ),
        Index("ix_rate_plan_prices_hotel_id", "hotel_id"),
        Index("ix_rate_plan_prices_rate_plan_id", "rate_plan_id"),
    )


class TaxPolicy(Base):
    __tablename__ = "tax_policies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False)
    code = Column(String(50), nullable=False)
    name = Column(String(150), nullable=False)
    taxes_included = Column(Boolean, nullable=False, default=True)
    apply_vat_by_default = Column(Boolean, nullable=False, default=True)
    vat_rate = Column(Float, nullable=True)
    foreign_guest_tax_exempt = Column(Boolean, nullable=False, default=False)
    is_active = Column(Boolean, nullable=False, default=True)
    metadata_json = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    rules = relationship("TaxRule", back_populates="tax_policy", lazy="selectin", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("hotel_id", "code", name="uq_tax_policy_code_hotel"),
        Index("ix_tax_policies_hotel_id", "hotel_id"),
    )


class TaxRule(Base):
    __tablename__ = "tax_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False)
    tax_policy_id = Column(Integer, ForeignKey("tax_policies.id", ondelete="CASCADE"), nullable=False)
    channel_code = Column(String(50), nullable=True)
    guest_scope = Column(String(30), nullable=False, default="all")
    tax_code = Column(String(50), nullable=False)
    tax_name = Column(String(150), nullable=False)
    tax_type = Column(String(30), nullable=False, default="percentage")
    amount = Column(Float, nullable=False, default=0.0)
    currency_code = Column(String(3), nullable=True)
    priority = Column(Integer, nullable=False, default=100)
    applies_when_json = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    tax_policy = relationship("TaxPolicy", back_populates="rules", lazy="joined")

    __table_args__ = (
        UniqueConstraint("hotel_id", "tax_policy_id", "tax_code", name="uq_tax_rule_code_hotel_policy"),
        Index("ix_tax_rules_hotel_id", "hotel_id"),
        Index("ix_tax_rules_tax_policy_id", "tax_policy_id"),
    )


class FxPolicy(Base):
    __tablename__ = "fx_policies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False)
    code = Column(String(50), nullable=False)
    name = Column(String(150), nullable=False)
    base_currency = Column(String(3), nullable=False, default="ARS")
    preferred_source = Column(String(50), nullable=False, default="official")
    preferred_side = Column(String(20), nullable=False, default="sell")
    spread_pct = Column(Float, nullable=False, default=0.0)
    rounding_mode = Column(String(30), nullable=False, default="half_up")
    is_active = Column(Boolean, nullable=False, default=True)
    metadata_json = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        UniqueConstraint("hotel_id", "code", name="uq_fx_policy_code_hotel"),
        Index("ix_fx_policies_hotel_id", "hotel_id"),
    )
