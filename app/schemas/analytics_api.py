from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.models.analytics import RoomStateEventReasonCodeEnum, RoomStateEventTypeEnum
from app.models.reservation import ReservationChannelCodeEnum


class CompanyBase(BaseModel):
    legal_name: str = Field(..., min_length=1, max_length=200)
    display_name: str = Field(..., min_length=1, max_length=200)
    tax_id: str | None = Field(default=None, max_length=50)
    country_code: str | None = Field(default=None, min_length=2, max_length=2)
    notes: str | None = None

    @field_validator("tax_id", "country_code")
    @classmethod
    def _strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @field_validator("country_code")
    @classmethod
    def _normalize_country_code(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip().upper()


class CompanyCreate(CompanyBase):
    pass


class CompanyUpdate(BaseModel):
    legal_name: str | None = Field(default=None, min_length=1, max_length=200)
    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    tax_id: str | None = Field(default=None, max_length=50)
    country_code: str | None = Field(default=None, min_length=2, max_length=2)
    notes: str | None = None

    @field_validator("tax_id", "country_code")
    @classmethod
    def _strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @field_validator("country_code")
    @classmethod
    def _normalize_country_code(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip().upper()


class CompanyRead(CompanyBase):
    id: int
    hotel_id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    deactivated_at: datetime | None = None
    deactivated_by_user_id: int | None = None

    model_config = {"from_attributes": True}


class AnalyticsAlertSettingsRead(BaseModel):
    hotel_id: int
    cancellation_rate_threshold_pct: float
    commission_gap_threshold_pct: float
    subutilization_threshold_pct: float
    pickup_drop_threshold_pct: float
    updated_by_user_id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AnalyticsAlertSettingsUpdate(BaseModel):
    cancellation_rate_threshold_pct: float | None = Field(default=None, ge=0, le=100)
    commission_gap_threshold_pct: float | None = Field(default=None, ge=0, le=100)
    subutilization_threshold_pct: float | None = Field(default=None, ge=0, le=100)
    pickup_drop_threshold_pct: float | None = Field(default=None, ge=0, le=100)


class AnalyticsAlertSnoozeCreate(BaseModel):
    scope_key: str = Field(default="global", min_length=1, max_length=120)
    duration_code: Literal["24h", "72h", "7d"] = Field(default="24h")


class AnalyticsAlertSnoozeRead(BaseModel):
    id: int
    hotel_id: int
    alert_code: str
    scope_key: str
    snooze_until: datetime
    created_by_user_id: int
    created_at: datetime

    model_config = {"from_attributes": True}


class AnalyticsAIConfigRead(BaseModel):
    hotel_id: int
    analytics_ai_enabled: bool
    provider: str
    runtime_healthy: bool
    effective_model: str | None = None
    quota_monthly: int | None = None
    quota_used: int
    quota_remaining: int | None = None


class AnalyticsAIConfigUpdate(BaseModel):
    analytics_ai_enabled: bool


class RoomStateEventBase(BaseModel):
    room_id: int
    event_type: RoomStateEventTypeEnum
    reason_code: RoomStateEventReasonCodeEnum
    reason_note: str | None = Field(default=None, max_length=500)
    started_at: datetime | None = None


class RoomStateEventCreate(RoomStateEventBase):
    pass


class RoomStateEventRead(RoomStateEventBase):
    id: int
    hotel_id: int
    ended_at: datetime | None = None
    created_by_user_id: int
    closed_by_user_id: int | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


AnalyticsExportEntityCode = Literal["home", "rooms", "room", "category", "segments", "company", "channels", "operations"]
AnalyticsExportCurrencyDisplay = Literal["ARS", "USD", "BOTH"]


class AnalyticsExportRequest(BaseModel):
    entity_code: AnalyticsExportEntityCode = Field(default="home")
    card_code: str | None = Field(default=None, max_length=60)
    date_from: date | None = None
    date_to: date | None = None
    compare_previous: bool = Field(default=True)
    compare_yoy: bool = Field(default=False)
    currency_display: AnalyticsExportCurrencyDisplay = Field(default="ARS")
    room_id: int | None = None
    category_id: int | None = None
    company_id: int | None = None

    @field_validator("card_code")
    @classmethod
    def _strip_card_code(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @field_validator("date_from", "date_to")
    @classmethod
    def _preserve_date(cls, value: date | None) -> date | None:
        return value

    @field_validator("currency_display")
    @classmethod
    def _normalize_currency_display(cls, value: str) -> str:
        return value.upper()


class AnalyticsExportJobRead(BaseModel):
    id: int
    hotel_id: int
    user_id: int
    entity_code: str
    card_code: str | None = None
    format: str
    currency_display: str
    date_from: date
    date_to: date
    compare_previous: bool
    compare_yoy: bool
    filters_json: str
    status: str
    file_path: str | None = None
    file_size_bytes: int | None = None
    sha256_hex: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    expires_at: datetime

    model_config = {"from_attributes": True}
