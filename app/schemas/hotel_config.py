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
    fiscal_legal_name: Optional[str] = None
    fiscal_tax_id: Optional[str] = None
    fiscal_vat_condition: Optional[Literal[
        "responsable_inscripto", "monotributo", "exento", "consumidor_final", "no_responsable", "otro"
    ]] = None
    fiscal_address: Optional[str] = None
    fiscal_point_of_sale: Optional[int] = None
    hotel_timezone: str
    check_in_time: Optional[str] = None
    check_out_time: Optional[str] = None
    manual_rate_min_adjustment_pct: Optional[Decimal] = None
    manual_rate_max_adjustment_pct: Optional[Decimal] = None
    default_currency: str
    fx_conversion_rate_type: Literal["oficial", "blue"] = "oficial"
    fx_display_rate_types: List[Literal["oficial", "blue"]] = Field(default_factory=lambda: ["oficial"])
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
    fiscal_legal_name: Optional[str] = Field(default=None, max_length=200)
    fiscal_tax_id: Optional[str] = Field(default=None, max_length=20)
    fiscal_vat_condition: Optional[Literal[
        "responsable_inscripto", "monotributo", "exento", "consumidor_final", "no_responsable", "otro"
    ]] = None
    fiscal_address: Optional[str] = Field(default=None, max_length=300)
    fiscal_point_of_sale: Optional[int] = Field(default=None, ge=1, le=99999)
    hotel_timezone: Optional[str] = None
    check_in_time: Optional[str] = None
    check_out_time: Optional[str] = None
    manual_rate_min_adjustment_pct: Optional[Decimal] = Field(default=None, ge=-100, max_digits=7, decimal_places=2)
    manual_rate_max_adjustment_pct: Optional[Decimal] = Field(default=None, max_digits=7, decimal_places=2)
    default_currency: Optional[str] = None
    fx_conversion_rate_type: Optional[Literal["oficial", "blue"]] = None
    fx_display_rate_types: Optional[List[Literal["oficial", "blue"]]] = Field(default=None, min_length=1, max_length=2)
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

    @field_validator("fx_display_rate_types")
    @classmethod
    def normalize_fx_display_rate_types(
        cls,
        value: Optional[List[Literal["oficial", "blue"]]],
    ) -> Optional[List[Literal["oficial", "blue"]]]:
        if value is None:
            return None
        if len(set(value)) != len(value):
            raise ValueError("fx_display_rate_types no puede repetir cotizaciones")
        # Stable order makes responses and the settings control predictable.
        return [rate_type for rate_type in ("oficial", "blue") if rate_type in value]

    @field_validator("interface_language")
    @classmethod
    def normalize_interface_language(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        candidate = value.strip().lower()
        if candidate not in ("es", "en"):
            raise ValueError(f"Unsupported interface_language: {value}")
        return candidate

    @field_validator("fiscal_legal_name", "fiscal_tax_id", "fiscal_address", mode="before")
    @classmethod
    def normalize_fiscal_text(cls, value: object) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("Los datos fiscales deben ser texto")
        cleaned = value.strip()
        return cleaned or None

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
    def validate_configuration_consistency(self):
        if (self.jurisdiction_code or "AR").strip().upper() == "AR" and self.fiscal_tax_id:
            digits = re.sub(r"\D", "", self.fiscal_tax_id)
            if len(digits) != 11:
                raise ValueError("El CUIT debe tener 11 dígitos")
            weights = (5, 4, 3, 2, 7, 6, 5, 4, 3, 2)
            check = 11 - sum(int(digit) * weight for digit, weight in zip(digits[:10], weights)) % 11
            if check == 11:
                check = 0
            elif check == 10:
                check = 9
            if check != int(digits[-1]):
                raise ValueError("El dígito verificador del CUIT no es válido")
            self.fiscal_tax_id = digits
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
