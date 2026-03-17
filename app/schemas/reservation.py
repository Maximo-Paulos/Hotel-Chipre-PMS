"""
Pydantic schemas for Reservation.
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import date, datetime
from app.models.reservation import ReservationStatusEnum, ReservationSourceEnum


class ReservationCreate(BaseModel):
    guest_id: int
    category_id: int
    room_id: Optional[int] = None
    check_in_date: date
    check_out_date: date
    num_adults: int = Field(default=1, gt=0)
    num_children: int = Field(default=0, ge=0)
    notes: Optional[str] = None
    source: ReservationSourceEnum = ReservationSourceEnum.DIRECT
    external_id: Optional[str] = None


class ReservationRead(BaseModel):
    id: int
    confirmation_code: str
    guest_id: int
    room_id: Optional[int]
    category_id: int
    check_in_date: date
    check_out_date: date
    actual_check_in: Optional[datetime]
    actual_check_out: Optional[datetime]
    total_amount: float
    amount_paid: float
    deposit_amount: float
    status: ReservationStatusEnum
    source: ReservationSourceEnum
    external_id: Optional[str]
    num_adults: int
    num_children: int
    notes: Optional[str]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    balance_due: float = 0.0
    nights: int = 0

    model_config = {"from_attributes": True}


class ReservationUpdate(BaseModel):
    room_id: Optional[int] = None
    check_in_date: Optional[date] = None
    check_out_date: Optional[date] = None
    num_adults: Optional[int] = None
    num_children: Optional[int] = None
    notes: Optional[str] = None
