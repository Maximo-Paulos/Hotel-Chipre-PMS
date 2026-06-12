"""
RefundRequest model — tracks the three-path refund lifecycle per product §8.7.

Paths:
  gateway      — money returned via original payment gateway (MP, PayPal, Stripe).
  voucher      — hotel credit issued (see hotel_vouchers table).
  manual_review — case flagged for human resolution; no automatic settlement.

Every refund outcome must produce an audit record (via audit_logs) after
the service layer processes the request.
"""
from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Enum,
    Numeric,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.database import Base


class RefundPathEnum(str, enum.Enum):
    GATEWAY = "gateway"
    VOUCHER = "voucher"
    MANUAL_REVIEW = "manual_review"


class RefundStatusEnum(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RefundRequest(Base):
    """
    Tracks a refund from request through resolution.
    Partial refunds are allowed when gateway/voucher supports them;
    otherwise the status should be FAILED and a manual_review action created.
    """
    __tablename__ = "refund_requests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(
        Integer,
        ForeignKey("hotel_configuration.id", ondelete="CASCADE"),
        nullable=False,
    )
    reservation_id = Column(
        Integer,
        ForeignKey("reservations.id", ondelete="CASCADE"),
        nullable=False,
    )
    original_transaction_id = Column(
        Integer,
        ForeignKey("transactions.id", ondelete="SET NULL"),
        nullable=True,
    )

    amount = Column(Numeric(12, 2), nullable=False)
    currency_code = Column(String(3), nullable=False, default="ARS")

    path = Column(
        Enum(
            RefundPathEnum,
            name="refund_path_enum",
            create_constraint=True,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
    )
    status = Column(
        Enum(
            RefundStatusEnum,
            name="refund_status_enum",
            create_constraint=True,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
        default=RefundStatusEnum.PENDING,
    )

    # Gateway path — provider-issued refund reference
    gateway_refund_id = Column(String(200), nullable=True)
    gateway_response = Column(Text, nullable=True)

    # Voucher path — FK to the created voucher (set when path=voucher and status=completed)
    voucher_id = Column(
        Integer,
        ForeignKey("hotel_vouchers.id", ondelete="SET NULL"),
        nullable=True,
    )

    reason_code = Column(String(50), nullable=True)
    reason_note = Column(Text, nullable=True)

    requested_by_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    authorized_by_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    requested_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    resolved_at = Column(DateTime, nullable=True)

    reservation = relationship("Reservation", lazy="select")
    original_transaction = relationship("Transaction", lazy="select")
    voucher = relationship("HotelVoucher", lazy="select")
    requested_by = relationship("User", foreign_keys=[requested_by_user_id], lazy="select")
    authorized_by = relationship("User", foreign_keys=[authorized_by_user_id], lazy="select")

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_refund_requests_amount_positive"),
        Index("ix_refund_requests_hotel_reservation", "hotel_id", "reservation_id"),
        Index("ix_refund_requests_hotel_status", "hotel_id", "status"),
    )

    def __repr__(self) -> str:
        return (
            f"<RefundRequest(id={self.id}, hotel={self.hotel_id}, "
            f"reservation={self.reservation_id}, amount={self.amount}, "
            f"path={self.path}, status={self.status})>"
        )
