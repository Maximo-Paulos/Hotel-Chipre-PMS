"""
Pydantic schemas for GuestRestriction (formal lodging-prohibition entity).
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.models.guest_restriction import GuestRestrictionStatusEnum


class GuestRestrictionOverrideRequest(BaseModel):
    """Carried on reservation/checkin/quote requests to authorize bypassing
    an active restriction. The reason is mandatory and audited -- it must
    never be whitespace-only."""

    restriction_id: int
    reason: str = Field(..., min_length=1, max_length=500)

    @field_validator("reason")
    @classmethod
    def _reason_must_not_be_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("reason no puede estar vacío")
        return cleaned


class GuestRestrictionCreate(BaseModel):
    reason: str = Field(..., min_length=1, max_length=500)
    detail: Optional[str] = Field(default=None, max_length=2000)
    valid_until: Optional[datetime] = None

    @field_validator("reason")
    @classmethod
    def _reason_must_not_be_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("reason no puede estar vacío")
        return cleaned


class GuestRestrictionResolveRequest(BaseModel):
    resolution_note: Optional[str] = Field(default=None, max_length=2000)


class GuestRestrictionRead(BaseModel):
    id: int
    hotel_id: int
    guest_id: int
    status: GuestRestrictionStatusEnum
    reason: str
    detail: Optional[str] = None
    valid_until: Optional[datetime] = None
    created_by_user_id: Optional[int] = None
    created_at: datetime
    resolved_by_user_id: Optional[int] = None
    resolved_at: Optional[datetime] = None
    resolution_note: Optional[str] = None
    legacy_guest_tag_id: Optional[int] = None

    model_config = {"from_attributes": True}
