"""API contracts for operational tasks and shift handoffs."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.operational_task import (
    OperationalTaskPriorityEnum,
    OperationalTaskStatusEnum,
    OperationalTaskTypeEnum,
    ShiftHandoffStatusEnum,
)


class OperationalTaskCreate(BaseModel):
    task_type: OperationalTaskTypeEnum = OperationalTaskTypeEnum.GENERAL
    priority: OperationalTaskPriorityEnum = OperationalTaskPriorityEnum.MEDIUM
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    room_id: int | None = Field(default=None, gt=0)
    reservation_id: int | None = Field(default=None, gt=0)
    room_block_id: int | None = Field(default=None, gt=0)
    assigned_to_user_id: int | None = Field(default=None, gt=0)
    due_at: datetime | None = None

    @field_validator("title")
    @classmethod
    def title_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("El título es obligatorio")
        return value


class OperationalTaskUpdate(BaseModel):
    client_version: int = Field(ge=0)
    status: OperationalTaskStatusEnum | None = None
    priority: OperationalTaskPriorityEnum | None = None
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    assigned_to_user_id: int | None = Field(default=None, gt=0)
    due_at: datetime | None = None
    comment: str | None = Field(default=None, max_length=2000)

    @field_validator("title", "comment")
    @classmethod
    def optional_text_not_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class OperationalTaskEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    from_status: str | None = None
    to_status: str
    actor_user_id: int | None = None
    comment: str | None = None
    created_at: datetime


class OperationalTaskRead(BaseModel):
    id: int
    hotel_id: int
    task_type: OperationalTaskTypeEnum
    status: OperationalTaskStatusEnum
    priority: OperationalTaskPriorityEnum
    title: str
    description: str | None = None
    room_id: int | None = None
    room_number: str | None = None
    reservation_id: int | None = None
    confirmation_code: str | None = None
    room_block_id: int | None = None
    assigned_to_user_id: int | None = None
    due_at: datetime | None = None
    created_by_user_id: int | None = None
    resolved_by_user_id: int | None = None
    resolved_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    version: int


class ShiftHandoffCreate(BaseModel):
    task_ids: list[int] = Field(min_length=1, max_length=100)
    notes: str | None = Field(default=None, max_length=5000)
    cash_close_report_id: int | None = Field(default=None, gt=0)


class ShiftHandoffRead(BaseModel):
    id: int
    hotel_id: int
    delivered_by_user_id: int | None = None
    received_by_user_id: int | None = None
    cash_close_report_id: int | None = None
    status: ShiftHandoffStatusEnum
    notes: str | None = None
    delivered_at: datetime
    acknowledged_at: datetime | None = None
    created_at: datetime
    version: int
    task_ids: list[int] = Field(default_factory=list)


class ShiftHandoffAcknowledge(BaseModel):
    client_version: int = Field(ge=0)
