"""Shared, non-tenant-scoped cache of public DolarAPI market quotes."""

from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)

from app.database import Base


class FxRateCache(Base):
    """Latest accepted DolarAPI quote, shared because the source data is public.

    This table contains no hotel or guest data. ``observed_at`` is when the PMS
    received the provider response; ``provider_updated_at`` is retained only as
    market-data provenance because a valid weekend response may repeat Friday's
    market timestamp.
    """

    __tablename__ = "fx_rate_cache"

    id = Column(Integer, primary_key=True, autoincrement=True)
    currency = Column(String(3), nullable=False)
    rate_type = Column(String(30), nullable=False)
    provider_market = Column(String(30), nullable=False)
    name = Column(String(120), nullable=True)
    buy = Column(Numeric(20, 8), nullable=False)
    sell = Column(Numeric(20, 8), nullable=False)
    provider_updated_at = Column(DateTime(timezone=True), nullable=True)
    observed_at = Column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    is_derived = Column(Boolean, nullable=False, default=False, server_default="false")
    source_quotes = Column(JSON, nullable=True)
    cache_source = Column(
        String(30), nullable=False, default="on_demand", server_default="on_demand"
    )

    __table_args__ = (
        UniqueConstraint(
            "currency", "rate_type", name="uq_fx_rate_cache_currency_type"
        ),
        Index("ix_fx_rate_cache_observed_at", "observed_at"),
    )
