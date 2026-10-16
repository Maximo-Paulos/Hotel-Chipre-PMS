from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator

from app.utils.reservation_email_validation import normalize_reservation_email


class ReservationEmailKind(str, Enum):
    CONFIRMATION = "confirmation"
    VOUCHER = "voucher"


class ReservationEmailStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    FAILED = "failed"
    UNKNOWN = "unknown"


class ReservationEmailSendRequest(BaseModel):
    kind: ReservationEmailKind = ReservationEmailKind.CONFIRMATION
    recipient_email: str | None = Field(
        default=None,
        json_schema_extra={"format": "email"},
    )
    resend: bool = False

    @field_validator("recipient_email")
    @classmethod
    def _validate_recipient_email(cls, value: str | None) -> str | None:
        return normalize_reservation_email(value) if value is not None else None


class ReservationEmailDeliveryRead(BaseModel):
    id: int
    reservation_id: int
    kind: ReservationEmailKind
    status: ReservationEmailStatus
    recipient_email: str = Field(json_schema_extra={"format": "email"})
    subject: str
    provider_message_id: str | None = None
    attempt_count: int
    is_resend: bool
    requested_by_user_id: int | None = None
    last_error: str | None = None
    created_at: datetime
    updated_at: datetime
    accepted_at: datetime | None = None

    model_config = {"from_attributes": True}

    @field_validator("recipient_email")
    @classmethod
    def _validate_recipient_email(cls, value: str) -> str:
        return normalize_reservation_email(value)


class ReservationEmailSendResponse(BaseModel):
    delivery: ReservationEmailDeliveryRead
    deduplicated: bool = False
