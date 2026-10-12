"""Pydantic schemas for cash register sessions, movements, and close reports."""
from datetime import date
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.cash_register import CashCustodyStatusEnum, CashMovementTypeEnum, CashSessionStatusEnum
from app.schemas.datetime_types import UTCDateTime


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
    opened_at: UTCDateTime
    closed_at: Optional[UTCDateTime] = None
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
    group_payment_batch_id: Optional[int] = None
    group_payment_total: Optional[Decimal] = None
    group_payment_reservation_count: Optional[int] = None
    movement_type: CashMovementTypeEnum
    amount: Decimal
    description: Optional[str] = None
    recorded_at: UTCDateTime

    model_config = {"from_attributes": True}


class CashSessionClose(BaseModel):
    counted_balance: Decimal = Field(..., ge=Decimal("0"))
    notes: Optional[str] = Field(default=None, max_length=1000)
    approve_difference: bool = False

    model_config = {"extra": "forbid"}


class CashCustodyReceipt(BaseModel):
    successor_float_amount: Decimal = Field(
        default=Decimal("0.00"),
        ge=Decimal("0"),
        le=Decimal("9999999999.99"),
    )

    model_config = {"extra": "forbid"}


class CashSessionCollectorSummaryRead(BaseModel):
    collector_user_id: Optional[int] = None
    collector_name: str
    income_total: Decimal
    expense_total: Decimal
    adjustment_total: Decimal
    net_total: Decimal
    movement_count: int


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
    by_collector: list[CashSessionCollectorSummaryRead] = Field(default_factory=list)


class CashDailyPaymentMethodRead(BaseModel):
    payment_method: str
    gross_collected: Decimal
    refunds: Decimal
    net_collected: Decimal
    transaction_count: int


class CashDailyCollectorRead(BaseModel):
    collector_user_id: Optional[int] = None
    collector_name: str
    gross_collected: Decimal
    refunds: Decimal
    net_collected: Decimal
    transaction_count: int


class CashDailyEntryRead(BaseModel):
    entry_type: Literal["payment", "manual_movement"]
    actor_user_id: Optional[int] = None
    actor_name: str
    transaction_id: Optional[int] = None
    group_payment_batch_id: Optional[int] = None
    cash_movement_id: Optional[int] = None
    reservation_id: Optional[int] = None
    amount: Decimal
    signed_amount: Decimal
    currency_code: str
    payment_method: Optional[str] = None
    transaction_type: Optional[str] = None
    transaction_status: Optional[str] = None
    movement_type: Optional[str] = None
    occurred_at: UTCDateTime
    description: Optional[str] = None
    provider_code: Optional[str] = None


class CashDailySessionRead(BaseModel):
    session_id: int
    status: str
    currency_code: str
    opened_at: UTCDateTime
    closed_at: Optional[UTCDateTime] = None
    opened_by_user_id: Optional[int] = None
    closed_by_user_id: Optional[int] = None
    opened_by_name: Optional[str] = None
    closed_by_name: Optional[str] = None
    opening_balance: Decimal
    expected_balance: Decimal
    declared_balance: Optional[Decimal] = None
    difference: Optional[Decimal] = None


class CashDailyPhysicalRead(BaseModel):
    opening_balance: Decimal
    income_total: Decimal
    expense_total: Decimal
    adjustment_total: Decimal
    custody_delivered_total: Decimal = Decimal("0.00")
    custody_difference_total: Decimal = Decimal("0.00")
    expected_balance: Decimal
    declared_balance: Optional[Decimal] = None
    difference: Optional[Decimal] = None
    manual_income_total: Decimal
    manual_expense_total: Decimal


class CashDailyPriorReceiptRead(BaseModel):
    transaction_id: int
    reservation_id: int
    confirmation_code: str
    amount: Decimal
    currency_code: str
    collected_on: date
    prior_receipt_note: str
    recorded_at: UTCDateTime
    recorded_by_user_id: Optional[int] = None
    recorded_by_name: str


class CashDailyPriorReceiptTotalRead(BaseModel):
    currency_code: str
    amount: Decimal
    transaction_count: int


class CashDailySummaryRead(BaseModel):
    hotel_id: int
    report_date: str
    timezone: str
    currency_code: str
    gross_collected: Decimal
    refunds: Decimal
    net_collected: Decimal
    physical_cash_net_collected: Decimal
    digital_net_collected: Decimal
    by_payment_method: list[CashDailyPaymentMethodRead] = Field(default_factory=list)
    by_collector: list[CashDailyCollectorRead] = Field(default_factory=list)
    physical_cash: CashDailyPhysicalRead
    prior_receipts: list[CashDailyPriorReceiptRead] = Field(default_factory=list)
    prior_receipt_totals: list[CashDailyPriorReceiptTotalRead] = Field(default_factory=list)
    prior_receipts_truncated: bool = False
    sessions: list[CashDailySessionRead] = Field(default_factory=list)
    entries: list[CashDailyEntryRead] = Field(default_factory=list)
    entries_truncated: bool = False
    generated_at: UTCDateTime


class CashCustodyHandoffRead(BaseModel):
    id: int
    hotel_id: int
    close_report_id: int
    delivered_by_user_id: Optional[int] = None
    received_by_user_id: Optional[int] = None
    delivered_amount: Decimal
    status: CashCustodyStatusEnum
    delivered_at: UTCDateTime
    received_at: Optional[UTCDateTime] = None
    notes: Optional[str] = None

    model_config = {"from_attributes": True}


class CashCloseReportRead(BaseModel):
    id: int
    hotel_id: int
    session_id: int
    currency_code: str
    closed_by_user_id: Optional[int] = None
    closed_by_name: Optional[str] = None
    expected_balance: Decimal
    declared_balance: Decimal
    difference: Decimal
    difference_approved: bool
    approved_by_user_id: Optional[int] = None
    approved_by_name: Optional[str] = None
    successor_session_id: Optional[int] = None
    successor_opening_balance: Optional[Decimal] = None
    successor_float_declared_amount: Optional[Decimal] = None
    successor_float_declared_by_user_id: Optional[int] = None
    successor_float_declared_by_name: Optional[str] = None
    successor_float_declared_at: Optional[UTCDateTime] = None
    custody_handoff: Optional[CashCustodyHandoffRead] = None
    notes: Optional[str] = None
    closed_at: UTCDateTime

    model_config = {"from_attributes": True}


class CashExpenseCreate(BaseModel):
    amount: Decimal = Field(..., gt=Decimal("0"), le=Decimal("9999999999.99"))
    category: str = Field(min_length=1, max_length=64)
    vendor: str = Field(min_length=1, max_length=120)
    description: Optional[str] = Field(default=None, max_length=300)
    receipt_reference: Optional[str] = Field(default=None, min_length=1, max_length=120)
    receipt_image_base64: Optional[str] = Field(default=None, max_length=7_000_000)
    receipt_filename: Optional[str] = Field(default=None, max_length=255)

    @field_validator("category", "vendor", "receipt_reference")
    @classmethod
    def trim_required_or_optional_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @model_validator(mode="after")
    def require_receipt_reference_or_image(self):
        if not self.receipt_reference and not self.receipt_image_base64:
            raise ValueError("Ingresá la referencia del comprobante o adjuntá una imagen")
        return self

    model_config = {"extra": "forbid"}


class CashExpenseRead(BaseModel):
    id: int
    hotel_id: int
    session_id: int
    amount: Decimal
    currency_code: str
    category: str
    vendor: str
    description: Optional[str] = None
    receipt_reference: Optional[str] = None
    receipt_filename: Optional[str] = None
    has_receipt_image: bool = False
    status: str
    cash_movement_id: Optional[int] = None
    recorded_by_user_id: Optional[int] = None
    recorded_by_name: Optional[str] = None
    approved_by_user_id: Optional[int] = None
    approved_by_name: Optional[str] = None
    rejected_by_user_id: Optional[int] = None
    rejected_by_name: Optional[str] = None
    rejection_reason: Optional[str] = None
    created_at: UTCDateTime
    approved_at: Optional[UTCDateTime] = None
    rejected_at: Optional[UTCDateTime] = None


class CashExpenseReject(BaseModel):
    reason: str = Field(min_length=1, max_length=1000)

    @field_validator("reason")
    @classmethod
    def trim_reason(cls, value: str) -> str:
        return value.strip()

    model_config = {"extra": "forbid"}
