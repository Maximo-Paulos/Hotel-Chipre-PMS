"""
Pydantic schemas for Booking (lightweight wrapper around Reservation).
"""
from datetime import date, datetime
from typing import Optional
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from app.models.reservation import ReservationStatusEnum, ReservationSourceEnum
from app.schemas.reservation import GuestSummary, _normalize_arrival_time_hint, _normalize_reservation_comment


class BookingCreate(BaseModel):
    """Input for creating a booking/reservation."""

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
    source: ReservationSourceEnum = ReservationSourceEnum.DIRECT
    external_id: Optional[str] = None
    sellable_product_id: Optional[int] = None
    rate_plan_id: Optional[int] = None
    tax_policy_id: Optional[int] = None
    pricing_channel_code: Optional[str] = Field(default=None, max_length=50)
    pricing_payment_method: Optional[str] = Field(default=None, max_length=30)
    guest_scope: str = Field(default="all", max_length=30)
    target_currency: Optional[str] = Field(default=None, min_length=3, max_length=3)
    total_amount: Optional[Decimal] = Field(default=None, ge=0)
    deposit_amount: Optional[Decimal] = Field(default=None, ge=0)
    quote_token: str = Field(..., min_length=20, max_length=24000)

    @field_validator("arrival_time_hint", mode="before")
    @classmethod
    def normalize_arrival_time_hint(cls, value: object) -> str | None:
        return _normalize_arrival_time_hint(value)

    @field_validator("reservation_comment", mode="before")
    @classmethod
    def normalize_reservation_comment(cls, value: object) -> str | None:
        return _normalize_reservation_comment(value)


class BookingUpdate(BaseModel):
    """Partial update payload for a booking."""

    room_id: Optional[int] = None
    category_id: Optional[int] = None
    check_in_date: Optional[date] = None
    check_out_date: Optional[date] = None
    num_adults: Optional[int] = Field(default=None, gt=0)
    num_children: Optional[int] = Field(default=None, ge=0)
    notes: Optional[str] = None
    arrival_time_hint: Optional[str] = None
    reservation_comment: Optional[str] = Field(default=None, max_length=1000)
    client_version: Optional[int] = None
    status: Optional[ReservationStatusEnum] = None

    @field_validator("arrival_time_hint", mode="before")
    @classmethod
    def normalize_arrival_time_hint(cls, value: object) -> str | None:
        return _normalize_arrival_time_hint(value)

    @field_validator("reservation_comment", mode="before")
    @classmethod
    def normalize_reservation_comment(cls, value: object) -> str | None:
        return _normalize_reservation_comment(value)


class BookingRead(BaseModel):
    """Output representation of a booking."""

    id: int
    confirmation_code: str
    guest_id: int
    room_id: Optional[int]
    category_id: int
    check_in_date: date
    check_out_date: date
    total_amount: float
    amount_paid: float
    deposit_amount: float
    status: ReservationStatusEnum
    source: ReservationSourceEnum
    external_id: Optional[str]
    num_adults: int
    num_children: int
    notes: Optional[str]
    arrival_time_hint: Optional[str] = None
    reservation_comment: Optional[str] = None
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    actual_check_in: Optional[datetime] = None
    actual_check_out: Optional[datetime] = None
    balance_due: float = 0.0
    nights: int = 0
    additional_guests: list[GuestSummary] = []

    model_config = {"from_attributes": True}
