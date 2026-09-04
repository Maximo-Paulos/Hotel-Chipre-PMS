"""Schemas for manual OTA reservation entry."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from app.schemas.reservation import _normalize_arrival_time_hint, _normalize_reservation_comment


class ManualOTAReservationCreate(BaseModel):
    guest_id: int
    category_id: int
    room_id: int | None = None
    sellable_product_id: int | None = None
    rate_plan_id: int | None = None
    tax_policy_id: int | None = None
    check_in_date: date
    check_out_date: date
    num_adults: int = Field(default=1, gt=0)
    num_children: int = Field(default=0, ge=0)
    channel: str = Field(min_length=1, max_length=50)
    external_id: str = Field(min_length=1, max_length=100)
    external_confirmation_code: str | None = Field(default=None, max_length=120)
    notes: str | None = None
    arrival_time_hint: str | None = None
    reservation_comment: str | None = Field(default=None, max_length=1000)
    pricing_channel_code: str | None = Field(default=None, max_length=50)
    guest_scope: str = Field(default="all", max_length=30)
    target_currency: str | None = Field(default=None, min_length=3, max_length=3)
    total_amount: Decimal | None = Field(default=None, ge=0)
    # Two independently-typed prices the receptionist can quote the guest
    # (not a conversion of one into the other -- see Reservation model).
    quoted_amount_ars: Decimal | None = Field(default=None, ge=0)
    quoted_amount_usd: Decimal | None = Field(default=None, ge=0)
    amount_paid: Decimal | None = Field(default=None, ge=0)
    payment_collection_model: str = Field(default="hotel_collect", max_length=40)
    settlement_status: str | None = Field(default=None, max_length=40)
    client_version: int | None = Field(default=None, ge=0)

    @field_validator("arrival_time_hint", mode="before")
    @classmethod
    def normalize_arrival_time_hint(cls, value: object) -> str | None:
        return _normalize_arrival_time_hint(value)

    @field_validator("reservation_comment", mode="before")
    @classmethod
    def normalize_reservation_comment(cls, value: object) -> str | None:
        return _normalize_reservation_comment(value)
