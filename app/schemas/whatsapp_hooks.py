"""Schemas for WhatsApp bot public hooks."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.schemas.payment_link import PaymentLinkCreate, PaymentLinkRead
from app.schemas.hotel_api_key import PublicReservationRead
from app.schemas.reservation import _normalize_arrival_time_hint, _normalize_reservation_comment


class WhatsAppAvailabilityResponse(BaseModel):
    status: str
    category_id: int
    check_in_date: date
    check_out_date: date
    available_room_ids: list[int] = Field(default_factory=list)
    count: int


class WhatsAppPriceQuote(BaseModel):
    status: str
    category_id: int
    check_in_date: date
    check_out_date: date
    nights: int
    nightly_rate: float
    total_amount: float
    deposit_amount: float
    currency: str = "ARS"
    pricing_revision: str
    expires_at: datetime
    quote_token: str
    breakdown: list[dict[str, Any]] = Field(default_factory=list)


class WhatsAppOption(BaseModel):
    category_id: int
    category_name: str
    category_code: str
    available_room_ids: list[int] = Field(default_factory=list)
    count: int
    nights: int
    nightly_rate: float
    total_amount: float
    deposit_amount: float
    currency: str = "ARS"
    pricing_revision: str
    expires_at: datetime
    quote_token: str


class WhatsAppOptionsResponse(BaseModel):
    status: str
    check_in_date: date
    check_out_date: date
    options: list[WhatsAppOption] = Field(default_factory=list)


class WhatsAppReservationCreate(BaseModel):
    guest_id: int
    category_id: int
    room_id: Optional[int] = None
    check_in_date: date
    check_out_date: date
    num_adults: int = Field(default=1, gt=0)
    num_children: int = Field(default=0, ge=0)
    notes: Optional[str] = None
    arrival_time_hint: Optional[str] = None
    reservation_comment: Optional[str] = Field(default=None, max_length=1000)
    external_id: Optional[str] = None
    quote_token: Optional[str] = Field(default=None, min_length=20, max_length=24000)

    @field_validator("arrival_time_hint", mode="before")
    @classmethod
    def normalize_arrival_time_hint(cls, value: object) -> str | None:
        return _normalize_arrival_time_hint(value)

    @field_validator("reservation_comment", mode="before")
    @classmethod
    def normalize_reservation_comment(cls, value: object) -> str | None:
        return _normalize_reservation_comment(value)


class WhatsAppPaymentLinkCreate(BaseModel):
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

    def to_payment_link_create(self) -> PaymentLinkCreate:
        return PaymentLinkCreate(**self.model_dump())


class WhatsAppPaymentConfirmationResponse(BaseModel):
    status: str
    duplicate: bool
    event_id: int
    payment_id: int


class WhatsAppReservationRead(PublicReservationRead):
    pass


class WhatsAppPaymentLinkRead(PaymentLinkRead):
    pass
