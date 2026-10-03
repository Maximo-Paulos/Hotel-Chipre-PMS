from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    JSON,
    String,
    text,
)

from app.database import Base


class RateChangeDraft(Base):
    """Auditable, tenant-scoped draft for daily rates or a price period."""

    __tablename__ = "rate_change_drafts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False)
    category_id = Column(Integer, nullable=False)
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    draft_type = Column(String(16), nullable=False, default="daily_rates")
    status = Column(String(16), nullable=False, default="draft")
    version = Column(Integer, nullable=False, default=1)
    changes = Column(JSON, nullable=False)
    period_operation = Column(JSON, nullable=True)
    impact = Column(JSON, nullable=False)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    confirmed_at = Column(DateTime, nullable=True)
    confirmed_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    cancelled_at = Column(DateTime, nullable=True)
    cancelled_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    __table_args__ = (
        ForeignKeyConstraint(
            ["hotel_id", "category_id"],
            ["room_categories.hotel_id", "room_categories.id"],
            name="fk_rate_change_drafts_hotel_category",
            ondelete="CASCADE",
        ),
        CheckConstraint("draft_type IN ('daily_rates', 'price_period')", name="ck_rate_change_drafts_type"),
        CheckConstraint("status IN ('draft', 'confirmed', 'cancelled')", name="ck_rate_change_drafts_status"),
        CheckConstraint("version > 0", name="ck_rate_change_drafts_version_positive"),
        Index("ix_rate_change_drafts_hotel_status_created", "hotel_id", "status", "created_at"),
        Index("ix_rate_change_drafts_hotel_category", "hotel_id", "category_id", "created_at"),
        Index(
            "uq_rate_change_drafts_one_open_per_category",
            "hotel_id",
            "category_id",
            unique=True,
            postgresql_where=text("status = 'draft'"),
            sqlite_where=text("status = 'draft'"),
        ),
    )
