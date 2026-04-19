from typing import Any

from pydantic import BaseModel, Field


class Entitlement(BaseModel):
    code: str
    value: Any | None = None
    source: str | None = None


class EntitlementsResponse(BaseModel):
    hotel_id: int
    plan: str | None = None
    status: str | None = None
    enforcement_enabled: bool
    entitlements: list[Entitlement]


class EntitlementOverrideRequest(BaseModel):
    code: str = Field(..., examples=["rooms.max_active", "reports.advanced"])
    value: Any
    value_type: str | None = Field(
        default=None,
        description="int|bool|str - opcional, si se omite se infiere automaticamente",
    )


class TrialRequest(BaseModel):
    plan_code: str = Field(default="pro", examples=["starter", "pro", "ultra"])


class CompedOverrideRequest(BaseModel):
    hotel_id: int = Field(..., gt=0)
    plan_code: str = Field(default="ultra", examples=["starter", "pro", "ultra"])
    reason: str | None = Field(default=None, max_length=250)
