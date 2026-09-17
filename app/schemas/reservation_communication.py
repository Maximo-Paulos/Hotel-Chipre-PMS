from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, EmailStr


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
    recipient_email: EmailStr | None = None
    resend: bool = False


class ReservationEmailDeliveryRead(BaseModel):
    id: int
    reservation_id: int
    kind: ReservationEmailKind
    status: ReservationEmailStatus
    recipient_email: EmailStr
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


class ReservationEmailSendResponse(BaseModel):
    delivery: ReservationEmailDeliveryRead
    deduplicated: bool = False
