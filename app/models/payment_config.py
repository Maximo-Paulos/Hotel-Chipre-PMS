"""
Payment surcharge configuration — v72 §12.3.

Hotels can configure a surcharge (recargo) per payment method: either a fixed
amount or a percentage of the transaction total. Both fields are nullable;
the service layer applies whichever is set (percentage takes precedence if both
are set, which should not happen in practice).

One row per (hotel_id, payment_method). UniqueConstraint enforces this.
"""
from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    UniqueConstraint,
)

from app.database import Base
from app.models.transaction import PaymentMethodEnum


class PaymentSurchargeConfig(Base):
    """
    Per-payment-method surcharge configuration for a hotel.
    """
    __tablename__ = "payment_surcharge_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(
        Integer,
        ForeignKey("hotel_configuration.id", ondelete="CASCADE"),
        nullable=False,
    )

    payment_method = Column(
        Enum(
            PaymentMethodEnum,
            name="payment_method_enum",
            create_constraint=False,
        ),
        nullable=False,
    )

    surcharge_pct = Column(Numeric(5, 4), nullable=True)    # e.g. 0.0350 = 3.50 %
    surcharge_fixed = Column(Numeric(12, 2), nullable=True)  # fixed amount in hotel currency
    is_active = Column(Boolean, nullable=False, default=True)

    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime, nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        CheckConstraint(
            "surcharge_pct IS NULL OR (surcharge_pct >= 0 AND surcharge_pct < 1)",
            name="ck_surcharge_pct_range",
        ),
        CheckConstraint(
            "surcharge_fixed IS NULL OR surcharge_fixed >= 0",
            name="ck_surcharge_fixed_nonneg",
        ),
        UniqueConstraint("hotel_id", "payment_method", name="uq_surcharge_hotel_method"),
        Index("ix_surcharge_hotel_id", "hotel_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<PaymentSurchargeConfig(id={self.id}, hotel={self.hotel_id}, "
            f"method={self.payment_method}, pct={self.surcharge_pct}, "
            f"fixed={self.surcharge_fixed})>"
        )
