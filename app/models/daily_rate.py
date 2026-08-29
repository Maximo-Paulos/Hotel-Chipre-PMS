"""
V72 §8.5 — Per-day pricing models.

DailyRate: explicit price for a (hotel, category, date) triplet.
PricePeriod: named date-range for bulk rate loading (materialised into DailyRate rows
             via apply_price_period in pricing_service).
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)

from app.database import Base


class DailyRate(Base):
    """Explicit nightly price for a specific category and date."""

    __tablename__ = "daily_rates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(
        Integer, ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False
    )
    category_id = Column(
        Integer, ForeignKey("room_categories.id", ondelete="CASCADE"), nullable=False
    )
    date = Column(Date, nullable=False)
    price = Column(Float, nullable=False)  # base price for that night

    # Optional per-method overrides (if None, falls back to `price`)
    price_cash = Column(Float, nullable=True)
    price_transfer = Column(Float, nullable=True)
    price_mercadopago = Column(Float, nullable=True)
    price_paypal = Column(Float, nullable=True)
    price_credit_card = Column(Float, nullable=True)

    created_by_user_id = Column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        UniqueConstraint("hotel_id", "category_id", "date", name="uq_daily_rate"),
    )

    def __repr__(self) -> str:
        return f"<DailyRate hotel={self.hotel_id} category={self.category_id} date={self.date} price={self.price}>"


class PricePeriod(Base):
    """Named date-range season/period for bulk rate loading.

    Higher ``priority`` wins when periods overlap.
    Rows are materialised into ``daily_rates`` via
    ``pricing_service.apply_price_period``.
    """

    __tablename__ = "price_periods"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(
        Integer, ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False
    )
    category_id = Column(
        Integer, ForeignKey("room_categories.id", ondelete="CASCADE"), nullable=False
    )
    name = Column(String(100), nullable=False)  # e.g. "Temporada alta 2026"
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    price_per_night = Column(Float, nullable=False)
    # Legacy category-pricing rows are folded into these optional seasonal
    # overrides by the retirement migration. They are also useful for future
    # per-method seasonal prices without introducing another pricing layer.
    price_cash = Column(Float, nullable=True)
    price_transfer = Column(Float, nullable=True)
    price_mercadopago = Column(Float, nullable=True)
    price_paypal = Column(Float, nullable=True)
    price_credit_card = Column(Float, nullable=True)
    price_debit_card = Column(Float, nullable=True)
    price_booking = Column(Float, nullable=True)
    price_expedia = Column(Float, nullable=True)
    priority = Column(Integer, nullable=False, default=0)  # higher wins on overlap
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    deleted_at = Column(DateTime, nullable=True)
    deleted_by_user_id = Column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    __table_args__ = (
        Index("ix_price_period_hotel_cat", "hotel_id", "category_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<PricePeriod hotel={self.hotel_id} category={self.category_id} "
            f"name={self.name!r} {self.start_date}–{self.end_date}>"
        )
