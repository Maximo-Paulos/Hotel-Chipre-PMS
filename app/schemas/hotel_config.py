"""
Pydantic schemas for HotelConfiguration.
"""
from typing import Optional
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.services.timezones import normalize_timezone


class HotelConfigRead(BaseModel):
    id: int
    deposit_percentage: float
    enable_full_payment: bool
    enable_deposit_payment: bool
    enable_cash: bool
    enable_mercado_pago: bool
    enable_paypal: bool
    enable_credit_card: bool
    enable_debit_card: bool
    enable_bank_transfer: bool
    free_cancellation_hours: int
    cancellation_penalty_percentage: float
    allow_cancellation_after_checkin: bool
    enable_booking_sync: bool
    enable_expedia_sync: bool
    require_document_for_checkin: bool
    require_terms_acceptance: bool
    hotel_name: str
    hotel_timezone: str
    default_currency: str
    receptionist_view_past_days: int
    receptionist_view_future_days: int
    allow_revenue_manager: bool
    allow_revenue_receptionist: bool
    sync_interval_minutes: int
    safety_buffer_rooms: int
    allow_overbooking: bool
    max_overallocation_pct: float
    no_show_cutoff_hours: int
    ota_autopush_enabled: bool
    card_validation_enabled: bool
    payment_retry_attempts: int
    auth_amount_pct: float
    stop_sell_channels: Optional[str]
    event_notifications: Optional[str]
    extra_policies: Optional[str]
    updated_at: Optional[datetime]

    model_config = {"from_attributes": True}


class HotelConfigUpdate(BaseModel):
    deposit_percentage: Optional[float] = Field(default=None, ge=0, le=100)
    enable_full_payment: Optional[bool] = None
    enable_deposit_payment: Optional[bool] = None
    enable_cash: Optional[bool] = None
    enable_mercado_pago: Optional[bool] = None
    enable_paypal: Optional[bool] = None
    enable_credit_card: Optional[bool] = None
    enable_debit_card: Optional[bool] = None
    enable_bank_transfer: Optional[bool] = None
    free_cancellation_hours: Optional[int] = Field(default=None, ge=0)
    cancellation_penalty_percentage: Optional[float] = Field(default=None, ge=0, le=100)
    allow_cancellation_after_checkin: Optional[bool] = None
    enable_booking_sync: Optional[bool] = None
    enable_expedia_sync: Optional[bool] = None
    require_document_for_checkin: Optional[bool] = None
    require_terms_acceptance: Optional[bool] = None
    hotel_name: Optional[str] = None
    hotel_timezone: Optional[str] = None
    default_currency: Optional[str] = None
    receptionist_view_past_days: Optional[int] = Field(default=None, ge=0, le=365)
    receptionist_view_future_days: Optional[int] = Field(default=None, ge=0, le=365)
    allow_revenue_manager: Optional[bool] = None
    allow_revenue_receptionist: Optional[bool] = None
    sync_interval_minutes: Optional[int] = Field(default=None, ge=1, le=1440)
    safety_buffer_rooms: Optional[int] = Field(default=None, ge=0, le=50)
    allow_overbooking: Optional[bool] = None
    max_overallocation_pct: Optional[float] = Field(default=None, ge=0, le=100)
    no_show_cutoff_hours: Optional[int] = Field(default=None, ge=0, le=72)
    ota_autopush_enabled: Optional[bool] = None
    card_validation_enabled: Optional[bool] = None
    payment_retry_attempts: Optional[int] = Field(default=None, ge=0, le=10)
    auth_amount_pct: Optional[float] = Field(default=None, ge=0, le=100)
    stop_sell_channels: Optional[str] = None
    event_notifications: Optional[str] = None
    extra_policies: Optional[str] = None

    @field_validator("hotel_timezone")
    @classmethod
    def normalize_hotel_timezone(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return normalize_timezone(value)
