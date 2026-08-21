"""
Lightweight subscription tracking for enforcement and auditing (v2 tables).
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


def _utcnow():
    return datetime.now(timezone.utc)


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False, unique=True)
    plan = Column(String(20), nullable=False, default="starter")
    status = Column(String(20), nullable=False, default="active")
    trial_started_at = Column(DateTime(timezone=True), nullable=True)
    trial_end_at = Column(DateTime(timezone=True), nullable=True)
    current_period_end = Column(DateTime(timezone=True), nullable=True)
    grace_until = Column(DateTime(timezone=True), nullable=True)
    room_limit = Column(Integer, nullable=True)
    staff_limit = Column(Integer, nullable=True)
    can_write_cache = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)

    events = relationship("SubscriptionEvent", back_populates="subscription", cascade="all, delete-orphan")
    adjustments = relationship("SubscriptionAdjustment", back_populates="subscription", passive_deletes=True)

    __table_args__ = (
        UniqueConstraint("hotel_id", "id", name="uq_subscriptions_hotel_id_id"),
        CheckConstraint("plan in ('starter','pro','ultra')", name="ck_subscriptions_plan"),
        CheckConstraint("status in ('active','past_due','suspended','trialing','demo','comped')", name="ck_subscriptions_status"),
    )


class SubscriptionEvent(Base):
    __tablename__ = "subscription_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id", ondelete="CASCADE"), nullable=False)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False)
    event_type = Column(String(50), nullable=False)
    payload = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    subscription = relationship("Subscription", back_populates="events")

    __table_args__ = (
        Index("ix_subscription_events_subscription_id", "subscription_id"),
        Index("ix_subscription_events_hotel_id", "hotel_id"),
    )


class SubscriptionAdjustment(Base):
    """Immutable ledger entry for a subscription discount or override.

    This table records the commercial intent and audit context only. It does
    not calculate prices or charge a customer. There are deliberately no
    application update/delete paths, and the hotel/subscription foreign keys
    use RESTRICT so the evidence cannot disappear with a parent row.
    """

    __tablename__ = "subscription_adjustments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", ondelete="RESTRICT"), nullable=False)
    subscription_id = Column(Integer, nullable=False)
    adjustment_type = Column(String(30), nullable=False)
    plan_code = Column(String(20), nullable=True)
    amount = Column(Numeric(12, 2), nullable=True)
    duration_days = Column(Integer, nullable=True)
    reason = Column(Text, nullable=False)
    actor_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    actor_role = Column(String(50), nullable=True)
    valid_from = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    valid_until = Column(DateTime(timezone=True), nullable=True)
    idempotency_key = Column(String(100), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    subscription = relationship("Subscription", back_populates="adjustments")

    __table_args__ = (
        ForeignKeyConstraint(
            ["hotel_id", "subscription_id"],
            ["subscriptions.hotel_id", "subscriptions.id"],
            name="fk_subscription_adjustments_hotel_subscription",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "adjustment_type in ('discount','credit','free_extension','override')",
            name="ck_subscription_adjustments_type",
        ),
        CheckConstraint(
            "valid_until IS NULL OR valid_until >= valid_from",
            name="ck_subscription_adjustments_validity",
        ),
        UniqueConstraint(
            "hotel_id",
            "idempotency_key",
            name="uq_subscription_adjustments_hotel_idempotency_key",
        ),
        Index("ix_subscription_adjustments_hotel_created", "hotel_id", "created_at"),
        Index("ix_subscription_adjustments_subscription_id", "subscription_id"),
    )
