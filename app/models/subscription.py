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
    entitlements = relationship("SubscriptionEntitlement", back_populates="plan", cascade="all, delete-orphan")


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


class SubscriptionEntitlement(Base):
    """
    Entitlement linked to a subscription plan (e.g., room limits, feature toggles).
    Stores value as string with an explicit type for portable parsing across DB backends.
    """

    __tablename__ = "subscription_entitlements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    plan_id = Column(Integer, ForeignKey("subscription_plans.id", ondelete="CASCADE"), nullable=False)
    code = Column(String(100), nullable=False)
    value = Column(String(200), nullable=True)
    value_type = Column(String(20), nullable=False, default="str")
    description = Column(String(255), nullable=True)

    plan = relationship("SubscriptionPlan", back_populates="entitlements")

    __table_args__ = (
        UniqueConstraint("plan_id", "code", name="uq_plan_entitlement_code"),
    )


class HotelEntitlementOverride(Base):
    """
    Per-hotel entitlement override to tweak limits/features without cloning plans.
    """

    __tablename__ = "hotel_entitlement_overrides"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False)
    code = Column(String(100), nullable=False)
    value = Column(String(200), nullable=True)
    value_type = Column(String(20), nullable=False, default="str")

    __table_args__ = (
        UniqueConstraint("hotel_id", "code", name="uq_hotel_entitlement_code"),
    )
