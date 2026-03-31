"""
Pydantic schemas for Booking (lightweight wrapper around Reservation).
"""
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.models.reservation import ReservationStatusEnum, ReservationSourceEnum
from app.schemas.reservation import GuestSummary


class BookingCreate(BaseModel):
    """Input for creating a booking/reservation."""

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


class BookingUpdate(BaseModel):
    """Partial update payload for a booking."""

    room_id: Optional[int] = None
    category_id: Optional[int] = None
    check_in_date: Optional[date] = None
    check_out_date: Optional[date] = None
    num_adults: Optional[int] = Field(default=None, gt=0)
    num_children: Optional[int] = Field(default=None, ge=0)
    notes: Optional[str] = None
    status: Optional[ReservationStatusEnum] = None


class BookingRead(BaseModel):
    """Output representation of a booking."""

    id: int
    confirmation_code: str
    guest_id: int
    room_id: Optional[int]
    category_id: int
    check_in_date: date
    check_out_date: date
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
    actual_check_in: Optional[datetime] = None
    actual_check_out: Optional[datetime] = None
    balance_due: float = 0.0
    nights: int = 0
    additional_guests: list[GuestSummary] = []

    model_config = {"from_attributes": True}
