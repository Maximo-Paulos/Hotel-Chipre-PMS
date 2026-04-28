"""
HotelConfiguration — per-hotel business rules.
No global/singleton: one row per hotel (id == hotel_id).
Admin Panel controls: deposit %, enabled gateways, cancellation policy, etc.
"""
import json
from sqlalchemy import Column, Integer, Float, Boolean, String, Text, DateTime
from datetime import datetime, timezone

from app.database import Base


class HotelConfiguration(Base):
    """Configuration table scoped by hotel (id == hotel_id)."""
    __tablename__ = "hotel_configuration"

    # hotel_id is the primary key; no auto-assigned default to avoid implicit singletons
    id = Column(Integer, primary_key=True, autoincrement=False)

    # Financial policies
    deposit_percentage = Column(Float, nullable=False, default=30.0)  # % of total required as deposit
    enable_full_payment = Column(Boolean, nullable=False, default=True)
    enable_deposit_payment = Column(Boolean, nullable=False, default=True)

    # Payment gateways toggles
    enable_cash = Column(Boolean, nullable=False, default=True)
    enable_mercado_pago = Column(Boolean, nullable=False, default=True)
    enable_paypal = Column(Boolean, nullable=False, default=True)
    enable_credit_card = Column(Boolean, nullable=False, default=True)
    enable_debit_card = Column(Boolean, nullable=False, default=True)
    enable_bank_transfer = Column(Boolean, nullable=False, default=False)

    # Cancellation policies
    free_cancellation_hours = Column(Integer, nullable=False, default=48)
    cancellation_penalty_percentage = Column(Float, nullable=False, default=0.0)
    allow_cancellation_after_checkin = Column(Boolean, nullable=False, default=False)

    # OTA toggles
    enable_booking_sync = Column(Boolean, nullable=False, default=True)
    enable_expedia_sync = Column(Boolean, nullable=False, default=True)

    # Subscription / ownership
    owner_email = Column(String(200), nullable=True)
    subscription_active = Column(Boolean, nullable=False, default=True)
    analytics_ai_enabled = Column(Boolean, nullable=False, default=False)

    # Check-in policies
    require_document_for_checkin = Column(Boolean, nullable=False, default=True)
    require_terms_acceptance = Column(Boolean, nullable=False, default=True)

    # General
    hotel_name = Column(String(200), nullable=False, default="Mi Hotel")
    hotel_timezone = Column(String(100), nullable=False, default="America/Argentina/Buenos_Aires")
    default_currency = Column(String(3), nullable=False, default="ARS")

    # Display / permissions (scaffolding)
    receptionist_view_past_days = Column(Integer, nullable=False, default=0)
    receptionist_view_future_days = Column(Integer, nullable=False, default=7)
    allow_revenue_manager = Column(Boolean, nullable=False, default=True)
    allow_revenue_receptionist = Column(Boolean, nullable=False, default=False)

    # Operations / availability
    sync_interval_minutes = Column(Integer, nullable=False, default=5)
    safety_buffer_rooms = Column(Integer, nullable=False, default=0)
    allow_overbooking = Column(Boolean, nullable=False, default=False)
    max_overallocation_pct = Column(Float, nullable=False, default=0.0)

    # No-show and OTA push
    no_show_cutoff_hours = Column(Integer, nullable=False, default=24)
    ota_autopush_enabled = Column(Boolean, nullable=False, default=False)

    # Payment validation
    card_validation_enabled = Column(Boolean, nullable=False, default=False)
    payment_retry_attempts = Column(Integer, nullable=False, default=2)
    auth_amount_pct = Column(Float, nullable=False, default=0.0)

    # Notifications / stop-sell (stored as JSON/text for flexibility)
    stop_sell_channels = Column(Text, nullable=True)  # JSON array of channel codes
    event_notifications = Column(Text, nullable=True)  # JSON array of {event, channel, quiet_hours}

    # Additional policies as JSON
    extra_policies = Column(Text, nullable=True)  # Flexible JSON for future policies

    updated_at = Column(
        DateTime, nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def get_extra_policies(self) -> dict:
        """Parse and return extra_policies as a dictionary."""
        if self.extra_policies:
            return json.loads(self.extra_policies)
        return {}

    def set_extra_policies(self, policies: dict) -> None:
        """Serialize policies dict to JSON string."""
        self.extra_policies = json.dumps(policies)

    def is_payment_method_enabled(self, method_name: str) -> bool:
        """Check if a specific payment method is enabled."""
        mapping = {
            "cash": self.enable_cash,
            "mercado_pago": self.enable_mercado_pago,
            "paypal": self.enable_paypal,
            "credit_card": self.enable_credit_card,
            "debit_card": self.enable_debit_card,
            "bank_transfer": self.enable_bank_transfer,
        }
        return mapping.get(method_name, False)

    def __repr__(self) -> str:
        return f"<HotelConfiguration(hotel_id={self.id}, deposit={self.deposit_percentage}%, hotel='{self.hotel_name}')>"
