"""Validated payment-surcharge quote contracts."""

from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from app.models.transaction import PaymentMethodEnum
from app.services.fx_service import SUPPORTED_CONVERSION_CURRENCIES


class PaymentSurchargeQuoteRequest(BaseModel):
    reservation_id: int = Field(..., gt=0)
    payment_method: PaymentMethodEnum
    currency_code: str = Field(..., min_length=3, max_length=3)
    # Omit to quote the largest exact tender amount that does not exceed the
    # remaining reservation balance. A provided amount is in tender currency.
    base_amount: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)

    @field_validator("currency_code")
    @classmethod
    def normalize_currency_code(cls, value: str) -> str:
        normalized = value.strip().upper()
        if normalized not in SUPPORTED_CONVERSION_CURRENCIES:
            raise ValueError("La moneda debe ser ARS, USD, EUR, BRL, CLP o UYU.")
        return normalized


class PaymentSurchargeQuoteRead(BaseModel):
    reservation_id: int
    reservation_currency_code: str
    reservation_balance: Decimal
    applied_amount: Decimal
    remaining_balance: Decimal
    payment_method: PaymentMethodEnum
    currency_code: str
    base_amount: Decimal
    surcharge_type: str | None
    surcharge_value: Decimal | None
    surcharge_currency_code: str
    surcharge_amount: Decimal
    final_amount: Decimal
    surcharge_fx_rate: Decimal | None
    surcharge_fx_quote_details: dict | None
    fx_rate_snapshot: float | None
    fx_quote_details: dict | None
    cash_tender_rounding_policy: str | None
    cash_tender_suggestion: Decimal | None
    cash_tender_suggestion_difference: Decimal
    payment_quote_token: str
