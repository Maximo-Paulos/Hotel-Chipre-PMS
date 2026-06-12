"""
Payment gateway tracking models: PaymentLink, Payment, PaymentWebhookEvent.

Source-of-truth rule (docs/data-foundations/transactions-vs-payments.md):
  - transactions: the canonical financial ledger — balance/arqueo ALWAYS computed from it
  - payments: gateway-specific state (provider, external_payment_id, webhook lifecycle)
  - payment_links: pre-payment object sent to the guest (MercadoPago/PayPal/Stripe)
  - Flow: PaymentLink → webhook → Payment(completed) → Transaction (payment_service.py)

Schema mirrors alembic revision 20260612_v72_gaps_phase6_payment_tables exactly.
provider/status are String (not PG enums) intentionally — values evolve per gateway.
"""
import enum

from sqlalchemy import (
    Boolean, CheckConstraint, Column, DateTime, Float, ForeignKey,
    ForeignKeyConstraint, Integer, JSON, Numeric, String, Text,
    UniqueConstraint, func,
)
from sqlalchemy.orm import relationship

from app.database import Base


class PaymentProviderEnum(str, enum.Enum):
    """Reference values for payments.provider / payment_links.provider (stored as String)."""
    CASH = "cash"
    MERCADO_PAGO = "mercado_pago"
    PAYPAL = "paypal"
    STRIPE = "stripe"


class PaymentStatusEnum(str, enum.Enum):
    """Reference values for payments.status (stored as String)."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"
    EXPIRED = "expired"


class PaymentLinkStatusEnum(str, enum.Enum):
    """Reference values for payment_links.status (stored as String)."""
    ACTIVE = "active"
    PAID = "paid"
    PARTIALLY_PAID = "partially_paid"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class PaymentLink(Base):
    """Guest-facing pre-payment object (checkout URL / QR). May collect partial payments."""
    __tablename__ = "payment_links"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id"), nullable=False, index=True)
    reservation_id = Column(Integer, nullable=False, index=True)

    link_code = Column(String(64), nullable=False, index=True)
    requested_amount = Column(Numeric(12, 2), nullable=False)
    collected_amount = Column(Numeric(12, 2), nullable=False, default=0, server_default="0.00")
    currency = Column(String(3), nullable=False, default="ARS", server_default="ARS")
    provider = Column(String(30), nullable=False, default="mercado_pago", server_default="mercado_pago")
    status = Column(String(20), nullable=False, default="active", server_default="active", index=True)

    recipient_email = Column(String(255), nullable=False)
    recipient_name = Column(String(255), nullable=True)
    recipient_phone = Column(String(20), nullable=True)
    sent_via_email = Column(Boolean, nullable=False, default=False, server_default="0")
    sent_via_whatsapp = Column(Boolean, nullable=False, default=False, server_default="0")

    external_reference = Column(String(120), nullable=True, index=True)
    external_checkout_url = Column(Text, nullable=True)
    external_qr_code = Column(Text, nullable=True)

    title = Column(String(255), nullable=False, default="Pago de Reserva", server_default="Pago de Reserva")
    description = Column(Text, nullable=True)
    allow_partial_payments = Column(Boolean, nullable=False, default=True, server_default="1")
    require_exact_amount = Column(Boolean, nullable=False, default=False, server_default="0")

    created_by = Column(String(100), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    expires_at = Column(DateTime, nullable=True)
    cancelled_at = Column(DateTime, nullable=True)
    first_payment_at = Column(DateTime, nullable=True)
    last_payment_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    gateway_response = Column(JSON, nullable=True)
    last_error = Column(Text, nullable=True)

    payments = relationship("Payment", back_populates="payment_link")

    __table_args__ = (
        CheckConstraint("requested_amount > 0", name="ck_payment_link_amount_positive"),
        CheckConstraint("collected_amount >= 0", name="ck_payment_link_collected_nonnegative"),
        ForeignKeyConstraint(
            ["hotel_id", "reservation_id"],
            ["reservations.hotel_id", "reservations.id"],
            name="fk_payment_link_hotel_reservation",
            ondelete="CASCADE",
        ),
        UniqueConstraint("hotel_id", "id", name="uq_payment_link_hotel_id_id"),
        UniqueConstraint("link_code", name="uq_payment_link_code"),
        UniqueConstraint(
            "hotel_id", "provider", "external_reference",
            name="uq_payment_link_external_per_hotel_provider",
        ),
    )


class Payment(Base):
    """One gateway payment object (MP preference / PayPal order / Stripe intent).

    Never the financial source of truth — a completed Payment writes a Transaction.
    """
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id"), nullable=False, index=True)
    reservation_id = Column(Integer, nullable=False, index=True)

    amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(3), nullable=False, default="ARS", server_default="ARS")
    provider = Column(String(30), nullable=False, default="cash", server_default="cash")
    status = Column(String(20), nullable=False, default="pending", server_default="pending", index=True)

    external_payment_id = Column(String(200), nullable=True, index=True)
    external_status = Column(String(100), nullable=True)
    payment_link_id = Column(
        Integer, ForeignKey("payment_links.id", ondelete="SET NULL"), nullable=True
    )

    description = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    gateway_response = Column(JSON, nullable=True)

    fee_amount = Column(Numeric(12, 2), nullable=True)
    net_amount = Column(Numeric(12, 2), nullable=True)
    fx_rate = Column(Float, nullable=True)  # exchange rate, not monetary

    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now(), index=True)
    processed_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
    expires_at = Column(DateTime, nullable=True)

    payment_link = relationship("PaymentLink", back_populates="payments")
    webhook_events = relationship("PaymentWebhookEvent", back_populates="payment")

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_payment_amount_positive"),
        ForeignKeyConstraint(
            ["hotel_id", "reservation_id"],
            ["reservations.hotel_id", "reservations.id"],
            name="fk_payment_hotel_reservation",
            ondelete="CASCADE",
        ),
        UniqueConstraint("hotel_id", "id", name="uq_payment_hotel_id_id"),
        UniqueConstraint(
            "hotel_id", "provider", "external_payment_id",
            name="uq_payment_external_per_hotel_provider",
        ),
    )


class PaymentWebhookEvent(Base):
    """Raw webhook log per payment — idempotent on (hotel_id, provider, webhook_id)."""
    __tablename__ = "payment_webhook_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id"), nullable=False, index=True)
    payment_id = Column(Integer, nullable=False, index=True)

    provider = Column(String(30), nullable=False)
    webhook_id = Column(String(200), nullable=True, index=True)
    event_type = Column(String(100), nullable=False)
    raw_payload = Column(JSON, nullable=False)

    processed = Column(Boolean, nullable=False, default=False, server_default="0", index=True)
    processing_error = Column(Text, nullable=True)
    processed_at = Column(DateTime, nullable=True)
    received_at = Column(DateTime, nullable=False, server_default=func.now(), index=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    payment = relationship("Payment", back_populates="webhook_events")

    __table_args__ = (
        ForeignKeyConstraint(
            ["hotel_id", "payment_id"],
            ["payments.hotel_id", "payments.id"],
            name="fk_webhook_event_hotel_payment",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "hotel_id", "provider", "webhook_id",
            name="uq_webhook_event_provider_id_per_hotel",
        ),
    )
