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


class MasterAdminSessionResponse(BaseModel):
    user: MasterAdminUserPayload
    csrf_token: str


class BillingPolicyUpdateRequest(BaseModel):
    enabled: bool = True
    allow_active: bool = True
    allow_trialing: bool = True
    exempt_hotel_ids: list[int] = Field(default_factory=list)
    exempt_user_ids: list[int] = Field(default_factory=list)
    notes: str | None = None


class BillingPolicyPayload(BillingPolicyUpdateRequest):
    policy_key: str = "default"
    updated_at: datetime | None = None
    updated_by_user_id: int | None = None


class EmailTestRequest(BaseModel):
    recipient: EmailStr
    subject: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=10_000)


class MasterEmailStatusPayload(BaseModel):
    configured: bool
    status: str
    provider: str
    sender_email: EmailStr | None = None
    reply_to: EmailStr | None = None
    connected_account_email: EmailStr | None = None
    connected_account_name: str | None = None
    last_checked_at: datetime | None = None
    last_error: str | None = None
    updated_at: datetime | None = None


class MasterEmailConnectRequest(BaseModel):
    pass


class MasterEmailConnectResponse(BaseModel):
    redirect_url: str | None = None
    status: str


class MasterStripeConfigPayload(BaseModel):
    configured: bool
    enabled: bool
    account_id: str | None = None
    account_name: str | None = None
    webhook_secret_configured: bool
    last_checked_at: datetime | None = None
    last_error: str | None = None


class MasterStripeConnectRequest(BaseModel):
    stripe_secret_key: str = Field(min_length=1)
    webhook_secret: str | None = None
    enabled: bool = True

