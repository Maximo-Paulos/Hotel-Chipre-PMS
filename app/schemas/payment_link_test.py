from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class PaymentLinkTestCreate(BaseModel):
    recipient_email: str = Field(..., min_length=5, max_length=255)
    amount: float = Field(..., gt=0)
    currency: str = Field(default="ARS", min_length=3, max_length=3)
    description: str = Field(default="Sena de reserva", min_length=3, max_length=255)
    expires_in_minutes: Optional[int] = Field(default=None, ge=1, le=43200)


class PaymentLinkTestRead(BaseModel):
    hotel_id: int
    id: int
    provider: str
    recipient_email: str
    amount: float
    currency: str
    description: str
    external_reference: str
    preference_id: Optional[str] = None
    payment_url: Optional[str] = None
    status: str
    external_status: Optional[str] = None
    external_payment_id: Optional[str] = None
    refunded_amount: Optional[float] = None
    email_sent_at: Optional[datetime] = None
    sender_channel: Optional[str] = None
    sender_email: Optional[str] = None
    expires_at: Optional[datetime] = None
    last_checked_at: Optional[datetime] = None
    last_error: Optional[str] = None
    paid_at: Optional[datetime] = None
    refunded_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
