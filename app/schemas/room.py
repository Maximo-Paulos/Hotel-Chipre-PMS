"""
Pydantic schemas for Room and RoomCategory.
"""
from pydantic import BaseModel, Field
from typing import Optional
from app.models.room import RoomStatusEnum


# ── RoomCategory ──

class RoomCategoryBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    code: str = Field(..., min_length=1, max_length=20)
    description: Optional[str] = None
    base_price_per_night: float = Field(..., gt=0)
    max_occupancy: int = Field(..., gt=0)
    amenities: Optional[str] = None


class RoomCategoryCreate(RoomCategoryBase):
    pass


class RoomCategoryRead(RoomCategoryBase):
    id: int
    model_config = {"from_attributes": True}


# ── Room ──

class RoomBase(BaseModel):
    room_number: str = Field(..., min_length=1, max_length=10)
    floor: int = Field(default=1, ge=0)
    category_id: int
    status: RoomStatusEnum = RoomStatusEnum.AVAILABLE
    is_active: bool = True
    notes: Optional[str] = None


class RoomCreate(RoomBase):
    pass


class RoomRead(RoomBase):
    id: int
    category: Optional[RoomCategoryRead] = None
    model_config = {"from_attributes": True}


# ── Category Pricing ──

class CategoryPricingSchema(BaseModel):
    price_cash: Optional[float] = None
    price_transfer: Optional[float] = None
    price_mercadopago: Optional[float] = None
    price_paypal: Optional[float] = None
    price_credit_card: Optional[float] = None
    price_debit_card: Optional[float] = None
    price_booking: Optional[float] = None
    price_expedia: Optional[float] = None


class CategoryPricingRead(CategoryPricingSchema):
    category_id: int
    model_config = {"from_attributes": True}

    model_config = {"from_attributes": True}
