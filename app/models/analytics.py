from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import Boolean, CHAR, Column, Date, DateTime, Enum, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint

from app.database import Base
from app.models.reservation import (
    ReservationChannelCodeEnum,
    ReservationGuestSegmentEnum,
    ReservationOutcomeEnum,
    ReservationStatusEnum,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AnalyticsExportFormatEnum(str, enum.Enum):
    XLSX = "xlsx"


class AnalyticsCurrencyDisplayEnum(str, enum.Enum):
    ARS = "ARS"
    USD = "USD"
    BOTH = "BOTH"


class AnalyticsExportStatusEnum(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"


class AnalyticsAlertSetting(Base):
    __tablename__ = "analytics_alert_settings"

    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id"), primary_key=True)
    cancellation_rate_threshold_pct = Column(Numeric(5, 2), nullable=False, default=15.00)
    commission_gap_threshold_pct = Column(Numeric(5, 2), nullable=False, default=25.00)
    subutilization_threshold_pct = Column(Numeric(5, 2), nullable=False, default=40.00)
    pickup_drop_threshold_pct = Column(Numeric(5, 2), nullable=False, default=20.00)
    updated_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)


class AnalyticsAlertSnooze(Base):
    __tablename__ = "analytics_alert_snoozes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id"), nullable=False)
    alert_code = Column(String(60), nullable=False)
    scope_key = Column(String(120), nullable=False)
    snooze_until = Column(DateTime(timezone=True), nullable=False)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    __table_args__ = (
        UniqueConstraint("hotel_id", "alert_code", "scope_key", name="uq_analytics_alert_snoozes_hotel_alert_scope"),
        Index("ix_analytics_alert_snoozes_hotel_until", "hotel_id", "snooze_until"),
        Index("ix_analytics_alert_snoozes_hotel_alert_scope", "hotel_id", "alert_code", "scope_key"),
    )


class AnalyticsExportJob(Base):
    __tablename__ = "analytics_export_jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    entity_code = Column(String(60), nullable=False)
    card_code = Column(String(60), nullable=True)
    format = Column(
        Enum(
            AnalyticsExportFormatEnum,
            name="analytics_export_format_enum",
            create_constraint=True,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
    )
    currency_display = Column(
        Enum(
            AnalyticsCurrencyDisplayEnum,
            name="analytics_currency_display_enum",
            create_constraint=True,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
    )
    date_from = Column(Date, nullable=False)
    date_to = Column(Date, nullable=False)
    compare_previous = Column(Boolean, nullable=False, default=False)
    compare_yoy = Column(Boolean, nullable=False, default=False)
    filters_json = Column(Text, nullable=False)
    status = Column(
        Enum(
            AnalyticsExportStatusEnum,
            name="analytics_export_status_enum",
            create_constraint=True,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
    )
    file_path = Column(String(500), nullable=True)
    file_size_bytes = Column(Integer, nullable=True)
    sha256_hex = Column(String(64), nullable=True)
    error_code = Column(String(80), nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)


class AnalyticsAIUsageMonthly(Base):
    __tablename__ = "analytics_ai_usage_monthly"

    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id"), primary_key=True)
    year_month = Column(CHAR(7), primary_key=True)
    calls_used = Column(Integer, nullable=False, default=0)
    last_call_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)


class HotelAuditEvent(Base):
    __tablename__ = "hotel_audit_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    action_code = Column(String(80), nullable=False)
    entity_type = Column(String(60), nullable=False)
    entity_id = Column(Integer, nullable=True)
    before_json = Column(Text, nullable=True)
    after_json = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    __table_args__ = (
        Index("ix_hotel_audit_events_hotel_created", "hotel_id", "created_at"),
        Index("ix_hotel_audit_events_hotel_action", "hotel_id", "action_code"),
        Index("ix_hotel_audit_events_entity", "entity_type", "entity_id"),
    )


class RoomStateEventTypeEnum(str, enum.Enum):
    OUT_OF_SERVICE = "out_of_service"
    MAINTENANCE = "maintenance"
    HOUSEKEEPING_BLOCK = "housekeeping_block"
    RENOVATION = "renovation"


class RoomStateEventReasonCodeEnum(str, enum.Enum):
    PLUMBING = "plumbing"
    ELECTRICAL = "electrical"
    FURNITURE = "furniture"
    DEEP_CLEAN = "deep_clean"
    INSPECTION = "inspection"
    OTHER = "other"


class RoomStateEvent(Base):
    __tablename__ = "room_state_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id"), nullable=False)
    room_id = Column(Integer, ForeignKey("rooms.id"), nullable=False)
    event_type = Column(
        Enum(
            RoomStateEventTypeEnum,
            name="room_state_event_type_enum",
            create_constraint=True,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
    )
    reason_code = Column(
        Enum(
            RoomStateEventReasonCodeEnum,
            name="room_state_event_reason_code_enum",
            create_constraint=True,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
    )
    reason_note = Column(String(500), nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=False)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    closed_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)


class FactReservationRowKindEnum(str, enum.Enum):
    OCCUPIED = "occupied"
    NO_SHOW_CHARGEABLE = "no_show_chargeable"
    NO_SHOW_WAIVED = "no_show_waived"


class FactRoomOccupancyStatusAtNightEnum(str, enum.Enum):
    AVAILABLE = "available"
    OCCUPIED = "occupied"
    OUT_OF_SERVICE = "out_of_service"
    MAINTENANCE = "maintenance"
    HOUSEKEEPING_BLOCK = "housekeeping_block"
    RENOVATION = "renovation"


class FactReservationDaily(Base):
    __tablename__ = "fact_reservation_daily"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id"), nullable=False)
    reservation_id = Column(Integer, ForeignKey("reservations.id"), nullable=False)
    stay_date = Column(Date, nullable=False)
    room_id = Column(Integer, ForeignKey("rooms.id"), nullable=True)
    category_id = Column(Integer, ForeignKey("room_categories.id"), nullable=False)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=True)
    channel_code = Column(
        Enum(
            ReservationChannelCodeEnum,
            name="fact_reservation_daily_channel_code_enum",
            create_constraint=True,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
    )
    guest_segment = Column(
        Enum(
            ReservationGuestSegmentEnum,
            name="fact_reservation_daily_guest_segment_enum",
            create_constraint=True,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
    )
    status = Column(
        Enum(
            ReservationStatusEnum,
            name="fact_reservation_daily_status_enum",
            create_constraint=True,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
    )
    outcome = Column(
        Enum(
            ReservationOutcomeEnum,
            name="fact_reservation_daily_outcome_enum",
            create_constraint=True,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
    )
    row_kind = Column(
        Enum(
            FactReservationRowKindEnum,
            name="fact_reservation_daily_row_kind_enum",
            create_constraint=True,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
    )
    occupied_night = Column(Boolean, nullable=False)
    chargeable_night = Column(Boolean, nullable=False)
    revenue_gross_ars = Column(Numeric(12, 2), nullable=False)
    revenue_gross_usd = Column(Numeric(12, 2), nullable=False)
    revenue_net_ars = Column(Numeric(12, 2), nullable=False)
    revenue_net_usd = Column(Numeric(12, 2), nullable=False)
    tax_ars = Column(Numeric(12, 2), nullable=False)
    tax_usd = Column(Numeric(12, 2), nullable=False)
    fee_ars = Column(Numeric(12, 2), nullable=False)
    fee_usd = Column(Numeric(12, 2), nullable=False)
    commission_ars = Column(Numeric(12, 2), nullable=False)
    commission_usd = Column(Numeric(12, 2), nullable=False)
    variable_cost_ars = Column(Numeric(12, 2), nullable=False)
    variable_cost_usd = Column(Numeric(12, 2), nullable=False)
    margin_operating_ars = Column(Numeric(12, 2), nullable=False)
    margin_operating_usd = Column(Numeric(12, 2), nullable=False)
    source_currency = Column(String(3), nullable=False)
    fx_rate_snapshot = Column(Numeric(12, 6), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)

    __table_args__ = (
        UniqueConstraint("hotel_id", "reservation_id", "stay_date", name="uq_fact_reservation_daily_hotel_reservation_date"),
        Index("ix_fact_reservation_daily_hotel_date", "hotel_id", "stay_date"),
        Index("ix_fact_reservation_daily_hotel_reservation", "hotel_id", "reservation_id"),
        Index("ix_fact_reservation_daily_hotel_category_date", "hotel_id", "category_id", "stay_date"),
        Index("ix_fact_reservation_daily_hotel_room_date", "hotel_id", "room_id", "stay_date"),
        Index("ix_fact_reservation_daily_hotel_company_date", "hotel_id", "company_id", "stay_date"),
        Index("ix_fact_reservation_daily_hotel_channel_date", "hotel_id", "channel_code", "stay_date"),
        Index("ix_fact_reservation_daily_hotel_segment_date", "hotel_id", "guest_segment", "stay_date"),
        Index("ix_fact_reservation_daily_hotel_outcome_date", "hotel_id", "outcome", "stay_date"),
    )


class FactRoomOccupancyDaily(Base):
    __tablename__ = "fact_room_occupancy_daily"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id"), nullable=False)
    room_id = Column(Integer, ForeignKey("rooms.id"), nullable=False)
    stay_date = Column(Date, nullable=False)
    category_id = Column(Integer, ForeignKey("room_categories.id"), nullable=False)
    status_at_night = Column(
        Enum(
            FactRoomOccupancyStatusAtNightEnum,
            name="fact_room_occupancy_daily_status_at_night_enum",
            create_constraint=True,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
    )
    is_sellable_night = Column(Boolean, nullable=False)
    is_occupied = Column(Boolean, nullable=False)
    reservation_id = Column(Integer, ForeignKey("reservations.id"), nullable=True)
    revenue_net_ars = Column(Numeric(12, 2), nullable=False)
    revenue_net_usd = Column(Numeric(12, 2), nullable=False)
    margin_operating_ars = Column(Numeric(12, 2), nullable=False)
    margin_operating_usd = Column(Numeric(12, 2), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)

    __table_args__ = (
        UniqueConstraint("hotel_id", "room_id", "stay_date", name="uq_fact_room_occupancy_daily_hotel_room_date"),
        Index("ix_fact_room_occupancy_daily_hotel_date", "hotel_id", "stay_date"),
        Index("ix_fact_room_occupancy_daily_hotel_room_date", "hotel_id", "room_id", "stay_date"),
        Index("ix_fact_room_occupancy_daily_hotel_category_date", "hotel_id", "category_id", "stay_date"),
        Index("ix_fact_room_occupancy_daily_hotel_status_date", "hotel_id", "status_at_night", "stay_date"),
    )
