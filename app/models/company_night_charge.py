"""Per-night company extras and their payment allocations."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
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
    Text,
    UniqueConstraint,
    text,
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
    # Keep the price and quantity used to build the total as a durable
    # snapshot. Legacy charges have no rate row and are backfilled as one
    # extra person at their original total amount.
    unit_amount = Column(Numeric(12, 2), nullable=True)
    quantity = Column(Integer, nullable=False, default=1, server_default="1")
    rate_id = Column(Integer, nullable=True)
    rate_effective_from = Column(Date, nullable=True)
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
        ForeignKeyConstraint(
            ["hotel_id", "company_id", "rate_id"],
            [
                "company_nightly_surcharge_rates.hotel_id",
                "company_nightly_surcharge_rates.company_id",
                "company_nightly_surcharge_rates.id",
            ],
            name="fk_company_night_charges_hotel_rate",
            ondelete="RESTRICT",
        ),
        CheckConstraint("quantity > 0", name="ck_company_night_charges_quantity_positive"),
        Index("ix_company_night_charges_hotel_reservation", "hotel_id", "reservation_id", "stay_date"),
    )


class CompanyNightlySurchargeRate(Base):
    """Append-only, effective-dated per-extra-person company rates."""

    __tablename__ = "company_nightly_surcharge_rates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False)
    company_id = Column(Integer, nullable=False)
    effective_from = Column(Date, nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    is_migration_seed = Column(Boolean, nullable=False, default=False, server_default=text("false"))
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        CheckConstraint("amount >= 0", name="ck_company_nightly_surcharge_rates_amount_nonnegative"),
        UniqueConstraint("hotel_id", "company_id", "id", name="uq_company_nightly_surcharge_rates_hotel_company_id"),
        ForeignKeyConstraint(
            ["hotel_id", "company_id"],
            ["companies.hotel_id", "companies.id"],
            name="fk_company_nightly_surcharge_rates_hotel_company",
            ondelete="CASCADE",
        ),
        Index(
            "ix_company_nightly_surcharge_rates_hotel_company_date",
            "hotel_id",
            "company_id",
            "effective_from",
            "id",
        ),
    )


class CompanyNightChargeAmountAdjustment(Base):
    """Audited correction of a selected company's nightly charge amount."""

    __tablename__ = "company_night_charge_amount_adjustments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False)
    company_night_charge_id = Column(Integer, nullable=False)
    previous_amount = Column(Numeric(12, 2), nullable=False)
    new_amount = Column(Numeric(12, 2), nullable=False)
    delta_amount = Column(Numeric(12, 2), nullable=False)
    reason = Column(Text, nullable=False)
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        CheckConstraint("previous_amount > 0", name="ck_company_night_charge_amount_adjustments_previous_positive"),
        CheckConstraint("new_amount > 0", name="ck_company_night_charge_amount_adjustments_new_positive"),
        CheckConstraint(
            "delta_amount = new_amount - previous_amount",
            name="ck_company_night_charge_amount_adjustments_delta_consistent",
        ),
        ForeignKeyConstraint(
            ["hotel_id", "company_night_charge_id"],
            ["company_night_charges.hotel_id", "company_night_charges.id"],
            name="fk_company_night_charge_amount_adjustments_hotel_charge",
            ondelete="CASCADE",
        ),
        Index(
            "ix_company_night_charge_amount_adjustments_hotel_charge",
            "hotel_id",
            "company_night_charge_id",
            "created_at",
            "id",
        ),
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
