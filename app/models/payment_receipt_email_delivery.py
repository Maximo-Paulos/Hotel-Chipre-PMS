"""Idempotency and outcome record for explicit payment receipt emails."""
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


class PaymentReceiptEmailDelivery(Base):
    """One attempted receipt email, without retaining the guest's email address.

    ``sending`` is committed before contacting Gmail. If the process stops while
    Gmail may have accepted the request, retries see the durable in-flight row
    and fail closed instead of sending the same receipt again.
    """

    __tablename__ = "payment_receipt_email_deliveries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, nullable=False)
    transaction_id = Column(Integer, nullable=False)
    idempotency_key_hash = Column(String(64), nullable=False)
    recipient_fingerprint = Column(String(64), nullable=False)
    provider_message_id = Column(String(255), nullable=True)
    actor_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    status = Column(String(16), nullable=False, default="sending", server_default="sending")
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint("status in ('sending', 'sent', 'unknown')", name="ck_payment_receipt_email_status"),
        CheckConstraint("length(idempotency_key_hash) = 64", name="ck_payment_receipt_email_key_hash"),
        CheckConstraint("length(recipient_fingerprint) = 64", name="ck_payment_receipt_email_recipient_fingerprint"),
        ForeignKeyConstraint(
            ["hotel_id", "transaction_id"],
            ["transactions.hotel_id", "transactions.id"],
            name="fk_payment_receipt_email_hotel_transaction",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "hotel_id",
            "idempotency_key_hash",
            name="uq_payment_receipt_email_hotel_idempotency",
        ),
        Index(
            "uq_payment_receipt_email_active_transaction",
            "hotel_id",
            "transaction_id",
            unique=True,
            sqlite_where=(status.in_(["sending", "unknown"])),
            postgresql_where=(status.in_(["sending", "unknown"])),
        ),
        Index(
            "ix_payment_receipt_email_hotel_transaction_created",
            "hotel_id",
            "transaction_id",
            "created_at",
        ),
    )
