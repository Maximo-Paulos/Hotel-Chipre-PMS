from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class MasterAdminLoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)
    pin: str = Field(min_length=6, max_length=32)


class MasterAdminUserPayload(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    role: str
    is_active: bool
    is_verified: bool


class MasterAdminLoginResponse(BaseModel):
    user: MasterAdminUserPayload
    csrf_token: str
    expires_at: datetime


class BillingPolicyUpdateRequest(BaseModel):
    enabled: bool = True
    allow_active: bool = True
    allow_trialing: bool = True
    allow_demo: bool = True
    allow_comped: bool = True
    allow_past_due_grace: bool = False
    exempt_hotel_ids: list[int] = Field(default_factory=list)
    notes: str | None = None


class BillingPolicyPayload(BillingPolicyUpdateRequest):
    policy_key: str = "default"
    updated_at: datetime | None = None
    updated_by_user_id: int | None = None


class EmailTestRequest(BaseModel):
    recipient: EmailStr
    subject: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=10_000)


class StripeWebhookConfigPayload(BaseModel):
    configured: bool
    secret_source: str
    tolerance_seconds: int

