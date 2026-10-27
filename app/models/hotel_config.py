"""
HotelConfiguration — per-hotel business rules.
No global/singleton: one row per hotel (id == hotel_id).
Admin Panel controls: deposit %, enabled gateways, cancellation policy, etc.
"""
import json
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    Integer,
    Numeric,
    String,
    Text,
    text,
)

from app.database import Base


class HotelConfiguration(Base):
    """Configuration table scoped by hotel (id == hotel_id)."""
    __tablename__ = "hotel_configuration"
    __table_args__ = (
        CheckConstraint(
            "checkin_payment_policy IN ('deposit', 'total', 'free')",
            name="ck_hotel_configuration_checkin_payment_policy",
        ),
        CheckConstraint(
            "checkin_reservation_status_policy IN ('partial_checkin', 'checked_in_on_first_guest')",
            name="ck_hotel_configuration_checkin_reservation_status_policy",
        ),
        CheckConstraint(
            "(manual_rate_min_adjustment_pct IS NULL AND manual_rate_max_adjustment_pct IS NULL) "
            "OR (manual_rate_min_adjustment_pct IS NOT NULL AND manual_rate_max_adjustment_pct IS NOT NULL "
            "AND manual_rate_min_adjustment_pct >= -100 "
            "AND manual_rate_min_adjustment_pct <= manual_rate_max_adjustment_pct)",
            name="ck_hotel_configuration_manual_rate_bounds",
        ),
        CheckConstraint(
            "fx_usd_to_ars_rate_side IN ('compra', 'venta')",
            name="ck_hotel_configuration_fx_usd_to_ars_rate_side",
        ),
        CheckConstraint(
            "fx_ars_to_usd_rate_side IN ('compra', 'venta')",
            name="ck_hotel_configuration_fx_ars_to_usd_rate_side",
        ),
        CheckConstraint(
            "fx_usd_to_ars_rate_type IN ('oficial', 'blue')",
            name="ck_hotel_configuration_fx_usd_to_ars_rate_type",
        ),
        CheckConstraint(
            "fx_ars_to_usd_rate_type IN ('oficial', 'blue')",
            name="ck_hotel_configuration_fx_ars_to_usd_rate_type",
        ),
        CheckConstraint(
            "fx_rounding_policy IN ('round_up', 'round_down', 'nearest_ten', 'exact', 'keep_remainder')",
            name="ck_hotel_configuration_fx_rounding_policy",
        ),
        CheckConstraint(
            "tariff_low_occupancy_pct >= 0 AND tariff_low_occupancy_pct < tariff_high_occupancy_pct "
            "AND tariff_high_occupancy_pct <= 100",
            name="ck_hotel_configuration_tariff_occupancy_thresholds",
        ),
        CheckConstraint(
            "tariff_pickup_change_pct > 0 AND tariff_max_step_pct > 0 AND tariff_max_step_pct <= 5",
            name="ck_hotel_configuration_tariff_recommendation_bounds",
        ),
    )

    # hotel_id is the primary key; no auto-assigned default to avoid implicit singletons
    id = Column(Integer, primary_key=True, autoincrement=False)

    # Financial policies
    deposit_percentage = Column(Float, nullable=False, default=30.0)  # % of total required as deposit
    # Ordered duration bands; null retains the legacy percentage behavior.
    # PostgreSQL remains authoritative; this JSON is small, hotel-owned config.
    deposit_policy_rules = Column(JSON, nullable=True)
    # Defaults are not hotel decisions; reservations stay blocked until an
    # owner explicitly confirms the deposit and cancellation rules.
    deposit_policy_configured = Column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    # Check-in requires the full hotel-collected amount unless this hotel
    # explicitly selects another policy. Deferred company accounts are
    # evaluated from their company profile in checkin_service.
    checkin_payment_policy = Column(
        String(16), nullable=False, default="total", server_default=text("'total'")
    )
    checkin_reservation_status_policy = Column(
        String(32),
        nullable=False,
        default="partial_checkin",
        server_default=text("'partial_checkin'"),
    )
    block_checkin_on_company_terms_change = Column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    allow_stock_count_self_approval = Column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    enable_full_payment = Column(Boolean, nullable=False, default=True)
    enable_deposit_payment = Column(Boolean, nullable=False, default=True)

    # Payment gateways toggles
    # New hotels start with cash as the only enabled collection method. The
    # owner selects other methods during onboarding; existing rows are untouched.
    enable_cash = Column(Boolean, nullable=False, default=True)
    enable_mercado_pago = Column(Boolean, nullable=False, default=False)
    enable_paypal = Column(Boolean, nullable=False, default=False)
    enable_credit_card = Column(Boolean, nullable=False, default=False)
    enable_debit_card = Column(Boolean, nullable=False, default=False)
    enable_bank_transfer = Column(Boolean, nullable=False, default=False)

    # Cancellation policies
    free_cancellation_hours = Column(Integer, nullable=False, default=48)
    cancellation_penalty_percentage = Column(Float, nullable=False, default=0.0)
    allow_cancellation_after_checkin = Column(Boolean, nullable=False, default=False)

    # OTA toggles
    enable_booking_sync = Column(Boolean, nullable=False, default=True)
    enable_expedia_sync = Column(Boolean, nullable=False, default=True)
    enable_despegar_sync = Column(Boolean, nullable=False, default=False)

    # Public API controls
    public_api_rate_limit_per_minute = Column(Integer, nullable=True)

    # Subscription / ownership
    owner_email = Column(String(200), nullable=True)
    subscription_active = Column(Boolean, nullable=False, default=True)
    analytics_ai_enabled = Column(Boolean, nullable=False, default=False)

    # Check-in policies
    require_document_for_checkin = Column(Boolean, nullable=False, default=True)
    require_terms_acceptance = Column(Boolean, nullable=False, default=True)

    # General
    hotel_name = Column(String(200), nullable=False, default="Mi Hotel")
    # Nullable by design: floor preference is used only when the hotel has
    # explicitly confirmed that it has no elevator.
    has_elevator = Column(Boolean, nullable=True)
    # Informational fiscal issuer profile. It is deliberately separate from
    # electronic invoicing; these values never imply an ARCA-issued document.
    fiscal_legal_name = Column(String(200), nullable=True)
    fiscal_tax_id = Column(String(20), nullable=True)
    fiscal_vat_condition = Column(String(40), nullable=True)
    fiscal_address = Column(String(300), nullable=True)
    fiscal_point_of_sale = Column(Integer, nullable=True)
    hotel_timezone = Column(String(100), nullable=False, default="America/Argentina/Buenos_Aires")
    default_currency = Column(String(3), nullable=False, default="ARS")
    # Global market reference for non-USD currencies. USD uses the selected
    # market and Compra/Venta side for each conversion direction below.
    fx_conversion_rate_type = Column(
        String(20), nullable=False, default="oficial", server_default=text("'oficial'")
    )
    # USD market sources are independently selectable for each conversion
    # direction. The global market above remains the reference for other
    # currencies and for legacy reporting.
    fx_usd_to_ars_rate_type = Column(
        String(20), nullable=False, default="oficial", server_default=text("'oficial'")
    )
    fx_ars_to_usd_rate_type = Column(
        String(20), nullable=False, default="oficial", server_default=text("'oficial'")
    )
    # Select the DolarAPI side for each conversion direction. These defaults
    # preserve the user-confirmed local behavior while keeping direction
    # choices independently configurable by the hotel owner.
    fx_usd_to_ars_rate_side = Column(
        String(10), nullable=False, default="venta", server_default=text("'venta'")
    )
    fx_ars_to_usd_rate_side = Column(
        String(10), nullable=False, default="venta", server_default=text("'venta'")
    )
    # Policy selected by the hotel for converting foreign tender amounts.
    fx_rounding_policy = Column(
        String(24), nullable=False, default="keep_remainder", server_default=text("'keep_remainder'")
    )
    # Quotes exposed for operator comparison. Selection never rewrites a
    # reservation's stored price or FX snapshot.
    fx_display_rate_types = Column(
        JSON,
        nullable=False,
        default=lambda: ["oficial"],
        server_default=text("'[\"oficial\"]'"),
    )
    check_in_time = Column(String(5), nullable=True)
    check_out_time = Column(String(5), nullable=True)
    manual_rate_min_adjustment_pct = Column(Numeric(7, 2), nullable=True)
    manual_rate_max_adjustment_pct = Column(Numeric(7, 2), nullable=True)

    # Experimental recommendation-only tariff engine. New hotels remain
    # opted out until an owner enables recommendations; its pilot thresholds
    # are explicit and configurable per hotel.
    tariff_recommendations_enabled = Column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    tariff_high_occupancy_pct = Column(
        Numeric(5, 2), nullable=False, default=80, server_default=text("80")
    )
    tariff_low_occupancy_pct = Column(
        Numeric(5, 2), nullable=False, default=40, server_default=text("40")
    )
    tariff_pickup_change_pct = Column(
        Numeric(6, 2), nullable=False, default=20, server_default=text("20")
    )
    tariff_max_step_pct = Column(
        Numeric(5, 2), nullable=False, default=5, server_default=text("5")
    )

    # Identity fields collected by onboarding and edited in Settings.
    languages = Column(JSON, nullable=False, default=lambda: ["es"])
    jurisdiction_code = Column(String(3), nullable=False, default="AR")

    # Frontend interface locale (distinct from `languages`, which is the
    # languages the hotel staff speaks to guests).
    interface_language = Column(String(2), nullable=False, default="es")

    # Operations / availability. This is a real policy consumed by reservation
    # creation; unlike the retired scaffolding below it has an operator surface.
    allow_overbooking = Column(Boolean, nullable=False, default=False)

    # No-show policy
    no_show_cutoff_hours = Column(Integer, nullable=False, default=24)

    # Dedicated authority for the operational report recipient list. Other
    # wizard input remains in onboarding_state and extra_policies as history.
    operational_report_recipients = Column(JSON, nullable=True)

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
