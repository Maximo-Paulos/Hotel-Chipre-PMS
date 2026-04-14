"""
Pydantic schemas for Reservation.
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import date, datetime
from app.models.reservation import ReservationStatusEnum, ReservationSourceEnum
from app.schemas.guest import GuestRead

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
    check_in_date: date
    check_out_date: date
    num_adults: int = Field(default=1, gt=0)
    num_children: int = Field(default=0, ge=0)
    notes: Optional[str] = None
    source: ReservationSourceEnum = ReservationSourceEnum.DIRECT
    external_id: Optional[str] = None
    pricing_channel_code: Optional[str] = Field(default=None, max_length=50)
    guest_scope: str = Field(default="all", max_length=30)
    target_currency: Optional[str] = Field(default=None, min_length=3, max_length=3)


class ReservationRead(BaseModel):
    id: int
    confirmation_code: str
    guest_id: int
    guest: Optional[GuestSummary] = None
    room_id: Optional[int]
    category_id: int
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
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    balance_due: float = 0.0
    nights: int = 0
    additional_guests: list[GuestSummary] = []
    allocation_status: str = "unassigned"
    requires_manual_review: bool = False

    model_config = {"from_attributes": True}


class ReservationUpdate(BaseModel):
    room_id: Optional[int] = None
    check_in_date: Optional[date] = None
    check_out_date: Optional[date] = None
    num_adults: Optional[int] = None
    num_children: Optional[int] = None
    notes: Optional[str] = None
