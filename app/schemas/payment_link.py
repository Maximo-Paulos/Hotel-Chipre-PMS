"""Pydantic schemas for production payment links (reservation guest-facing)."""
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


class PaymentLinkCreate(BaseModel):
    reservation_id: int
    requested_amount: Decimal = Field(..., gt=Decimal("0"))
    recipient_email: EmailStr
    recipient_name: Optional[str] = None
    recipient_phone: Optional[str] = None
    currency: str = Field(default="ARS", min_length=3, max_length=3)
    provider: str = "mercado_pago"
    title: Optional[str] = None
    description: Optional[str] = None
    expires_at: Optional[datetime] = None

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("provider")
    @classmethod
    def normalize_provider(cls, value: str) -> str:
        return (value or "mercado_pago").strip().lower()


class PaymentLinkCancel(BaseModel):
    reason: Optional[str] = Field(default=None, max_length=255)


class PaymentLinkRead(BaseModel):
    id: int
    hotel_id: int
    reservation_id: int
    provider: str
    link_code: str
    requested_amount: Decimal
    collected_amount: Decimal
    currency: str
    recipient_email: str
    recipient_name: Optional[str] = None
    description: Optional[str] = None
    status: str
    external_reference: Optional[str] = None
    external_checkout_url: Optional[str] = None
    expires_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    first_payment_at: Optional[datetime] = None
    last_payment_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}
