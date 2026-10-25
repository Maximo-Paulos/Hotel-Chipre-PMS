"""Transport contracts for manual reservation cancellation review."""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.booking import BookingRead
from app.schemas.reservation import ReservationRead


class CancellationReviewRead(BaseModel):
    id: int
    reservation_id: int
    confirmation_code: str
    check_in_date: date
    check_out_date: date
    reservation_total: Decimal | None = None
    reservation_currency_code: str | None = None
    review_type: Literal["penalty", "historical_policy_missing", "policy_needs_review"]
    status: Literal["pending", "approved", "rejected"]
    reason_code: str
    policy_snapshot: dict | None = None
    free_cancellation_hours: int | None = None
    check_in_time: str | None = None
    hotel_timezone: str | None = None
    cancellation_cutoff_at: datetime | None = None
    penalty_amount: Decimal | None = None
    penalty_currency_code: str | None = None
    requested_by_user_id: int | None = None
    requested_at: datetime
    reviewed_by_user_id: int | None = None
    reviewed_at: datetime | None = None
    review_reason: str | None = None


class ReservationCancellationResponse(ReservationRead):
    cancellation_outcome: Literal["cancelled", "approval_required", "manager_review_required"]
    cancellation_review: CancellationReviewRead | None = None


class BookingCancellationResponse(BookingRead):
    cancellation_outcome: Literal["cancelled", "approval_required", "manager_review_required"]
    cancellation_review: CancellationReviewRead | None = None


class CancellationReviewDecisionRequest(BaseModel):
    decision: Literal["approve", "reject"]
    reason: str = Field(..., min_length=3, max_length=500)

    @field_validator("reason")
    @classmethod
    def reason_must_not_be_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) < 3:
            raise ValueError("Indicá un motivo de al menos 3 caracteres.")
        return cleaned


class CancellationReviewResolutionResponse(BaseModel):
    cancellation_review: CancellationReviewRead
    reservation: ReservationRead
