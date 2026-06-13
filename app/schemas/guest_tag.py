from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.guest import GuestRatingEnum, GuestTagTypeEnum


class GuestTagCreate(BaseModel):
    tag_type: GuestTagTypeEnum
    note: str | None = Field(default=None, max_length=2000)
    expires_at: datetime | None = None


class GuestTagRead(BaseModel):
    id: int
    hotel_id: int
    guest_id: int
    tag_type: GuestTagTypeEnum
    note: str | None = None
    expires_at: datetime | None = None
    created_at: datetime
    created_by_user_id: int | None = None

    model_config = {"from_attributes": True}


class GuestRatingUpdate(BaseModel):
    rating: GuestRatingEnum


class GuestStaySummary(BaseModel):
    reservation_id: int
    confirmation_code: str
    status: Any
    check_in_date: date
    check_out_date: date
    room_id: int | None = None
    room_number: str | None = None
    notes: str | None = None


class GuestQuickProfileRead(BaseModel):
    guest: Any
    active_tags: list[GuestTagRead]
    last_stays: list[GuestStaySummary]
