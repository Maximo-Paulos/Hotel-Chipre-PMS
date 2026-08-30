"""Pydantic schemas for a guest's room-rejection lifecycle."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.models.guest_room_avoidance import GuestRoomAvoidanceStatusEnum


class GuestRoomAvoidanceResolveRequest(BaseModel):
    resolution_note: str = Field(..., min_length=1, max_length=2000)

    @field_validator("resolution_note")
    @classmethod
    def _resolution_note_must_not_be_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("resolution_note no puede estar vacío")
        return cleaned


class GuestRoomAvoidanceRead(BaseModel):
    id: int
    hotel_id: int
    guest_id: int
    room_id: int
    status: GuestRoomAvoidanceStatusEnum
    source_move_event_id: int | None = None
    reason: str | None = None
    created_by_user_id: int | None = None
    created_at: datetime
    resolved_by_user_id: int | None = None
    resolved_at: datetime | None = None
    resolution_note: str | None = None

    model_config = {"from_attributes": True}
