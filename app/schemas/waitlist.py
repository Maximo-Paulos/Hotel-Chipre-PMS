"""Schemas for hotel-scoped waitlist entries."""
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.models.waitlist import WaitlistStatusEnum
from app.schemas.reservation import ReservationRead


class WaitlistEntryCreate(BaseModel):
    guest_id: int
    category_id: int
    check_in_date: date
    check_out_date: date
    num_adults: int = Field(default=1, gt=0)
    num_children: int = Field(default=0, ge=0)
    priority: int = Field(default=100, ge=0)
    notes: Optional[str] = None
    contact_phone: Optional[str] = Field(default=None, max_length=50)


class WaitlistEntryUpdate(BaseModel):
    priority: Optional[int] = Field(default=None, ge=0)
    notes: Optional[str] = None
    contact_phone: Optional[str] = Field(default=None, max_length=50)


class WaitlistEntryRead(BaseModel):
    id: int
    hotel_id: int
    guest_id: int
    category_id: int
    promoted_reservation_id: Optional[int] = None
    check_in_date: date
    check_out_date: date
    num_adults: int
    num_children: int
    status: WaitlistStatusEnum
    priority: int
    notes: Optional[str] = None
    contact_phone: Optional[str] = None
    created_at: datetime
    promoted_at: Optional[datetime] = None
    expired_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class WaitlistPromoteRequest(BaseModel):
    room_id: Optional[int] = None
    notes: Optional[str] = None


class WaitlistPromoteResponse(BaseModel):
    waitlist_entry: WaitlistEntryRead
    reservation: ReservationRead
