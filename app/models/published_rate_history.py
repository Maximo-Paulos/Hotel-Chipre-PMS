"""Auditable facts for category rates that were explicitly published."""
from datetime import UTC, datetime

from sqlalchemy import (
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)

from app.database import Base


class PublishedRateHistory(Base):
    """One confirmed base rate per category and stay date.

    USD values are populated only when the rate currency is USD or a fresh,
    hotel-selected FX snapshot was available at publication time.
    """

    __tablename__ = "published_rate_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(
        Integer, ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False
    )
    category_id = Column(Integer, nullable=False)
    source_draft_id = Column(Integer, nullable=False)
    rate_date = Column(Date, nullable=False)
    comparable_season_key = Column(String(80), nullable=True)
    published_amount = Column(Numeric(12, 2), nullable=False)
    currency_code = Column(String(3), nullable=False)
    usd_amount = Column(Numeric(12, 4), nullable=True)
    fx_snapshot_id = Column(Integer, nullable=True)
    fx_market = Column(String(20), nullable=True)
    fx_side = Column(String(10), nullable=True)
    ars_per_usd = Column(Numeric(20, 8), nullable=True)
    rate_source = Column(String(16), nullable=False)
    captured_at = Column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    __table_args__ = (
        CheckConstraint("currency_code = upper(currency_code)", name="ck_published_rate_history_currency_upper"),
        CheckConstraint(
            "rate_source IN ('daily_rates', 'price_period')",
            name="ck_published_rate_history_source",
        ),
        CheckConstraint("published_amount >= 0", name="ck_published_rate_history_amount_nonnegative"),
        CheckConstraint(
            "usd_amount IS NULL OR usd_amount >= 0",
            name="ck_published_rate_history_usd_nonnegative",
        ),
        ForeignKeyConstraint(
            ["hotel_id", "category_id"],
            ["room_categories.hotel_id", "room_categories.id"],
            name="fk_published_rate_history_hotel_category",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "hotel_id", "source_draft_id", "rate_date",
            name="uq_published_rate_history_source_date",
        ),
        Index(
            "ix_published_rate_history_comparable",
            "hotel_id", "category_id", "comparable_season_key", "rate_date",
        ),
    )
