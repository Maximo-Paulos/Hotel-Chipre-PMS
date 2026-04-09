"""
OTA domain models for channel mappings, sync orchestration and external links.

These models sit alongside the legacy OTA tables so we can migrate runtime logic
gradually without losing existing webhook flows.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
import enum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


class OTAConnectionStatusEnum(str, enum.Enum):
    PENDING = "pending"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    ERROR = "error"
    REVOKED = "revoked"


class OTAReservationLifecycleEnum(str, enum.Enum):
    NEW = "new"
    CONFIRMED = "confirmed"
    MODIFIED = "modified"
    CANCEL_REQUESTED = "cancel_requested"
    CANCELLED = "cancelled"
    HOLD = "hold"
    EXPIRED = "expired"
    MANUAL_RESOLUTION_REQUIRED = "manual_resolution_required"


class OTASyncJobStatusEnum(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    RETRYING = "retrying"
    CANCELLED = "cancelled"


class OTAProvider(Base):
    __tablename__ = "ota_providers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(50), nullable=False)
    name = Column(String(150), nullable=False)
    auth_type = Column(String(50), nullable=False, default="api_key")
    security_model = Column(String(50), nullable=False, default="shared_secret")
    api_base_url = Column(String(255), nullable=True)
    docs_url = Column(String(255), nullable=True)
    supported_features_json = Column(Text, nullable=True)
    requires_certification = Column(Boolean, nullable=False, default=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        UniqueConstraint("code", name="uq_ota_provider_code"),
    )


class OTAConnection(Base):
    __tablename__ = "ota_connections"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False)
    provider_id = Column(Integer, ForeignKey("ota_providers.id", ondelete="CASCADE"), nullable=False)
    environment = Column(String(20), nullable=False, default="sandbox")
    status = Column(
        Enum(OTAConnectionStatusEnum, name="ota_connection_status_enum", create_constraint=True),
        nullable=False,
        default=OTAConnectionStatusEnum.PENDING,
    )
    is_enabled = Column(Boolean, nullable=False, default=True)
    auth_config_encrypted = Column(Text, nullable=True)
    external_account_id = Column(String(120), nullable=True)
    external_property_id = Column(String(120), nullable=True)
    settings_json = Column(Text, nullable=True)
    last_health_check_at = Column(DateTime, nullable=True)
    last_sync_at = Column(DateTime, nullable=True)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    provider = relationship("OTAProvider", lazy="joined")

    __table_args__ = (
        UniqueConstraint(
            "hotel_id",
            "provider_id",
            "environment",
            name="uq_ota_connection_hotel_provider_env",
        ),
        Index("ix_ota_connections_hotel_id", "hotel_id"),
        Index("ix_ota_connections_provider_id", "provider_id"),
    )


class OTAPropertyMapping(Base):
    __tablename__ = "ota_property_mappings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False)
    provider_id = Column(Integer, ForeignKey("ota_providers.id", ondelete="CASCADE"), nullable=False)
    connection_id = Column(Integer, ForeignKey("ota_connections.id", ondelete="CASCADE"), nullable=True)
    external_property_id = Column(String(120), nullable=False)
    external_property_name = Column(String(200), nullable=True)
    is_primary = Column(Boolean, nullable=False, default=True)
    is_active = Column(Boolean, nullable=False, default=True)
    metadata_json = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    provider = relationship("OTAProvider", lazy="joined")
    connection = relationship("OTAConnection", lazy="joined")

    __table_args__ = (
        UniqueConstraint(
            "hotel_id",
            "provider_id",
            "external_property_id",
            name="uq_ota_property_mapping_hotel_provider_property",
        ),
        Index("ix_ota_property_mappings_hotel_id", "hotel_id"),
    )


class OTARoomMapping(Base):
    __tablename__ = "ota_room_mappings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False)
    provider_id = Column(Integer, ForeignKey("ota_providers.id", ondelete="CASCADE"), nullable=False)
    connection_id = Column(Integer, ForeignKey("ota_connections.id", ondelete="CASCADE"), nullable=True)
    sellable_product_id = Column(Integer, ForeignKey("sellable_products.id", ondelete="CASCADE"), nullable=True)
    room_category_id = Column(Integer, ForeignKey("room_categories.id", ondelete="CASCADE"), nullable=True)
    external_room_type_id = Column(String(120), nullable=False)
    external_room_type_name = Column(String(200), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    metadata_json = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    provider = relationship("OTAProvider", lazy="joined")
    connection = relationship("OTAConnection", lazy="joined")
    sellable_product = relationship("SellableProduct", lazy="joined")
    room_category = relationship("RoomCategory", lazy="joined")

    __table_args__ = (
        UniqueConstraint(
            "hotel_id",
            "provider_id",
            "external_room_type_id",
            name="uq_ota_room_mapping_hotel_provider_external_room",
        ),
        Index("ix_ota_room_mappings_hotel_id", "hotel_id"),
        Index("ix_ota_room_mappings_sellable_product_id", "sellable_product_id"),
    )


class OTARatePlanMapping(Base):
    __tablename__ = "ota_rate_plan_mappings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False)
    provider_id = Column(Integer, ForeignKey("ota_providers.id", ondelete="CASCADE"), nullable=False)
    connection_id = Column(Integer, ForeignKey("ota_connections.id", ondelete="CASCADE"), nullable=True)
    rate_plan_id = Column(Integer, ForeignKey("rate_plans.id", ondelete="CASCADE"), nullable=False)
    external_rate_plan_id = Column(String(120), nullable=False)
    external_rate_plan_name = Column(String(200), nullable=True)
    pricing_model_external = Column(String(50), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    metadata_json = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    provider = relationship("OTAProvider", lazy="joined")
    connection = relationship("OTAConnection", lazy="joined")
    rate_plan = relationship("RatePlan", lazy="joined")

    __table_args__ = (
        UniqueConstraint(
            "hotel_id",
            "provider_id",
            "external_rate_plan_id",
            name="uq_ota_rate_plan_mapping_hotel_provider_external_plan",
        ),
        UniqueConstraint(
            "hotel_id",
            "provider_id",
            "rate_plan_id",
            name="uq_ota_rate_plan_mapping_hotel_provider_internal_plan",
        ),
        Index("ix_ota_rate_plan_mappings_hotel_id", "hotel_id"),
    )


class OTAInventoryRule(Base):
    __tablename__ = "ota_inventory_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False)
    provider_id = Column(Integer, ForeignKey("ota_providers.id", ondelete="CASCADE"), nullable=False)
    rate_plan_id = Column(Integer, ForeignKey("rate_plans.id", ondelete="CASCADE"), nullable=False)
    stay_date = Column(Date, nullable=False)
    allotment = Column(Integer, nullable=True)
    stop_sell = Column(Boolean, nullable=False, default=False)
    closed_to_arrival = Column(Boolean, nullable=False, default=False)
    closed_to_departure = Column(Boolean, nullable=False, default=False)
    min_stay = Column(Integer, nullable=True)
    max_stay = Column(Integer, nullable=True)
    advance_purchase_min_days = Column(Integer, nullable=True)
    advance_purchase_max_days = Column(Integer, nullable=True)
    release_days = Column(Integer, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        CheckConstraint("allotment IS NULL OR allotment >= 0", name="ck_ota_inventory_rule_allotment_nonnegative"),
        CheckConstraint("min_stay IS NULL OR min_stay > 0", name="ck_ota_inventory_rule_min_stay_positive"),
        CheckConstraint(
            "max_stay IS NULL OR min_stay IS NULL OR max_stay >= min_stay",
            name="ck_ota_inventory_rule_stay_range",
        ),
        UniqueConstraint(
            "hotel_id",
            "provider_id",
            "rate_plan_id",
            "stay_date",
            name="uq_ota_inventory_rules_hotel_provider_plan_date",
        ),
        Index("ix_ota_inventory_rules_hotel_id", "hotel_id"),
    )


class OTAPriceRule(Base):
    __tablename__ = "ota_price_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False)
    provider_id = Column(Integer, ForeignKey("ota_providers.id", ondelete="CASCADE"), nullable=False)
    rate_plan_id = Column(Integer, ForeignKey("rate_plans.id", ondelete="CASCADE"), nullable=False)
    stay_date = Column(Date, nullable=False)
    occupancy = Column(Integer, nullable=True)
    currency_code = Column(String(3), nullable=False, default="ARS")
    gross_amount = Column(Float, nullable=False, default=0.0)
    net_amount = Column(Float, nullable=True)
    tax_amount = Column(Float, nullable=True)
    fee_amount = Column(Float, nullable=True)
    commission_pct = Column(Float, nullable=True)
    commission_amount = Column(Float, nullable=True)
    markup_pct = Column(Float, nullable=True)
    markup_amount = Column(Float, nullable=True)
    fx_rate_snapshot = Column(Float, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        CheckConstraint("gross_amount >= 0", name="ck_ota_price_rule_gross_nonnegative"),
        CheckConstraint("occupancy IS NULL OR occupancy > 0", name="ck_ota_price_rule_occupancy_positive"),
        UniqueConstraint(
            "hotel_id",
            "provider_id",
            "rate_plan_id",
            "stay_date",
            "occupancy",
            name="uq_ota_price_rules_hotel_provider_plan_date_occ",
        ),
        Index("ix_ota_price_rules_hotel_id", "hotel_id"),
    )


class OTACancellationRule(Base):
    __tablename__ = "ota_cancellation_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False)
    provider_id = Column(Integer, ForeignKey("ota_providers.id", ondelete="CASCADE"), nullable=False)
    rate_plan_id = Column(Integer, ForeignKey("rate_plans.id", ondelete="CASCADE"), nullable=False)
    refundable = Column(Boolean, nullable=False, default=True)
    free_cancel_until_hours = Column(Integer, nullable=True)
    penalty_type = Column(String(30), nullable=True)
    penalty_value = Column(Float, nullable=True)
    no_show_penalty_type = Column(String(30), nullable=True)
    no_show_penalty_value = Column(Float, nullable=True)
    policy_json = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        UniqueConstraint(
            "hotel_id",
            "provider_id",
            "rate_plan_id",
            name="uq_ota_cancellation_rules_hotel_provider_rate_plan",
        ),
        Index("ix_ota_cancellation_rules_hotel_id", "hotel_id"),
    )


class OTAReservationLink(Base):
    __tablename__ = "ota_reservation_links"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False)
    provider_id = Column(Integer, ForeignKey("ota_providers.id", ondelete="CASCADE"), nullable=False)
    connection_id = Column(Integer, ForeignKey("ota_connections.id", ondelete="SET NULL"), nullable=True)
    reservation_id = Column(Integer, ForeignKey("reservations.id", ondelete="SET NULL"), nullable=True)
    rate_plan_id = Column(Integer, ForeignKey("rate_plans.id", ondelete="SET NULL"), nullable=True)
    external_reservation_id = Column(String(120), nullable=False)
    external_confirmation_code = Column(String(120), nullable=True)
    provider_state = Column(
        Enum(OTAReservationLifecycleEnum, name="ota_reservation_lifecycle_enum", create_constraint=True),
        nullable=False,
        default=OTAReservationLifecycleEnum.NEW,
    )
    sync_status = Column(String(30), nullable=False, default="pending")
    currency_code = Column(String(3), nullable=True)
    gross_total = Column(Float, nullable=True)
    net_total = Column(Float, nullable=True)
    commission_total = Column(Float, nullable=True)
    hold_token = Column(String(200), nullable=True)
    hold_expires_at = Column(DateTime, nullable=True)
    raw_payload_encrypted = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    last_seen_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    provider = relationship("OTAProvider", lazy="joined")
    connection = relationship("OTAConnection", lazy="joined")
    reservation = relationship("Reservation", lazy="joined")
    rate_plan = relationship("RatePlan", lazy="joined")

    __table_args__ = (
        UniqueConstraint(
            "hotel_id",
            "provider_id",
            "external_reservation_id",
            name="uq_ota_reservation_link_hotel_provider_external",
        ),
        Index("ix_ota_reservation_links_hotel_id", "hotel_id"),
        Index("ix_ota_reservation_links_reservation_id", "reservation_id"),
    )


class OTASyncJob(Base):
    __tablename__ = "ota_sync_jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False)
    provider_id = Column(Integer, ForeignKey("ota_providers.id", ondelete="CASCADE"), nullable=False)
    connection_id = Column(Integer, ForeignKey("ota_connections.id", ondelete="SET NULL"), nullable=True)
    job_type = Column(String(50), nullable=False)
    scope_type = Column(String(50), nullable=True)
    scope_id = Column(String(120), nullable=True)
    status = Column(
        Enum(OTASyncJobStatusEnum, name="ota_sync_job_status_enum", create_constraint=True),
        nullable=False,
        default=OTASyncJobStatusEnum.PENDING,
    )
    attempt_count = Column(Integer, nullable=False, default=0)
    scheduled_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    provider = relationship("OTAProvider", lazy="joined")
    connection = relationship("OTAConnection", lazy="joined")
    events = relationship("OTASyncEvent", back_populates="job", lazy="selectin", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_ota_sync_jobs_hotel_id", "hotel_id"),
        Index("ix_ota_sync_jobs_status", "status"),
    )


class OTASyncEvent(Base):
    __tablename__ = "ota_sync_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(Integer, ForeignKey("ota_sync_jobs.id", ondelete="CASCADE"), nullable=False)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False)
    provider_id = Column(Integer, ForeignKey("ota_providers.id", ondelete="CASCADE"), nullable=False)
    event_type = Column(String(50), nullable=False)
    request_payload_encrypted = Column(Text, nullable=True)
    response_payload_encrypted = Column(Text, nullable=True)
    http_status = Column(Integer, nullable=True)
    result = Column(String(30), nullable=False, default="pending")
    message = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    job = relationship("OTASyncJob", back_populates="events", lazy="joined")
    provider = relationship("OTAProvider", lazy="joined")

    __table_args__ = (
        Index("ix_ota_sync_events_job_id", "job_id"),
        Index("ix_ota_sync_events_hotel_id", "hotel_id"),
    )


class OTACurrencyRate(Base):
    __tablename__ = "ota_currency_rates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False)
    provider_id = Column(Integer, ForeignKey("ota_providers.id", ondelete="SET NULL"), nullable=True)
    base_currency = Column(String(3), nullable=False)
    quote_currency = Column(String(3), nullable=False)
    rate = Column(Float, nullable=False)
    source = Column(String(50), nullable=False, default="manual")
    captured_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        CheckConstraint("rate > 0", name="ck_ota_currency_rates_rate_positive"),
        Index("ix_ota_currency_rates_hotel_id", "hotel_id"),
    )


class OTACommissionRule(Base):
    __tablename__ = "ota_commission_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False)
    provider_id = Column(Integer, ForeignKey("ota_providers.id", ondelete="CASCADE"), nullable=False)
    rate_plan_id = Column(Integer, ForeignKey("rate_plans.id", ondelete="SET NULL"), nullable=True)
    commission_pct = Column(Float, nullable=True)
    commission_fixed = Column(Float, nullable=True)
    payout_model = Column(String(50), nullable=False, default="merchant_of_record")
    effective_from = Column(Date, nullable=True)
    effective_to = Column(Date, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        CheckConstraint(
            "effective_to IS NULL OR effective_from IS NULL OR effective_to >= effective_from",
            name="ck_ota_commission_rules_effective_range",
        ),
        Index("ix_ota_commission_rules_hotel_id", "hotel_id"),
    )
