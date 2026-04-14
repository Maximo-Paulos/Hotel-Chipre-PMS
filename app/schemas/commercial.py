"""
Schemas for the configurable commercial domain.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


class ProductRoomCompatibilityWrite(BaseModel):
    room_category_id: int
    compatibility_kind: str = Field(default="exact", min_length=1, max_length=30)
    priority: int = Field(default=100, ge=0)
    allows_auto_assignment: bool = True
    price_adjustment_type: Optional[str] = Field(default=None, max_length=30)
    price_adjustment_value: Optional[float] = None
    notes: Optional[str] = None


class ProductRoomCompatibilityRead(ProductRoomCompatibilityWrite):
    id: int
    model_config = {"from_attributes": True}


class SellableProductBase(BaseModel):
    primary_room_category_id: Optional[int] = None
    code: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=150)
    description: Optional[str] = None
    min_occupancy: int = Field(default=1, gt=0)
    max_occupancy: int = Field(default=1, gt=0)
    bathroom_type: Optional[str] = Field(default=None, max_length=40)
    board_type: Optional[str] = Field(default=None, max_length=40)
    gender_policy: Optional[str] = Field(default=None, max_length=40)
    accessibility_required: bool = False
    is_active: bool = True
    sort_order: int = 0
    metadata_json: Optional[str] = None


class SellableProductCreate(SellableProductBase):
    compatibilities: list[ProductRoomCompatibilityWrite] = Field(default_factory=list)


class SellableProductUpdate(BaseModel):
    primary_room_category_id: Optional[int] = None
    code: Optional[str] = Field(default=None, min_length=1, max_length=50)
    name: Optional[str] = Field(default=None, min_length=1, max_length=150)
    description: Optional[str] = None
    min_occupancy: Optional[int] = Field(default=None, gt=0)
    max_occupancy: Optional[int] = Field(default=None, gt=0)
    bathroom_type: Optional[str] = Field(default=None, max_length=40)
    board_type: Optional[str] = Field(default=None, max_length=40)
    gender_policy: Optional[str] = Field(default=None, max_length=40)
    accessibility_required: Optional[bool] = None
    is_active: Optional[bool] = None
    sort_order: Optional[int] = None
    metadata_json: Optional[str] = None
    compatibilities: Optional[list[ProductRoomCompatibilityWrite]] = None


class SellableProductRead(SellableProductBase):
    id: int
    compatibilities: list[ProductRoomCompatibilityRead] = Field(default_factory=list)
    model_config = {"from_attributes": True}


class RatePlanPriceWrite(BaseModel):
    sales_channel_code: Optional[str] = Field(default=None, max_length=50)
    occupancy: Optional[int] = Field(default=None, gt=0)
    currency_code: str = Field(default="ARS", min_length=3, max_length=3)
    base_amount: float = Field(..., ge=0.0)
    tax_inclusive: bool = True
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None
    is_active: bool = True


class RatePlanPriceRead(RatePlanPriceWrite):
    id: int
    model_config = {"from_attributes": True}


class RatePlanBase(BaseModel):
    sellable_product_id: int
    code: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=150)
    pricing_model: str = Field(default="fixed_per_night", min_length=1, max_length=50)
    cancellation_model: str = Field(default="flexible", min_length=1, max_length=50)
    currency_code: str = Field(default="ARS", min_length=3, max_length=3)
    is_refundable: bool = True
    is_active: bool = True
    min_nights_default: int = Field(default=1, gt=0)
    max_nights_default: Optional[int] = Field(default=None, gt=0)
    free_cancellation_hours: int = Field(default=0, ge=0)
    cancellation_penalty_type: Optional[str] = Field(default=None, max_length=30)
    cancellation_penalty_value: Optional[float] = None
    default_commission_pct: Optional[float] = None
    default_markup_pct: Optional[float] = None
    metadata_json: Optional[str] = None


class RatePlanCreate(RatePlanBase):
    prices: list[RatePlanPriceWrite] = Field(default_factory=list)


class RatePlanUpdate(BaseModel):
    sellable_product_id: Optional[int] = None
    code: Optional[str] = Field(default=None, min_length=1, max_length=50)
    name: Optional[str] = Field(default=None, min_length=1, max_length=150)
    pricing_model: Optional[str] = Field(default=None, min_length=1, max_length=50)
    cancellation_model: Optional[str] = Field(default=None, min_length=1, max_length=50)
    currency_code: Optional[str] = Field(default=None, min_length=3, max_length=3)
    is_refundable: Optional[bool] = None
    is_active: Optional[bool] = None
    min_nights_default: Optional[int] = Field(default=None, gt=0)
    max_nights_default: Optional[int] = Field(default=None, gt=0)
    free_cancellation_hours: Optional[int] = Field(default=None, ge=0)
    cancellation_penalty_type: Optional[str] = Field(default=None, max_length=30)
    cancellation_penalty_value: Optional[float] = None
    default_commission_pct: Optional[float] = None
    default_markup_pct: Optional[float] = None
    metadata_json: Optional[str] = None
    prices: Optional[list[RatePlanPriceWrite]] = None


class RatePlanRead(RatePlanBase):
    id: int
    prices: list[RatePlanPriceRead] = Field(default_factory=list)
    model_config = {"from_attributes": True}


class TaxRuleWrite(BaseModel):
    channel_code: Optional[str] = Field(default=None, max_length=50)
    guest_scope: str = Field(default="all", min_length=1, max_length=30)
    tax_code: str = Field(..., min_length=1, max_length=50)
    tax_name: str = Field(..., min_length=1, max_length=150)
    tax_type: str = Field(default="percentage", min_length=1, max_length=30)
    amount: float = 0.0
    currency_code: Optional[str] = Field(default=None, min_length=3, max_length=3)
    priority: int = Field(default=100, ge=0)
    applies_when_json: Optional[str] = None
    is_active: bool = True


class TaxRuleRead(TaxRuleWrite):
    id: int
    model_config = {"from_attributes": True}


class TaxPolicyBase(BaseModel):
    code: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=150)
    taxes_included: bool = True
    apply_vat_by_default: bool = True
    vat_rate: Optional[float] = None
    foreign_guest_tax_exempt: bool = False
    is_active: bool = True
    metadata_json: Optional[str] = None


class TaxPolicyCreate(TaxPolicyBase):
    rules: list[TaxRuleWrite] = Field(default_factory=list)


class TaxPolicyUpdate(BaseModel):
    code: Optional[str] = Field(default=None, min_length=1, max_length=50)
    name: Optional[str] = Field(default=None, min_length=1, max_length=150)
    taxes_included: Optional[bool] = None
    apply_vat_by_default: Optional[bool] = None
    vat_rate: Optional[float] = None
    foreign_guest_tax_exempt: Optional[bool] = None
    is_active: Optional[bool] = None
    metadata_json: Optional[str] = None
    rules: Optional[list[TaxRuleWrite]] = None


class TaxPolicyRead(TaxPolicyBase):
    id: int
    rules: list[TaxRuleRead] = Field(default_factory=list)
    model_config = {"from_attributes": True}


class FxPolicyBase(BaseModel):
    code: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=150)
    base_currency: str = Field(default="ARS", min_length=3, max_length=3)
    preferred_source: str = Field(default="official", min_length=1, max_length=50)
    preferred_side: str = Field(default="sell", min_length=1, max_length=20)
    spread_pct: float = 0.0
    rounding_mode: str = Field(default="half_up", min_length=1, max_length=30)
    is_active: bool = True
    metadata_json: Optional[str] = None


class FxPolicyCreate(FxPolicyBase):
    pass


class FxPolicyUpdate(BaseModel):
    code: Optional[str] = Field(default=None, min_length=1, max_length=50)
    name: Optional[str] = Field(default=None, min_length=1, max_length=150)
    base_currency: Optional[str] = Field(default=None, min_length=3, max_length=3)
    preferred_source: Optional[str] = Field(default=None, min_length=1, max_length=50)
    preferred_side: Optional[str] = Field(default=None, min_length=1, max_length=20)
    spread_pct: Optional[float] = None
    rounding_mode: Optional[str] = Field(default=None, min_length=1, max_length=30)
    is_active: Optional[bool] = None
    metadata_json: Optional[str] = None


class FxPolicyRead(FxPolicyBase):
    id: int
    model_config = {"from_attributes": True}
