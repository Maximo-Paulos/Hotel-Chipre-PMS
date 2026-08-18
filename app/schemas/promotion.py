"""Pydantic schemas for the Promotion CRUD API and the simulation endpoint."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, model_validator

from app.models.promotion import PromotionBenefitTypeEnum, PromotionScopeEnum

WEEKDAY_NAMES = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


def weekdays_to_mask(weekdays: Optional[list[str]]) -> Optional[int]:
    if not weekdays:
        return None
    mask = 0
    for day in weekdays:
        key = day.strip().lower()[:3]
        if key not in WEEKDAY_NAMES:
            raise ValueError(f"Invalid weekday: {day}")
        mask |= 1 << WEEKDAY_NAMES.index(key)
    return mask


def mask_to_weekdays(mask: Optional[int]) -> Optional[list[str]]:
    if mask is None:
        return None
    return [WEEKDAY_NAMES[i] for i in range(7) if mask & (1 << i)]


class PromotionConditions(BaseModel):
    """Typed condition set. Every field is a wildcard when omitted/None."""

    booking_from: Optional[date] = None
    booking_to: Optional[date] = None
    stay_from: Optional[date] = None
    stay_to: Optional[date] = None
    min_nights: Optional[int] = Field(default=None, ge=1)
    max_nights: Optional[int] = Field(default=None, ge=1)
    weekdays: Optional[list[str]] = None  # subset of mon..sun
    category_id: Optional[int] = None
    room_id: Optional[int] = None
    sales_channel_code: Optional[str] = Field(default=None, max_length=50)
    guest_id: Optional[int] = None
    company_id: Optional[int] = None
    guest_tag_type: Optional[str] = Field(default=None, max_length=30)
    payment_currency: Optional[str] = Field(default=None, min_length=3, max_length=3)
    payment_method: Optional[str] = Field(default=None, max_length=50)

    @model_validator(mode="after")
    def _validate_ranges(self) -> "PromotionConditions":
        if self.booking_from and self.booking_to and self.booking_from > self.booking_to:
            raise ValueError("booking_from must be <= booking_to")
        if self.stay_from and self.stay_to and self.stay_from > self.stay_to:
            raise ValueError("stay_from must be <= stay_to")
        if self.min_nights and self.max_nights and self.min_nights > self.max_nights:
            raise ValueError("min_nights must be <= max_nights")
        return self


class PromotionCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=2000)
    benefit_type: PromotionBenefitTypeEnum
    benefit_value: Decimal = Field(..., ge=0)
    scope: PromotionScopeEnum = PromotionScopeEnum.FULL_STAY
    from_night_number: Optional[int] = Field(default=None, ge=1)
    priority: int = 0
    stackable: bool = False
    conditions: PromotionConditions = Field(default_factory=PromotionConditions)

    @model_validator(mode="after")
    def _validate_benefit_and_scope(self) -> "PromotionCreate":
        if self.benefit_type == PromotionBenefitTypeEnum.PERCENTAGE and self.benefit_value > 100:
            raise ValueError("Percentage benefit_value must be <= 100")
        if self.scope == PromotionScopeEnum.FROM_NIGHT_N and self.from_night_number is None:
            raise ValueError("from_night_number is required when scope is from_night_n")
        return self


class PromotionUpdate(BaseModel):
    """Editing a promotion creates a new immutable version. Every field is
    optional; omitted fields inherit the current version's value."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=2000)
    benefit_type: Optional[PromotionBenefitTypeEnum] = None
    benefit_value: Optional[Decimal] = Field(default=None, ge=0)
    scope: Optional[PromotionScopeEnum] = None
    from_night_number: Optional[int] = Field(default=None, ge=1)
    priority: Optional[int] = None
    stackable: Optional[bool] = None
    conditions: Optional[PromotionConditions] = None


class PromotionRead(BaseModel):
    id: int
    hotel_id: int
    code: str
    name: str
    description: Optional[str] = None
    benefit_type: PromotionBenefitTypeEnum
    benefit_value: Decimal
    scope: PromotionScopeEnum
    from_night_number: Optional[int] = None
    priority: int
    stackable: bool
    is_active: bool
    version: int
    previous_version_id: Optional[int] = None
    conditions: PromotionConditions
    created_at: datetime
    updated_at: datetime
    deactivated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}

    @classmethod
    def from_model(cls, promo) -> "PromotionRead":
        return cls(
            id=promo.id,
            hotel_id=promo.hotel_id,
            code=promo.code,
            name=promo.name,
            description=promo.description,
            benefit_type=promo.benefit_type,
            benefit_value=promo.benefit_value,
            scope=promo.scope,
            from_night_number=promo.from_night_number,
            priority=promo.priority,
            stackable=promo.stackable,
            is_active=promo.is_active,
            version=promo.version,
            previous_version_id=promo.previous_version_id,
            conditions=PromotionConditions(
                booking_from=promo.booking_from,
                booking_to=promo.booking_to,
                stay_from=promo.stay_from,
                stay_to=promo.stay_to,
                min_nights=promo.min_nights,
                max_nights=promo.max_nights,
                weekdays=mask_to_weekdays(promo.weekdays_mask),
                category_id=promo.category_id,
                room_id=promo.room_id,
                sales_channel_code=promo.sales_channel_code,
                guest_id=promo.guest_id,
                company_id=promo.company_id,
                guest_tag_type=promo.guest_tag_type,
                payment_currency=promo.payment_currency,
                payment_method=promo.payment_method,
            ),
            created_at=promo.created_at,
            updated_at=promo.updated_at,
            deactivated_at=promo.deactivated_at,
        )


class PromotionSimulateRequest(BaseModel):
    category_id: int
    check_in_date: date
    check_out_date: date
    payment_method: Optional[str] = None
    target_currency: Optional[str] = None
    sales_channel_code: Optional[str] = None
    guest_id: Optional[int] = None
    company_id: Optional[int] = None
    booking_date: Optional[date] = None
