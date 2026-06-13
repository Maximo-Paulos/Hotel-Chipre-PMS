from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class RoomMoveEventRead(BaseModel):
    id: int
    hotel_id: int
    reservation_id: int
    movement_group_id: int | None = None
    from_room_id: int | None = None
    to_room_id: int | None = None
    move_type: str
    reason_code: str | None = None
    trigger_event: str | None = None
    state_before: str | None = None
    state_after: str | None = None
    occurred_at: datetime
    created_by_user_id: int | None = None

    model_config = {"from_attributes": True}


class RoomMovementGroupRead(BaseModel):
    id: int
    hotel_id: int
    trigger_reason: str
    notes: str | None = None
    is_reverted: bool
    reverted_by_user_id: int | None = None
    reverted_at: datetime | None = None
    created_by_user_id: int | None = None
    created_at: datetime
    move_events: list[RoomMoveEventRead] = []

    model_config = {"from_attributes": True}
