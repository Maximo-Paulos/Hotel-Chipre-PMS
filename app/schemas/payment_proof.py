from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.payment_proof import PaymentProofStatusEnum


class PaymentProofCreate(BaseModel):
    reservation_id: int
    amount: Decimal = Field(..., gt=Decimal("0.00"))
    image_base64: str = Field(..., min_length=16, max_length=11_200_000)
    original_filename: str | None = Field(default=None, max_length=255)


class PaymentProofReject(BaseModel):
    reason: str = Field(..., min_length=1, max_length=2000)


class PaymentProofRead(BaseModel):
    id: int
    hotel_id: int
    reservation_id: int
    transaction_id: int | None = None
    amount: Decimal
    currency: str
    payment_method: str
    status: PaymentProofStatusEnum
    original_filename: str | None = None
    content_type: str
    file_size_bytes: int
    sha256_hex: str
    submitted_by_user_id: int | None = None
    reviewed_by_user_id: int | None = None
    rejection_reason: str | None = None
    created_at: datetime
    reviewed_at: datetime | None = None

    model_config = {"from_attributes": True}
