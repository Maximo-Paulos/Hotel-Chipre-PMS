"""Auditable corrections that reverse and optionally reassign a payment entry."""
from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
)

from app.database import Base


class PaymentCorrection(Base):
    """One atomic correction for a completed payment transaction.

    The original transaction remains as historical evidence but changes to
    ``cancelled`` so normal financial aggregates stop counting it. A
    replacement transaction is present only when reassigning the payment to
    another reservation. This record links both entries and stores the reason
    and idempotency identity for the correction operation.
    """

    __tablename__ = "payment_corrections"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", ondelete="RESTRICT"), nullable=False)
    source_transaction_id = Column(Integer, nullable=False)
    source_reservation_id = Column(Integer, nullable=False)
    target_reservation_id = Column(Integer, nullable=True)
    replacement_transaction_id = Column(Integer, nullable=True)
    correction_type = Column(String(32), nullable=False)
    reason = Column(String(240), nullable=False)
    idempotency_key = Column(String(100), nullable=False)
    actor_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        CheckConstraint(
            "correction_type IN ('reassign', 'duplicate_reversal')",
            name="ck_payment_corrections_type",
        ),
        CheckConstraint(
            "length(trim(reason)) > 0 AND length(trim(idempotency_key)) >= 8",
            name="ck_payment_corrections_reason_and_key",
        ),
        CheckConstraint(
            "(correction_type = 'reassign' AND target_reservation_id IS NOT NULL "
            "AND replacement_transaction_id IS NOT NULL) OR "
            "(correction_type = 'duplicate_reversal' AND target_reservation_id IS NULL "
            "AND replacement_transaction_id IS NULL)",
            name="ck_payment_corrections_replacement_shape",
        ),
        UniqueConstraint("hotel_id", "source_transaction_id", name="uq_payment_corrections_source"),
        UniqueConstraint("hotel_id", "idempotency_key", name="uq_payment_corrections_idempotency"),
        UniqueConstraint("hotel_id", "id", name="uq_payment_corrections_hotel_id_id"),
        ForeignKeyConstraint(
            ["hotel_id", "source_transaction_id"],
            ["transactions.hotel_id", "transactions.id"],
            name="fk_payment_corrections_source_transaction",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["hotel_id", "source_reservation_id"],
            ["reservations.hotel_id", "reservations.id"],
            name="fk_payment_corrections_source_reservation",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["hotel_id", "target_reservation_id"],
            ["reservations.hotel_id", "reservations.id"],
            name="fk_payment_corrections_target_reservation",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["hotel_id", "replacement_transaction_id"],
            ["transactions.hotel_id", "transactions.id"],
            name="fk_payment_corrections_replacement_transaction",
            ondelete="RESTRICT",
        ),
        Index("ix_payment_corrections_hotel_created", "hotel_id", "created_at", "id"),
    )
