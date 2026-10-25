"""Idempotent group collections with explicit child-reservation allocations."""

from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)

from app.database import Base
from app.models.transaction import PaymentMethodEnum


class ReservationGroupPaymentBatch(Base):
    __tablename__ = "reservation_group_payment_batches"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False)
    group_id = Column(Integer, nullable=False)
    idempotency_key = Column(String(100), nullable=False)
    request_hash = Column(String(64), nullable=False)
    received_amount = Column(Numeric(12, 2), nullable=False)
    # Group allocations are stored in received_amount. gross_amount is the
    # amount retained in the tender currency after configured surcharges.
    gross_amount = Column(Numeric(12, 2), nullable=True)
    # Optional group-level tender detail; existing batches remain NULL.
    cash_received_amount = Column(Numeric(12, 2), nullable=True)
    cash_change_amount = Column(Numeric(12, 2), nullable=True)
    cash_tip_amount = Column(Numeric(12, 2), nullable=False, default=0, server_default="0")
    currency = Column(String(3), nullable=False)
    payment_method = Column(
        Enum(
            PaymentMethodEnum,
            name="reservation_group_payment_method_enum",
            create_constraint=True,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
    )
    manual_reference = Column(String(120), nullable=True)
    description = Column(String(300), nullable=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        CheckConstraint(
            "(cash_received_amount IS NULL AND cash_change_amount IS NULL AND cash_tip_amount = 0) OR "
            "(cash_received_amount IS NOT NULL AND cash_change_amount IS NOT NULL "
            "AND cash_received_amount > 0 AND cash_change_amount >= 0 "
            "AND cash_change_amount <= cash_received_amount "
            "AND gross_amount IS NOT NULL AND gross_amount > 0 "
            "AND cash_tip_amount >= 0 "
            "AND cash_tip_amount <= cash_received_amount - gross_amount "
            "AND ROUND(cash_change_amount, 2) = "
            "ROUND(cash_received_amount - gross_amount - cash_tip_amount, 2) "
            "AND payment_method = 'cash')",
            name="ck_group_payment_batch_cash_received_change_consistent",
        ),
        UniqueConstraint("hotel_id", "id", name="uq_reservation_group_payment_batches_hotel_id_id"),
        UniqueConstraint(
            "hotel_id", "idempotency_key", name="uq_reservation_group_payment_batches_idempotency"
        ),
        ForeignKeyConstraint(
            ["hotel_id", "group_id"],
            ["reservation_groups.hotel_id", "reservation_groups.id"],
            name="fk_reservation_group_payment_batches_hotel_group",
            ondelete="CASCADE",
        ),
        Index("ix_reservation_group_payment_batches_group_created", "hotel_id", "group_id", "created_at"),
    )


class ReservationGroupPaymentAllocation(Base):
    __tablename__ = "reservation_group_payment_allocations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, nullable=False)
    batch_id = Column(Integer, nullable=False)
    reservation_id = Column(Integer, nullable=False)
    transaction_id = Column(Integer, nullable=False)
    received_amount = Column(Numeric(12, 2), nullable=False)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        ForeignKeyConstraint(
            ["hotel_id", "batch_id"],
            ["reservation_group_payment_batches.hotel_id", "reservation_group_payment_batches.id"],
            name="fk_reservation_group_payment_allocations_hotel_batch",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["hotel_id", "reservation_id"],
            ["reservations.hotel_id", "reservations.id"],
            name="fk_reservation_group_payment_allocations_hotel_reservation",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["hotel_id", "transaction_id"],
            ["transactions.hotel_id", "transactions.id"],
            name="fk_reservation_group_payment_allocations_hotel_transaction",
            ondelete="CASCADE",
        ),
        UniqueConstraint("hotel_id", "batch_id", "reservation_id", name="uq_group_payment_batch_reservation"),
        UniqueConstraint("hotel_id", "transaction_id", name="uq_group_payment_allocation_transaction"),
        Index("ix_group_payment_allocations_hotel_batch", "hotel_id", "batch_id"),
    )
