"""
Payment surcharge model - v72 section 12.3.

Defines per-payment-method surcharges (fixed amount or percentage) that can be
applied on top of the base transaction amount.
"""
from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class PaymentSurchargeTypeEnum(str, enum.Enum):
    FIXED = "fixed"
    PERCENTAGE = "percentage"


class PaymentSurcharge(Base):
    __tablename__ = "payment_surcharges"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id"), nullable=False)
    payment_method = Column(String(50), nullable=False)
    surcharge_type = Column(
        Enum(
            PaymentSurchargeTypeEnum,
            name="payment_surcharge_type_enum",
            create_constraint=True,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
    )
    amount = Column(Float, nullable=False)
    currency_code = Column(String(3), nullable=False, default="ARS")
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    __table_args__ = (
        UniqueConstraint("hotel_id", "payment_method", name="uq_surcharge_hotel_method"),
    )
