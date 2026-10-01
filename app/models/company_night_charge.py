"""Per-night company extras and their payment allocations."""
from __future__ import annotations

from datetime import datetime, timezone

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


class CompanyNightCharge(Base):
    __tablename__ = "company_night_charges"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False)
    reservation_id = Column(Integer, nullable=False)
    company_id = Column(Integer, nullable=False)
    billing_adjustment_id = Column(Integer, nullable=False, unique=True)
    stay_date = Column(Date, nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    currency_code = Column(String(3), nullable=False, default="ARS")
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_company_night_charges_amount_positive"),
        UniqueConstraint("hotel_id", "reservation_id", "stay_date", name="uq_company_night_charges_reservation_date"),
        UniqueConstraint("hotel_id", "id", name="uq_company_night_charges_hotel_id_id"),
        ForeignKeyConstraint(
            ["hotel_id", "reservation_id"],
            ["reservations.hotel_id", "reservations.id"],
            name="fk_company_night_charges_hotel_reservation",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["hotel_id", "company_id"],
            ["companies.hotel_id", "companies.id"],
            name="fk_company_night_charges_hotel_company",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["hotel_id", "billing_adjustment_id"],
            ["billing_adjustments.hotel_id", "billing_adjustments.id"],
            name="fk_company_night_charges_hotel_billing_adjustment",
            ondelete="CASCADE",
        ),
        Index("ix_company_night_charges_hotel_reservation", "hotel_id", "reservation_id", "stay_date"),
    )


class CompanyNightChargePaymentAllocation(Base):
    __tablename__ = "company_night_charge_payment_allocations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False)
    transaction_id = Column(Integer, nullable=False)
    company_night_charge_id = Column(Integer, nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_company_night_charge_allocations_amount_positive"),
        UniqueConstraint("transaction_id", "company_night_charge_id", name="uq_company_night_charge_payment_allocation"),
        ForeignKeyConstraint(
            ["hotel_id", "transaction_id"],
            ["transactions.hotel_id", "transactions.id"],
            name="fk_company_night_charge_allocations_hotel_transaction",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["hotel_id", "company_night_charge_id"],
            ["company_night_charges.hotel_id", "company_night_charges.id"],
            name="fk_company_night_charge_allocations_hotel_charge",
            ondelete="CASCADE",
        ),
        Index("ix_company_night_charge_allocations_hotel_charge", "hotel_id", "company_night_charge_id"),
    )
