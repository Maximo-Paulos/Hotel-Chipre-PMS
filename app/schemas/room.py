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

# Updates for editing categories
class RoomCategoryUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    code: Optional[str] = Field(default=None, min_length=1, max_length=20)
    description: Optional[str] = None
    base_price_per_night: Optional[float] = Field(default=None, gt=0)
    max_occupancy: Optional[int] = Field(default=None, gt=0)
    amenities: Optional[str] = None


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


class RoomUpdate(BaseModel):
    room_number: Optional[str] = Field(default=None, min_length=1, max_length=10)
    floor: Optional[int] = Field(default=None, ge=0)
    category_id: Optional[int] = None
    status: Optional[RoomStatusEnum] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = None


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

# ── Housekeeping responses ──
class RoomStatusUpdateResponse(BaseModel):
    room: RoomRead
    reallocation: Optional[dict] = None
