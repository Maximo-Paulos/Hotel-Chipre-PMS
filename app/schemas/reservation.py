"""
Pydantic schemas for Reservation.
"""
import re

from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import date, datetime
from decimal import Decimal
from app.models.reservation import ReservationChannelCodeEnum, ReservationStatusEnum, ReservationSourceEnum
from app.schemas.payment_link import PaymentLinkCreate, PaymentLinkRead
from app.schemas.transaction import PaymentRequest, TransactionRead
from app.schemas.guest import GuestRead
from app.schemas.guest_restriction import GuestRestrictionOverrideRequest


_ARRIVAL_TIME_PATTERN = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")


def _normalize_arrival_time_hint(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("arrival_time_hint must use HH:MM format")
    cleaned = value.strip()
    if not cleaned:
        return None
    if not _ARRIVAL_TIME_PATTERN.fullmatch(cleaned):
        raise ValueError("arrival_time_hint must use HH:MM format")
    return cleaned


def _normalize_reservation_comment(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("reservation_comment must be text")
    cleaned = value.strip()
    return cleaned or None

class GuestSummary(BaseModel):
    id: int
    first_name: str
    last_name: str
    document_type: Optional[str] = None
    document_number: Optional[str] = None
    model_config = {"from_attributes": True}
class ReservationCreate(BaseModel):
    guest_id: int
    category_id: int
    room_id: Optional[int] = None
    sellable_product_id: Optional[int] = None
    rate_plan_id: Optional[int] = None
    tax_policy_id: Optional[int] = None
    company_id: Optional[int] = None
    check_in_date: date
    check_out_date: date
    num_adults: int = Field(default=1, gt=0)
    num_children: int = Field(default=0, ge=0)
    notes: Optional[str] = None
    arrival_time_hint: Optional[str] = None
    reservation_comment: Optional[str] = Field(default=None, max_length=1000)
    source: ReservationSourceEnum = ReservationSourceEnum.DIRECT
    channel_code: Optional[ReservationChannelCodeEnum] = None
    external_id: Optional[str] = None
    pricing_channel_code: Optional[str] = Field(default=None, max_length=50)
    pricing_payment_method: Optional[str] = Field(default=None, max_length=30)
    guest_scope: str = Field(default="all", max_length=30)
    target_currency: Optional[str] = Field(default=None, min_length=3, max_length=3)
    total_amount: Optional[Decimal] = Field(default=None, ge=0)
    deposit_amount: Optional[Decimal] = Field(default=None, ge=0)
    quote_token: Optional[str] = Field(default=None, min_length=20, max_length=24000)
    mobility_restriction: bool = False
    # Waitlist / overbooking (v72 §9)
    is_wait_listed: bool = False
    wait_list_reason: Optional[str] = Field(default=None, max_length=255)
    restriction_override: Optional[GuestRestrictionOverrideRequest] = None

    @field_validator("arrival_time_hint", mode="before")
    @classmethod
    def normalize_arrival_time_hint(cls, value: object) -> str | None:
        return _normalize_arrival_time_hint(value)

    @field_validator("reservation_comment", mode="before")
    @classmethod
    def normalize_reservation_comment(cls, value: object) -> str | None:
        return _normalize_reservation_comment(value)


class ReservationRead(BaseModel):
    id: int
    confirmation_code: str
    guest_id: int
    guest: Optional[GuestSummary] = None
    room_id: Optional[int]
    category_id: int
    company_id: Optional[int] = None
    sellable_product_id: Optional[int] = None
    rate_plan_id: Optional[int] = None
    tax_policy_id: Optional[int] = None
    check_in_date: date
    check_out_date: date
    actual_check_in: Optional[datetime]
    actual_check_out: Optional[datetime]
    total_amount: float
    amount_paid: float
    deposit_amount: float
    subtotal_amount: float = 0.0
    tax_amount: float = 0.0
    fee_amount: float = 0.0
    commission_amount: float = 0.0
    net_amount: float = 0.0
    currency_code: str = "ARS"
    fx_rate_snapshot: Optional[float] = None
    quoted_amount_ars: Optional[float] = None
    quoted_amount_usd: Optional[float] = None
    status: ReservationStatusEnum
    source: ReservationSourceEnum
    source_provider_code: Optional[str] = None
    external_id: Optional[str]
    external_confirmation_code: Optional[str] = None
    payment_collection_model: str = "hotel_collect"
    settlement_status: str = "not_applicable"
    num_adults: int
    num_children: int
    notes: Optional[str]
    arrival_time_hint: Optional[str] = None
    reservation_comment: Optional[str] = None
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    balance_due: float = 0.0
    nights: int = 0
    additional_guests: list[GuestSummary] = []
    allocation_status: str = "unassigned"
    requires_manual_review: bool = False
    mobility_restriction: bool = False
    is_wait_listed: bool = False
    wait_list_reason: Optional[str] = None
    version: int = 0

    model_config = {"from_attributes": True}


class ReservationUpdate(BaseModel):
    room_id: Optional[int] = None
    check_in_date: Optional[date] = None
    check_out_date: Optional[date] = None
    num_adults: Optional[int] = None
    num_children: Optional[int] = None
    notes: Optional[str] = None
    arrival_time_hint: Optional[str] = None
    reservation_comment: Optional[str] = Field(default=None, max_length=1000)
    mobility_restriction: Optional[bool] = None
    client_version: Optional[int] = None
    restriction_override: Optional[GuestRestrictionOverrideRequest] = None

    @field_validator("arrival_time_hint", mode="before")
    @classmethod
    def normalize_arrival_time_hint(cls, value: object) -> str | None:
        return _normalize_arrival_time_hint(value)

    @field_validator("reservation_comment", mode="before")
    @classmethod
    def normalize_reservation_comment(cls, value: object) -> str | None:
        return _normalize_reservation_comment(value)


class ReservationNoShowRequest(BaseModel):
    client_version: int
    notes: Optional[str] = Field(default=None, max_length=500)


class ReservationDateChangeRequest(BaseModel):
    check_in_date: date
    check_out_date: date
    client_version: int
    room_id: Optional[int] = None
    pricing_mode: str = Field(default="recalculate", pattern="^(recalculate|keep_current_total)$")
    reason: Optional[str] = Field(default=None, max_length=500)


class ReservationDateChangeResponse(BaseModel):
    original_reservation: ReservationRead
    reservation: ReservationRead
    recreated: bool
    status_transitioned: bool = False


class ReservationExtensionRequest(BaseModel):
    new_checkout_date: date
    client_version: int
    pricing_mode: str = Field(default="current_rate", pattern="^(current_rate|original_average)$")
    payment_action: str = Field(default="payment_link", pattern="^(immediate_payment|payment_link)$")
    immediate_payment: Optional[PaymentRequest] = None
    payment_link: Optional[PaymentLinkCreate] = None
    notes: Optional[str] = Field(default=None, max_length=500)


class ReservationExtensionResponse(BaseModel):
    reservation: ReservationRead
    extension_amount: Decimal
    transaction: Optional[TransactionRead] = None
    payment_link: Optional[PaymentLinkRead] = None
