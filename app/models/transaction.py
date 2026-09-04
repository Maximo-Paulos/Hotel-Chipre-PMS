"""
Transaction and PaymentMethod models.
Supports: Efectivo (Cash), MercadoPago, PayPal, Credit/Debit Card.
"""
import enum
from sqlalchemy import (
    Column, Integer, Float, Numeric, String, ForeignKey, Enum, Text, DateTime,
    CheckConstraint, ForeignKeyConstraint, Index, UniqueConstraint
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
    hotel_id = Column(
        Integer,
        ForeignKey("hotel_configuration.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reservation_id = Column(Integer, nullable=False)

    # Financial details
    amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(3), nullable=False, default="ARS")
    gross_amount = Column(Numeric(12, 2), nullable=True)
    tax_amount = Column(Numeric(12, 2), nullable=True)
    fee_amount = Column(Numeric(12, 2), nullable=True)
    net_amount = Column(Numeric(12, 2), nullable=True)
    fx_rate_snapshot = Column(Float, nullable=True)
    provider_code = Column(String(50), nullable=True)

    transaction_type = Column(
        Enum(
            TransactionTypeEnum,
            name="transaction_type_enum",
            create_constraint=True,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
    )
    payment_method = Column(
        Enum(
            PaymentMethodEnum,
            name="payment_method_enum",
            create_constraint=True,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
    )
    status = Column(
        Enum(
            TransactionStatusEnum,
            name="transaction_status_enum",
            create_constraint=True,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
        default=TransactionStatusEnum.PENDING,
    )

    # External payment gateway references
    external_payment_id = Column(String(200), nullable=True)  # MP preference_id, PayPal order_id
    external_status = Column(String(50), nullable=True)       # Gateway-reported status
    gateway_response = Column(Text, nullable=True)            # Full JSON response from gateway
    # Idempotency: dedupe gateway-driven transactions (hotel_id, reservation_id, idempotency_key)
    idempotency_key = Column(String(100), nullable=True)

    # Audit: which staff user triggered this money-moving state change, if any.
    # NULL is a legitimate value for gateway/webhook-initiated transactions
    # (no human actor exists) -- never fabricate one for those.
    created_by_user_id = Column(Integer, nullable=True)

    # Description / notes
    description = Column(Text, nullable=True)
    pricing_snapshot = Column(Text, nullable=True)

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
        # Gateway idempotency: at most one transaction per idempotency_key per reservation.
        # Partial index (key NOT NULL) so cash/manual transactions (null key) are unconstrained.
        Index(
            "uq_transactions_hotel_reservation_idempotency_key",
            "hotel_id", "reservation_id", "idempotency_key",
            unique=True,
            sqlite_where=idempotency_key.isnot(None),
            postgresql_where=idempotency_key.isnot(None),
        ),
        Index("ix_transactions_hotel_status_created_at", "hotel_id", "status", "created_at"),
        Index(
            "ix_transactions_hotel_processed_status_method",
            "hotel_id", "processed_at", "status", "payment_method",
        ),
        UniqueConstraint("hotel_id", "id", name="uq_transaction_hotel_id_id"),
        ForeignKeyConstraint(
            ["hotel_id", "reservation_id"],
            ["reservations.hotel_id", "reservations.id"],
            name="fk_transactions_hotel_reservation",
            ondelete="CASCADE",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<Transaction(id={self.id}, hotel_id={self.hotel_id}, reservation_id={self.reservation_id}, "
            f"amount={self.amount}, method={self.payment_method}, status={self.status})>"
        )
