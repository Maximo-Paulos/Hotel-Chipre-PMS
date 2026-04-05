"""
Subscription models: plans and per-hotel subscription status.
"""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database import Base


class SubscriptionPlan(Base):
    __tablename__ = "subscription_plans"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(30), nullable=False, unique=True)
    name = Column(String(100), nullable=False)
    room_limit = Column(Integer, nullable=False, default=20)
    price_month = Column(Float, nullable=True)  # placeholder for future billing
    features = Column(String(500), nullable=True)


class HotelSubscription(Base):
    __tablename__ = "hotel_subscriptions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False)
    plan_id = Column(Integer, ForeignKey("subscription_plans.id"), nullable=False)
    status = Column(String(20), nullable=False, default="active")  # active, paused, cancelled, past_due
    starts_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    ends_at = Column(DateTime, nullable=True)
    next_billing_at = Column(DateTime, nullable=True)
    room_limit_override = Column(Integer, nullable=True)
    last_payment_status = Column(String(20), nullable=True)

    plan = relationship("SubscriptionPlan")

    __table_args__ = (
        UniqueConstraint("hotel_id", name="uq_subscription_hotel_single"),
    )
