"""
Pydantic schemas for the onboarding flow.
"""
from typing import List, Optional, Dict

from pydantic import BaseModel, Field

from app.schemas.room import RoomCategoryCreate


class OwnerPayload(BaseModel):
    name: str = Field(..., min_length=1, max_length=150)
    email: str = Field(..., min_length=3, max_length=200)
    phone: Optional[str] = Field(default=None, max_length=80)
    role: Optional[str] = Field(default=None, max_length=120)


class CategoriesPayload(BaseModel):
    categories: List[RoomCategoryCreate]


class RoomInput(BaseModel):
    room_number: str = Field(..., min_length=1, max_length=10)
    floor: int = Field(ge=0)
    category_code: str = Field(..., min_length=1, max_length=20)


class RoomsPayload(BaseModel):
    rooms: List[RoomInput]


class StaffMember(BaseModel):
    name: str = Field(..., min_length=1, max_length=150)
    role: Optional[str] = Field(default=None, max_length=120)
    email: Optional[str] = Field(default=None, max_length=200)
    phone: Optional[str] = Field(default=None, max_length=80)


class StaffPayload(BaseModel):
    staff: List[StaffMember]


class OnboardingStatus(BaseModel):
    hotel_id: int
    completed: bool
    steps: Dict[str, bool]
    missing_steps: List[str]
    counts: Dict[str, int]
    owner: Optional[dict] = None
