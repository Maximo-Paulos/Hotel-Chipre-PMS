"""
Pydantic schemas for Transaction / Payments.
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from app.models.transaction import PaymentMethodEnum, TransactionStatusEnum, TransactionTypeEnum


class PaymentRequest(BaseModel):
    """Client-facing payment request (e.g. from booking cart)."""
    reservation_id: int
    amount: float = Field(..., gt=0)
    payment_method: PaymentMethodEnum
    transaction_type: TransactionTypeEnum
    currency: Optional[str] = Field(default=None, min_length=3, max_length=3)
    description: Optional[str] = None


class TransactionRead(BaseModel):
    id: int
    hotel_id: int
    reservation_id: int
    amount: float
    currency: str
    transaction_type: TransactionTypeEnum
    payment_method: PaymentMethodEnum
    status: TransactionStatusEnum
    external_payment_id: Optional[str]
    external_status: Optional[str]
    description: Optional[str]
    created_at: Optional[datetime]
    processed_at: Optional[datetime]

    model_config = {"from_attributes": True}


class PaymentGatewayResponse(BaseModel):
    """Standardized response from any payment gateway adapter."""
    success: bool
    external_payment_id: Optional[str] = None
    external_status: Optional[str] = None
    redirect_url: Optional[str] = None  # For MP / PayPal checkout redirects
    gateway_response: Optional[str] = None  # Raw JSON
    error_message: Optional[str] = None
