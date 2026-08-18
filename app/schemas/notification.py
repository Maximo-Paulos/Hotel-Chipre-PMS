"""Pydantic schemas for the notification backend (inbox, preferences, push
subscriptions, daily report schedule)."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.models.notification import NotificationSeverityEnum


class NotificationRead(BaseModel):
    id: int
    hotel_id: int
    recipient_user_id: int
    event_type: str
    severity: NotificationSeverityEnum
    title: str
    body: Optional[str] = None
    entity_type: Optional[str] = None
    entity_id: Optional[int] = None
    is_read: bool
    read_at: Optional[datetime] = None
    created_at: datetime
    expires_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class NotificationListResponse(BaseModel):
    items: list[NotificationRead]
    unread_count: int


class NotificationMarkReadRequest(BaseModel):
    read: bool = True


class PushSubscriptionRegisterRequest(BaseModel):
    endpoint: str = Field(..., min_length=1, max_length=2000)
    p256dh: str = Field(..., min_length=1, max_length=255)
    auth: str = Field(..., min_length=1, max_length=255)


class PushSubscriptionUnregisterRequest(BaseModel):
    endpoint: str = Field(..., min_length=1, max_length=2000)


class NotificationPreferenceRead(BaseModel):
    event_type: str
    in_app_enabled: bool
    push_enabled: bool
    email_enabled: bool
    quiet_hours_start: Optional[int] = None
    quiet_hours_end: Optional[int] = None

    model_config = {"from_attributes": True}


class NotificationPreferenceUpdate(BaseModel):
    event_type: str = Field(default="", max_length=100)
    in_app_enabled: Optional[bool] = None
    push_enabled: Optional[bool] = None
    email_enabled: Optional[bool] = None
    quiet_hours_start: Optional[int] = Field(default=None, ge=0, le=23)
    quiet_hours_end: Optional[int] = Field(default=None, ge=0, le=23)
    clear_quiet_hours: bool = False


class DailyReportScheduleRead(BaseModel):
    hotel_id: int
    hour: int
    recipient_user_ids: list[int]
    recipient_roles: list[str]
    channels: list[str]
    sections: list[str]
    enabled: bool


class DailyReportScheduleUpdate(BaseModel):
    hour: int = Field(default=7, ge=0, le=23)
    recipient_user_ids: list[int] = Field(default_factory=list)
    recipient_roles: list[str] = Field(default_factory=list)
    channels: list[str] = Field(default_factory=lambda: ["in_app"])
    sections: Optional[list[str]] = None
    enabled: bool = True

    @field_validator("channels")
    @classmethod
    def _channels_must_be_known(cls, value: list[str]) -> list[str]:
        allowed = {"in_app", "push", "email"}
        unknown = set(value) - allowed
        if unknown:
            raise ValueError(f"Unknown channel(s): {', '.join(sorted(unknown))}")
        return value
