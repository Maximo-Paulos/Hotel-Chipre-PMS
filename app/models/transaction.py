"""
Transaction and PaymentMethod models.
Supports: Efectivo (Cash), MercadoPago, PayPal, Credit/Debit Card.
"""
import enum
from sqlalchemy import (
    Column, Integer, Float, String, ForeignKey, Enum, Text, DateTime,
    CheckConstraint
)
from sqlalchemy.orm import relationship
from datetime import datetime, timezone

from app.database import Base


class PaymentMethodEnum(str, enum.Enum):
    CASH = "cash"
    MERCADO_PAGO = "mercado_pago"
    PAYPAL = "paypal"
    CREDIT_CARD = "credit_card"
    DEBIT_CARD = "debit_card"
    BANK_TRANSFER = "bank_transfer"


class TransactionStatusEnum(str, enum.Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"
    CANCELLED = "cancelled"


class TransactionTypeEnum(str, enum.Enum):
    DEPOSIT = "deposit"
    FULL_PAYMENT = "full_payment"
    PARTIAL_PAYMENT = "partial_payment"
    BALANCE_PAYMENT = "balance_payment"
    REFUND = "refund"


class Transaction(Base):
    """
    Financial transaction linked to a reservation.
    Every money movement is recorded here with its payment method and status.
    """
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    reservation_id = Column(Integer, ForeignKey("reservations.id", ondelete="CASCADE"), nullable=False)

    # Financial details
    amount = Column(Float, nullable=False)
    currency = Column(String(3), nullable=False, default="ARS")

    transaction_type = Column(
        Enum(TransactionTypeEnum, name="transaction_type_enum", create_constraint=True),
        nullable=False,
    )
    payment_method = Column(
        Enum(PaymentMethodEnum, name="payment_method_enum", create_constraint=True),
        nullable=False,
    )
    status = Column(
        Enum(TransactionStatusEnum, name="transaction_status_enum", create_constraint=True),
        nullable=False,
        default=TransactionStatusEnum.PENDING,
    )

    # External payment gateway references
    external_payment_id = Column(String(200), nullable=True)  # MP preference_id, PayPal order_id
    external_status = Column(String(50), nullable=True)       # Gateway-reported status
    gateway_response = Column(Text, nullable=True)            # Full JSON response from gateway

    # Description / notes
    description = Column(Text, nullable=True)

    # Metadata
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime, nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    processed_at = Column(DateTime, nullable=True)

    # Relationships
    reservation = relationship("Reservation", back_populates="transactions")

    __table_args__ = (
        CheckConstraint("amount != 0", name="ck_transaction_amount_nonzero"),
    )

    def __repr__(self) -> str:
        return (
            f"<Transaction(id={self.id}, reservation_id={self.reservation_id}, "
            f"amount={self.amount}, method={self.payment_method}, status={self.status})>"
        )
