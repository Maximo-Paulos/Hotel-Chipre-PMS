"""Public, redacted contracts for hotel security settings."""

from datetime import datetime

from pydantic import BaseModel, Field


class SecurityCurrentUserRead(BaseModel):
    id: int
    email: str
    role: str
    last_login: datetime | None = None
    token_version: int


class SecurityOverviewRead(BaseModel):
    hotel_id: int
    session_timeout_minutes: int
    active_members: int
    pending_invitations: int
    security_events_24h: int
    permission_denials_24h: int
    current_user: SecurityCurrentUserRead


class SecurityEventRead(BaseModel):
    id: int
    action: str
    actor_user_id: int | None = None
    resource_type: str | None = None
    resource_id: str | None = None
    created_at: datetime


class SecurityEventsRead(BaseModel):
    hotel_id: int
    events: list[SecurityEventRead] = Field(default_factory=list)


class RevokeAllSessionsResponse(BaseModel):
    revoked: bool
    user_id: int
    token_version: int
    reauthentication_required: bool
