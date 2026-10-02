"""Hotel-scoped manual cash expenses awaiting explicit approval."""
from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import (
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

from app.database import Base


class CashExpenseStatusEnum(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class CashExpense(Base):
    """A proposed drawer expense; approved expenses create one cash movement."""

    __tablename__ = "cash_expenses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False)
    session_id = Column(Integer, nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    currency_code = Column(String(3), nullable=False)
    category = Column(String(64), nullable=False)
    vendor = Column(String(120), nullable=False)
    description = Column(String(300), nullable=True)
    receipt_reference = Column(String(120), nullable=True)
    receipt_filename = Column(String(255), nullable=True)
    receipt_object_id = Column(String(36), nullable=True)
    status = Column(String(20), nullable=False, default=CashExpenseStatusEnum.PENDING.value)
    cash_movement_id = Column(Integer, nullable=True, unique=True)
    recorded_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    rejected_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    rejection_reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    approved_at = Column(DateTime(timezone=True), nullable=True)
    rejected_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_cash_expenses_amount_positive"),
        CheckConstraint("length(category) > 0", name="ck_cash_expenses_category_nonempty"),
        CheckConstraint("length(vendor) > 0", name="ck_cash_expenses_vendor_nonempty"),
        CheckConstraint("status IN ('pending', 'approved', 'rejected')", name="ck_cash_expenses_status"),
        CheckConstraint(
            "receipt_reference IS NOT NULL OR receipt_object_id IS NOT NULL",
            name="ck_cash_expenses_receipt_required",
        ),
        CheckConstraint(
            "(status = 'approved' AND approved_at IS NOT NULL AND approved_by_user_id IS NOT NULL AND cash_movement_id IS NOT NULL) OR "
            "(status != 'approved' AND approved_at IS NULL AND approved_by_user_id IS NULL AND cash_movement_id IS NULL)",
            name="ck_cash_expenses_approval_consistent",
        ),
        CheckConstraint(
            "(status = 'rejected' AND rejected_at IS NOT NULL AND rejected_by_user_id IS NOT NULL AND rejection_reason IS NOT NULL) OR "
            "(status != 'rejected' AND rejected_at IS NULL AND rejected_by_user_id IS NULL AND rejection_reason IS NULL)",
            name="ck_cash_expenses_rejection_consistent",
        ),
        UniqueConstraint("hotel_id", "id", name="uq_cash_expenses_hotel_id_id"),
        ForeignKeyConstraint(
            ["hotel_id", "session_id"],
            ["cash_sessions.hotel_id", "cash_sessions.id"],
            name="fk_cash_expenses_hotel_session",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["hotel_id", "receipt_object_id"],
            ["stored_objects.hotel_id", "stored_objects.id"],
            name="fk_cash_expenses_hotel_receipt_object",
        ),
        ForeignKeyConstraint(
            ["hotel_id", "cash_movement_id"],
            ["cash_movements.hotel_id", "cash_movements.id"],
            name="fk_cash_expenses_hotel_cash_movement",
        ),
        Index("ix_cash_expenses_hotel_status_created", "hotel_id", "status", "created_at"),
        Index("ix_cash_expenses_hotel_session", "hotel_id", "session_id", "created_at"),
    )
