"""Schemas for hotel API keys and public booking endpoints."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, EmailStr, Field

from app.models.hotel_api_key import APIKeyPurposeEnum
from app.models.reservation import ReservationSourceEnum
from app.schemas.payment_link import PaymentLinkCreate, PaymentLinkRead
from app.schemas.reservation import ReservationRead


class HotelAPIKeyIssue(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    purpose: APIKeyPurposeEnum = APIKeyPurposeEnum.OTHER
    expires_at: Optional[datetime] = None


class HotelAPIKeyRead(BaseModel):
    id: int
    hotel_id: int
    name: str
    purpose: APIKeyPurposeEnum
    key_prefix: str
    is_active: bool
    last_used_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    created_at: datetime
    revoked_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class HotelAPIKeyIssued(HotelAPIKeyRead):
    secret: str


class PublicAvailabilityResponse(BaseModel):
    status: str
    category_id: int
    check_in_date: date
    check_out_date: date
    available_room_ids: list[int] = Field(default_factory=list)
    count: int


class PublicCategoryRead(BaseModel):
    id: int
    name: str
    code: str
    base_price_per_night: float
    max_occupancy: int
    description: Optional[str] = None

    model_config = {"from_attributes": True}


class PublicRateQuote(BaseModel):
    status: str
    category_id: int
    check_in_date: date
    check_out_date: date
    nights: int
    nightly_rate: float
    total_amount: float
    deposit_amount: float
    currency_code: str = "ARS"
    pricing_revision: str
    expires_at: datetime
    quote_token: str
    breakdown: list[dict] = Field(default_factory=list)


class PublicReservationCreate(BaseModel):
    guest_id: int
    category_id: int
    room_id: Optional[int] = None
    check_in_date: date
    check_out_date: date
    num_adults: int = Field(default=1, gt=0)
    num_children: int = Field(default=0, ge=0)
    notes: Optional[str] = None
    external_id: Optional[str] = None
    source: ReservationSourceEnum = ReservationSourceEnum.DIRECT
    quote_token: Optional[str] = Field(default=None, min_length=20, max_length=24000)


class PublicPaymentLinkCreate(BaseModel):
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

    def to_payment_link_create(self) -> PaymentLinkCreate:
        return PaymentLinkCreate(**self.model_dump())


class PublicReservationRead(ReservationRead):
    pass


class PublicReservationStatusRead(BaseModel):
    """Read-only reservation/payment status for the public API (v72 §16).

    Scoped to the API key's hotel. Exposes only the queried reservation's own
    state — never other guests' data.
    """
    id: int
    confirmation_code: str
    status: str
    check_in_date: date
    check_out_date: date
    total_amount: Decimal
    amount_paid: Decimal
    balance_due: Decimal
    currency_code: str = "ARS"
    payment_status: str
    settlement_status: str = "not_applicable"

    model_config = {"from_attributes": True}


class PublicPaymentLinkRead(PaymentLinkRead):
    pass
