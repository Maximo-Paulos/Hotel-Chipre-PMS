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
    Index,
    Integer,
    String,
    Text,
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

    __table_args__ = (
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
