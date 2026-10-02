from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


class CompanyNightlySurchargeRateCreate(BaseModel):
    effective_from: date
    amount: Decimal = Field(..., ge=0, max_digits=12, decimal_places=2)


class CompanyNightlySurchargeRateRead(BaseModel):
    id: int
    company_id: int
    effective_from: date
    amount: Decimal
    created_by_user_id: int | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class CompanyNightlySurchargeRatesRead(BaseModel):
    hotel_today: date
    rates: list[CompanyNightlySurchargeRateRead] = Field(default_factory=list)


class CompanyNightChargeAmountAdjustmentRequest(BaseModel):
    charge_id: int = Field(..., gt=0)
    new_amount: Decimal = Field(..., gt=0, max_digits=12, decimal_places=2)
    reason: str = Field(..., min_length=1, max_length=500)

    @field_validator("reason")
    @classmethod
    def clean_reason(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Indicá el motivo de la corrección")
        return cleaned


class CompanyNightChargeAmountAdjustmentSetRequest(BaseModel):
    items: list[CompanyNightChargeAmountAdjustmentRequest] = Field(..., min_length=1, max_length=90)

    @field_validator("items")
    @classmethod
    def unique_charges(cls, value: list[CompanyNightChargeAmountAdjustmentRequest]) -> list[CompanyNightChargeAmountAdjustmentRequest]:
        charge_ids = [item.charge_id for item in value]
        if len(charge_ids) != len(set(charge_ids)):
            raise ValueError("No repitas cargos en la selección")
        return value


class CompanyNightChargeAmountAdjustmentRead(BaseModel):
    id: int
    previous_amount: Decimal
    new_amount: Decimal
    delta_amount: Decimal
    reason: str
    created_by_user_id: int | None = None
    created_at: datetime


class CompanyNightChargeSetRequest(BaseModel):
    stay_dates: list[date] = Field(..., min_length=1, max_length=90)
    extra_person_count: int = Field(default=1, ge=1, le=99)

    @field_validator("stay_dates")
    @classmethod
    def unique_stay_dates(cls, value: list[date]) -> list[date]:
        if len(value) != len(set(value)):
            raise ValueError("No repitas noches en la selección")
        return sorted(value)


class CompanyNightChargeRead(BaseModel):
    id: int
    stay_date: date
    amount: Decimal
    unit_amount: Decimal
    quantity: int
    rate_effective_from: date | None = None
    currency_code: str
    paid_amount: Decimal
    remaining_due: Decimal
    payment_pending: bool
    review_only: bool
    adjustments: list[CompanyNightChargeAmountAdjustmentRead] = Field(default_factory=list)


class CompanyNightChargesSummaryRead(BaseModel):
    reservation_id: int
    company_id: int
    currency_code: str
    nightly_surcharge_amount: Decimal | None
    charges: list[CompanyNightChargeRead]
