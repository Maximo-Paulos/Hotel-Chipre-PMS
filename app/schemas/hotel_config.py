"""
Pydantic schemas for HotelConfiguration.
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class HotelConfigRead(BaseModel):
    id: int
    deposit_percentage: float
    enable_full_payment: bool
    enable_deposit_payment: bool
    enable_cash: bool
    enable_mercado_pago: bool
    enable_paypal: bool
    enable_credit_card: bool
    enable_debit_card: bool
    enable_bank_transfer: bool
    free_cancellation_hours: int
    cancellation_penalty_percentage: float
    allow_cancellation_after_checkin: bool
    enable_booking_sync: bool
    enable_expedia_sync: bool
    require_document_for_checkin: bool
    require_terms_acceptance: bool
    hotel_name: str
    hotel_timezone: str
    default_currency: str
    extra_policies: Optional[str]
    updated_at: Optional[datetime]

    model_config = {"from_attributes": True}


class HotelConfigUpdate(BaseModel):
    deposit_percentage: Optional[float] = Field(default=None, ge=0, le=100)
    enable_full_payment: Optional[bool] = None
    enable_deposit_payment: Optional[bool] = None
    enable_cash: Optional[bool] = None
    enable_mercado_pago: Optional[bool] = None
    enable_paypal: Optional[bool] = None
    enable_credit_card: Optional[bool] = None
    enable_debit_card: Optional[bool] = None
    enable_bank_transfer: Optional[bool] = None
    free_cancellation_hours: Optional[int] = Field(default=None, ge=0)
    cancellation_penalty_percentage: Optional[float] = Field(default=None, ge=0, le=100)
    allow_cancellation_after_checkin: Optional[bool] = None
    enable_booking_sync: Optional[bool] = None
    enable_expedia_sync: Optional[bool] = None
    require_document_for_checkin: Optional[bool] = None
    require_terms_acceptance: Optional[bool] = None
    hotel_name: Optional[str] = None
    hotel_timezone: Optional[str] = None
    default_currency: Optional[str] = None
    extra_policies: Optional[str] = None
