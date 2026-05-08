from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


class RateCalendarChannelPrice(BaseModel):
    rate_plan_id: int
    rate_plan_code: str
    rate_plan_name: str
    base_amount: float
    sales_channel_code: Optional[str] = None
    currency_code: str


class RateCalendarChannelRestrictions(BaseModel):
    min_stay: Optional[int] = None
    max_stay: Optional[int] = None
    closed_to_arrival: bool = False
    closed_to_departure: bool = False
    allotment: Optional[int] = None
    stop_sell: bool = False


class RateCalendarChannelDay(BaseModel):
    provider_code: str
    provider_label: str
    currency_code: str
    missing_mapping: bool
    prices: list[RateCalendarChannelPrice] = Field(default_factory=list)
    restrictions: RateCalendarChannelRestrictions


class RateCalendarDay(BaseModel):
    date: date
    is_today: bool
    total_rooms: int
    reserved: int
    blocked: int
    for_sale: int
    status: str
    occupancy_pct: int
    channels: list[RateCalendarChannelDay] = Field(default_factory=list)


class RateCalendarMeta(BaseModel):
    category_id: int
    category_name: str
    category_code: str
    total_rooms: int
    hotel_currency_code: str
    date_from: date
    date_to: date


class RateCalendarResponse(BaseModel):
    meta: RateCalendarMeta
    days: list[RateCalendarDay] = Field(default_factory=list)
