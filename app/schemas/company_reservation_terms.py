"""API contracts for reviewing company profile changes on a reservation."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class CompanyReservationTermsReviewRequest(BaseModel):
    action: Literal["keep_snapshot", "accept_current"]
    reason: str = Field(..., min_length=1, max_length=1000)
    expected_config_fingerprint: str = Field(..., min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    idempotency_key: UUID

    @field_validator("reason")
    @classmethod
    def reason_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Se requiere un motivo para revisar las condiciones de empresa")
        return value


class CompanyReservationTermsReviewRead(BaseModel):
    reservation_id: int
    company_id: int | None
    company_name: str | None = None
    status: Literal[
        "not_applicable",
        "captured",
        "hold_for_manager_review",
        "snapshot_missing",
        "manager_kept_snapshot",
        "manager_accepted_current",
    ]
    needs_review: bool
    blocks_checkin: bool
    block_checkin_on_change: bool | None = None
    current_terms: dict[str, Any] | None = None
    reviewed_config: dict[str, Any] | None = None
    snapshot: dict[str, Any] | None = None
    changed_fields: list[str]
    current_fingerprint: str | None = None
    reviewed_config_fingerprint: str | None = None
    history: list["CompanyReservationTermsReviewEventRead"] = Field(default_factory=list)


class CompanyReservationTermsReviewEventRead(BaseModel):
    id: int
    action: Literal["keep_snapshot", "accept_current"]
    reason: str
    changed_fields: list[str]
    actor_user_id: int
    created_at: datetime

    model_config = {"from_attributes": True}
