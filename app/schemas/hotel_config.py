"""
Pydantic schemas for HotelConfiguration.
"""
from typing import Optional, List
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.services.fx_service import OTHER_CURRENCIES
from app.services.timezones import normalize_timezone

SUPPORTED_CURRENCIES = {c.upper() for c in OTHER_CURRENCIES} | {"ARS", "USD"}


def _normalize_currency(value: str) -> str:
    candidate = value.strip().upper()
    if candidate not in SUPPORTED_CURRENCIES:
        raise ValueError(f"Unsupported currency: {value}")
    return candidate


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
    enable_despegar_sync: bool
    require_document_for_checkin: bool
    require_terms_acceptance: bool
    hotel_name: str
    hotel_timezone: str
    default_currency: str
    languages: List[str]
    jurisdiction_code: str
    interface_language: str
    allow_overbooking: bool
    no_show_cutoff_hours: int
    operational_report_recipients: Optional[List[str]] = None
    extra_policies: Optional[str] = None
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
    enable_despegar_sync: Optional[bool] = None
    require_document_for_checkin: Optional[bool] = None
    require_terms_acceptance: Optional[bool] = None
    hotel_name: Optional[str] = None
    hotel_timezone: Optional[str] = None
    default_currency: Optional[str] = None
    languages: Optional[List[str]] = None
    jurisdiction_code: Optional[str] = Field(default=None, min_length=2, max_length=3)
    interface_language: Optional[str] = None
    allow_overbooking: Optional[bool] = None
    no_show_cutoff_hours: Optional[int] = Field(default=None, ge=0, le=72)
    operational_report_recipients: Optional[List[str]] = None
    extra_policies: Optional[str] = None

    @field_validator("hotel_timezone")
    @classmethod
    def normalize_hotel_timezone(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return normalize_timezone(value)

    @field_validator("default_currency")
    @classmethod
    def normalize_default_currency(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return _normalize_currency(value)

    @field_validator("interface_language")
    @classmethod
    def normalize_interface_language(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        candidate = value.strip().lower()
        if candidate not in ("es", "en"):
            raise ValueError(f"Unsupported interface_language: {value}")
        return candidate
