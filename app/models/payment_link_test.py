from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, Integer, JSON, String, Text, ForeignKey

from app.database import Base


class PaymentLinkTest(Base):
    __tablename__ = "payment_link_tests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False, index=True)
    provider = Column(String(50), nullable=False, default="mercadopago")
    recipient_email = Column(String(255), nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(String(3), nullable=False, default="ARS")
    description = Column(String(255), nullable=False)
    external_reference = Column(String(120), nullable=False, unique=True, index=True)
    preference_id = Column(String(120), nullable=True)
    payment_link = Column(Text, nullable=True)
    status = Column(String(30), nullable=False, default="pending")
    external_status = Column(String(120), nullable=True)
    external_payment_id = Column(String(120), nullable=True)
    refunded_amount = Column(Float, nullable=True)
    gateway_response = Column(JSON, nullable=True)
    email_sent_at = Column(DateTime, nullable=True)
    sender_channel = Column(String(50), nullable=True)
    sender_email = Column(String(255), nullable=True)
    expires_at = Column(DateTime, nullable=True)
    last_checked_at = Column(DateTime, nullable=True)
    last_error = Column(Text, nullable=True)
    paid_at = Column(DateTime, nullable=True)
    refunded_at = Column(DateTime, nullable=True)
    cancelled_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    @property
    def payment_url(self) -> str | None:
        return self.payment_link
