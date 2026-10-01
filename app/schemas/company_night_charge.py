from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


class CompanyNightChargeSetRequest(BaseModel):
    stay_dates: list[date] = Field(..., min_length=1, max_length=90)

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
    currency_code: str
    paid_amount: Decimal
    remaining_due: Decimal
    payment_pending: bool
    review_only: bool


class CompanyNightChargesSummaryRead(BaseModel):
    reservation_id: int
    company_id: int
    currency_code: str
    nightly_surcharge_amount: Decimal | None
    charges: list[CompanyNightChargeRead]
