"""Validated contract for the fixed post-checkout housekeeping checklist."""
from datetime import datetime

from pydantic import BaseModel

from app.models.housekeeping_checklist import (
    HousekeepingChecklistItemCodeEnum,
    HousekeepingChecklistStatusEnum,
)
from app.models.room import RoomHousekeepingStatusEnum, RoomStatusEnum


class HousekeepingChecklistRoomRead(BaseModel):
    id: int
    number: str
    operational_status: RoomStatusEnum
    housekeeping_status: RoomHousekeepingStatusEnum


class HousekeepingChecklistItemRead(BaseModel):
    code: HousekeepingChecklistItemCodeEnum
    label: str
    completed: bool
    completed_at: datetime | None


class HousekeepingChecklistRead(BaseModel):
    checklist_id: int
    room: HousekeepingChecklistRoomRead
    status: HousekeepingChecklistStatusEnum
    version: int
    created_at: datetime
    completed_at: datetime | None
    items: list[HousekeepingChecklistItemRead]


class HousekeepingChecklistListRead(BaseModel):
    checklists: list[HousekeepingChecklistRead]
