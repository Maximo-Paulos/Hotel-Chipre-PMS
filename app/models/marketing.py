"""
Public marketing surfaces: the pricing the landing page shows, and the
early-access leads it captures.

Both tables are written from the master-admin console and read by unauthenticated
endpoints, so they deliberately live outside any hotel's tenant scope -- there is
no hotel_id here and there must not be one.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Index, Integer, Numeric, String, Text

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class MarketingPricingPlan(Base):
    """A plan card as the public site renders it.

    `price_amount` is nullable on purpose: until the owner sets a number from
    the master-admin console the site shows "Consultar" rather than inventing
    one. Money is Numeric, never Float.
    """

    __tablename__ = "marketing_pricing_plans"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(40), nullable=False, unique=True, index=True)
    name = Column(String(80), nullable=False)
    is_public = Column(Boolean, nullable=False, default=True)
    sort_order = Column(Integer, nullable=False, default=0)

    price_amount = Column(Numeric(12, 2), nullable=True)
    currency = Column(String(3), nullable=True)
    billing_period = Column(String(20), nullable=False, default="month")

    headline = Column(String(160), nullable=True)
    description = Column(Text, nullable=True)
    features_json = Column(Text, nullable=True)

    room_limit = Column(Integer, nullable=True)
    staff_limit = Column(Integer, nullable=True)

    cta_label = Column(String(60), nullable=True)
    cta_kind = Column(String(20), nullable=False, default="early_access")
    highlight = Column(Boolean, nullable=False, default=False)

    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)

    __table_args__ = (Index("ix_marketing_pricing_plans_sort_order", "sort_order"),)


class MarketingLead(Base):
    """Someone who asked for access from the public site.

    Email is unique so a repeat submission updates the existing row instead of
    erroring -- the endpoint must not let an anonymous caller discover who has
    already signed up.
    """

    __tablename__ = "marketing_leads"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(320), nullable=False, unique=True, index=True)
    name = Column(String(120), nullable=True)
    hotel_name = Column(String(160), nullable=True)
    rooms_estimate = Column(Integer, nullable=True)
    city = Column(String(120), nullable=True)
    phone = Column(String(40), nullable=True)

    source = Column(String(60), nullable=False, default="landing")
    utm_json = Column(Text, nullable=True)
    # Hashed, never stored in the clear: it is only here for abuse triage.
    ip_hash = Column(String(64), nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)

    __table_args__ = (
        Index("ix_marketing_leads_created_at", "created_at"),
        Index("ix_marketing_leads_updated_at", "updated_at"),
    )
