"""
Pydantic schemas for HotelConfiguration.
"""
from typing import Literal, Optional, List
from datetime import datetime
from decimal import Decimal
import re

from pydantic import BaseModel, Field, field_validator, model_validator

from app.services.fx_service import OTHER_CURRENCIES
from app.services.timezones import normalize_timezone

SUPPORTED_CURRENCIES = {c.upper() for c in OTHER_CURRENCIES} | {"ARS", "USD"}
_LOCAL_TIME_PATTERN = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")


class HotelInterfaceLanguageRead(BaseModel):
    """The only hotel configuration exposed to every authenticated staff role."""

    interface_language: Literal["es", "en"]


def _normalize_currency(value: str) -> str:
    candidate = value.strip().upper()
    if candidate not in SUPPORTED_CURRENCIES:
        raise ValueError(f"Unsupported currency: {value}")
    return candidate


class HotelConfigRead(BaseModel):
    id: int
    deposit_percentage: float
    checkin_payment_policy: Literal["deposit", "total", "free"]
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
    check_in_time: Optional[str] = None
    check_out_time: Optional[str] = None
    manual_rate_min_adjustment_pct: Optional[Decimal] = None
    manual_rate_max_adjustment_pct: Optional[Decimal] = None
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
    checkin_payment_policy: Optional[Literal["deposit", "total", "free"]] = None
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
    check_in_time: Optional[str] = None
    check_out_time: Optional[str] = None
    manual_rate_min_adjustment_pct: Optional[Decimal] = Field(default=None, ge=-100, max_digits=7, decimal_places=2)
    manual_rate_max_adjustment_pct: Optional[Decimal] = Field(default=None, max_digits=7, decimal_places=2)
    default_currency: Optional[str] = None
    languages: Optional[List[str]] = None
    jurisdiction_code: Optional[str] = Field(default=None, min_length=2, max_length=3)
    interface_language: Optional[str] = None
    allow_overbooking: Optional[bool] = None
    no_show_cutoff_hours: Optional[int] = Field(default=None, ge=0, le=72)
    operational_report_recipients: Optional[List[str]] = None
    extra_policies: Optional[str] = None

    @field_validator("checkin_payment_policy")
    @classmethod
    def reject_null_checkin_payment_policy(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            raise ValueError("checkin_payment_policy cannot be null")
        return value

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

    @field_validator("check_in_time", "check_out_time", mode="before")
    @classmethod
    def normalize_hotel_local_time(cls, value: object) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("El horario debe tener formato HH:MM")
        candidate = value.strip()
        if not candidate:
            return None
        if not _LOCAL_TIME_PATTERN.fullmatch(candidate):
            raise ValueError("El horario debe tener formato HH:MM")
        return candidate

    @model_validator(mode="after")
    def validate_manual_rate_bounds(self):
        lower_supplied = "manual_rate_min_adjustment_pct" in self.model_fields_set
        upper_supplied = "manual_rate_max_adjustment_pct" in self.model_fields_set
        lower = self.manual_rate_min_adjustment_pct
        upper = self.manual_rate_max_adjustment_pct
        if lower is not None and lower < Decimal("-100"):
            raise ValueError("El límite inferior no puede ser menor a -100%")
        if lower_supplied and upper_supplied:
            if (lower is None) != (upper is None):
                raise ValueError("Configurá o limpiá juntos los dos límites de tarifa manual")
            if lower is not None and upper is not None and lower > upper:
                raise ValueError("El límite inferior no puede superar al límite superior")
        return self
