"""Schemas for manual OTA reservation entry."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


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
    pricing_channel_code: str | None = Field(default=None, max_length=50)
    guest_scope: str = Field(default="all", max_length=30)
    target_currency: str | None = Field(default=None, min_length=3, max_length=3)
    total_amount: Decimal | None = Field(default=None, ge=0)
    amount_paid: Decimal | None = Field(default=None, ge=0)
    payment_collection_model: str = Field(default="hotel_collect", max_length=40)
    settlement_status: str | None = Field(default=None, max_length=40)
