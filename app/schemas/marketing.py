"""Schemas for the public marketing site: pricing it renders, leads it captures."""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class PublicPricingPlan(BaseModel):
    code: str
    name: str
    # None means "no price published yet" and the site renders "Consultar".
    price_amount: Optional[Decimal] = None
    currency: Optional[str] = None
    billing_period: str = "month"
    headline: Optional[str] = None
    description: Optional[str] = None
    features: list[str] = Field(default_factory=list)
    room_limit: Optional[int] = None
    staff_limit: Optional[int] = None
    cta_label: Optional[str] = None
    cta_kind: str = "early_access"
    highlight: bool = False


class PublicPricingResponse(BaseModel):
    plans: list[PublicPricingPlan]
    trial_days: int


class LeadCreateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    email: EmailStr
    name: Optional[str] = Field(default=None, max_length=120)
    hotel_name: Optional[str] = Field(default=None, max_length=160)
    rooms_estimate: Optional[int] = Field(default=None, ge=1, le=100_000)
    city: Optional[str] = Field(default=None, max_length=120)
    phone: Optional[str] = Field(default=None, max_length=40)
    source: str = Field(default="landing", max_length=60)
    utm: Optional[dict[str, Any]] = None
    # Honeypot. Real people never see this field, so anything in it is a bot.
    company_website: Optional[str] = Field(default=None, max_length=200)

    @field_validator("utm")
    @classmethod
    def _cap_utm(cls, value: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
        if not value:
            return None
        # Keep an anonymous caller from using this as free storage.
        return {str(k)[:40]: str(v)[:200] for k, v in list(value.items())[:12]}


class LeadCreateResponse(BaseModel):
    status: str = "ok"


class MasterPricingPlanPayload(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    code: str = Field(max_length=40)
    name: str = Field(max_length=80)
    is_public: bool = True
    sort_order: int = 0
    price_amount: Optional[Decimal] = Field(default=None, ge=0)
    currency: Optional[str] = Field(default=None, max_length=3)
    billing_period: str = Field(default="month", max_length=20)
    headline: Optional[str] = Field(default=None, max_length=160)
    description: Optional[str] = None
    features: list[str] = Field(default_factory=list)
    room_limit: Optional[int] = Field(default=None, ge=0)
    staff_limit: Optional[int] = Field(default=None, ge=0)
    cta_label: Optional[str] = Field(default=None, max_length=60)
    cta_kind: str = Field(default="early_access", max_length=20)
    highlight: bool = False

    @field_validator("currency")
    @classmethod
    def _upper_currency(cls, value: Optional[str]) -> Optional[str]:
        return value.upper() if value else None


class MasterPricingPlanListPayload(BaseModel):
    plans: list[MasterPricingPlanPayload]


class MasterLeadPayload(BaseModel):
    id: int
    email: str
    name: Optional[str] = None
    hotel_name: Optional[str] = None
    rooms_estimate: Optional[int] = None
    city: Optional[str] = None
    phone: Optional[str] = None
    source: str
    created_at: str


class MasterLeadListPayload(BaseModel):
    items: list[MasterLeadPayload]
    total: int
