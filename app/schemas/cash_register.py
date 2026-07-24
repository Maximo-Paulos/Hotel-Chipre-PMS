"""Pydantic schemas for cash register sessions, movements, and close reports."""
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.models.cash_register import CashCustodyStatusEnum, CashMovementTypeEnum, CashSessionStatusEnum


class CashSessionOpen(BaseModel):
    opening_balance: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0"))
    currency_code: str = Field(default="ARS", min_length=3, max_length=3)
    notes: Optional[str] = Field(default=None, max_length=1000)

    @field_validator("currency_code")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.strip().upper()


class CashSessionRead(BaseModel):
    id: int
    hotel_id: int
    opened_by_user_id: Optional[int] = None
    closed_by_user_id: Optional[int] = None
    status: CashSessionStatusEnum
    opening_balance: Decimal
    currency_code: str
    opened_at: datetime
    closed_at: Optional[datetime] = None
    notes: Optional[str] = None

    model_config = {"from_attributes": True}


class CashMovementCreate(BaseModel):
    movement_type: CashMovementTypeEnum
    amount: Decimal = Field(..., gt=Decimal("0"))
    description: Optional[str] = Field(default=None, max_length=300)
    reservation_id: Optional[int] = None
    transaction_id: Optional[int] = None


class CashMovementRead(BaseModel):
    id: int
    hotel_id: int
    session_id: int
    reservation_id: Optional[int] = None
    transaction_id: Optional[int] = None
    recorded_by_user_id: Optional[int] = None
    movement_type: CashMovementTypeEnum
    amount: Decimal
    description: Optional[str] = None
    recorded_at: datetime

    model_config = {"from_attributes": True}


class CashSessionClose(BaseModel):
    counted_balance: Decimal = Field(..., ge=Decimal("0"))
    notes: Optional[str] = Field(default=None, max_length=1000)
    approve_difference: bool = False


class CashSessionSummaryRead(BaseModel):
    session_id: int
    status: str
    currency_code: str
    opening_balance: Decimal
    income_total: Decimal
    expense_total: Decimal
    adjustment_total: Decimal
    confirmed_cash_total: Decimal
    expected_balance: Decimal
    movements_count: int


class CashCustodyHandoffRead(BaseModel):
    id: int
    hotel_id: int
    close_report_id: int
    delivered_by_user_id: Optional[int] = None
    received_by_user_id: Optional[int] = None
    delivered_amount: Decimal
    status: CashCustodyStatusEnum
    delivered_at: datetime
    received_at: Optional[datetime] = None
    notes: Optional[str] = None

    model_config = {"from_attributes": True}


class CashCloseReportRead(BaseModel):
    id: int
    hotel_id: int
    session_id: int
    closed_by_user_id: Optional[int] = None
    expected_balance: Decimal
    declared_balance: Decimal
    difference: Decimal
    difference_approved: bool
    approved_by_user_id: Optional[int] = None
    successor_session_id: Optional[int] = None
    custody_handoff: Optional[CashCustodyHandoffRead] = None
    notes: Optional[str] = None
    closed_at: datetime

    model_config = {"from_attributes": True}
