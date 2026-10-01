"""
Pydantic schemas for Transaction / Payments.
"""
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional
from datetime import date
from decimal import Decimal
from app.models.transaction import PaymentMethodEnum, TransactionStatusEnum, TransactionTypeEnum
from app.schemas.datetime_types import UTCDateTime


class PaymentRequest(BaseModel):
    """Client-facing payment request (e.g. from booking cart)."""
    reservation_id: int
    amount: float = Field(..., gt=0)
    payment_method: PaymentMethodEnum
    transaction_type: TransactionTypeEnum
    currency: Optional[str] = Field(default=None, min_length=3, max_length=3)
    description: Optional[str] = None
    manual_reference: Optional[str] = Field(default=None, min_length=1, max_length=120)
    refund_of_transaction_id: Optional[int] = Field(default=None, gt=0)
    refund_reason: Optional[str] = Field(default=None, min_length=1, max_length=240)
    company_night_charge_ids: list[int] = Field(default_factory=list, max_length=90)
    collected_before: bool = False
    collected_on: Optional[date] = None
    prior_receipt_note: Optional[str] = Field(default=None, min_length=1, max_length=240)

    @field_validator("manual_reference")
    @classmethod
    def normalize_manual_reference(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("refund_reason")
    @classmethod
    def normalize_refund_reason(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("prior_receipt_note")
    @classmethod
    def normalize_prior_receipt_note(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @model_validator(mode="after")
    def validate_prior_receipt_fields(self) -> "PaymentRequest":
        if any(charge_id <= 0 for charge_id in self.company_night_charge_ids):
            raise ValueError("Company night charge ids must be positive")
        if len(self.company_night_charge_ids) != len(set(self.company_night_charge_ids)):
            raise ValueError("Company night charge ids must be unique")
        if self.transaction_type == TransactionTypeEnum.REFUND and self.company_night_charge_ids:
            raise ValueError("Refunds cannot allocate company night charges")
        has_prior_receipt_details = self.collected_on is not None or self.prior_receipt_note is not None
        if self.collected_before:
            if self.payment_method != PaymentMethodEnum.CASH:
                raise ValueError("Prior receipts must be recorded as cash payments")
            if self.transaction_type == TransactionTypeEnum.REFUND:
                raise ValueError("Refunds cannot be recorded as prior receipts")
            if self.collected_on is None or not self.prior_receipt_note:
                raise ValueError("A prior cash receipt requires its collection date and reason")
        elif has_prior_receipt_details:
            raise ValueError("Prior receipt date and reason require collected_before")
        return self


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
    manual_reference: Optional[str] = None
    refund_of_transaction_id: Optional[int] = None
    refund_reason: Optional[str] = None
    collected_before: bool = False
    collected_on: Optional[date] = None
    prior_receipt_note: Optional[str] = None
    description: Optional[str]
    created_at: Optional[UTCDateTime]
    processed_at: Optional[UTCDateTime]
    created_by_user_id: Optional[int] = None

    model_config = {"from_attributes": True}


class PaymentReceiptRead(BaseModel):
    """Minimal, tenant-authorized source data for an on-demand local receipt."""

    id: int
    reservation_id: int
    confirmation_code: str
    hotel_name: str
    hotel_timezone: str
    amount: Decimal
    gross_amount: Decimal
    fee_amount: Decimal
    currency: str
    method: PaymentMethodEnum
    type: TransactionTypeEnum
    status: TransactionStatusEnum
    manual_reference: Optional[str] = None
    refund_of_transaction_id: Optional[int] = None
    created_at: UTCDateTime


class PaymentGatewayResponse(BaseModel):
    """Standardized response from any payment gateway adapter."""
    success: bool
    external_payment_id: Optional[str] = None
    external_status: Optional[str] = None
    redirect_url: Optional[str] = None  # For MP / PayPal checkout redirects
    gateway_response: Optional[str] = None  # Raw JSON
    error_message: Optional[str] = None
