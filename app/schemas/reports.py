from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field
from app.schemas.datetime_types import UTCDateTime


class OperationalReservationSummary(BaseModel):
    reservation_id: int
    confirmation_code: str
    guest_id: int
    guest_name: str | None = None
    room_id: int | None = None
    room_number: str | None = None
    status: str
    check_in_date: date
    check_out_date: date
    total_amount: Decimal | None = None
    amount_paid: Decimal | None = None
    balance_due: Decimal | None = None
    currency_code: str = "ARS"
    company_billing_deferred: bool = False
    company_night_extra_due: Decimal | None = None


class OperationalReservationGroup(BaseModel):
    count: int
    reservations: list[OperationalReservationSummary] = Field(default_factory=list)


class ArrivalCountRead(BaseModel):
    report_date: date
    count: int


class AvailableWithReviewItem(BaseModel):
    reservation_id: int
    confirmation_code: str
    room_id: int | None = None
    room_number: str | None = None
    check_in_date: date
    check_out_date: date
    allocation_status: str


class ActiveRoomBlockItem(BaseModel):
    room_block_id: int
    room_id: int
    room_number: str | None = None
    reason_code: str
    reason_note: str | None = None
    starts_at: date
    ends_at: date | None = None
    is_indefinite: bool


class CashSessionStatusRead(BaseModel):
    status: str
    session_id: int | None = None
    opened_at: UTCDateTime | None = None
    opened_by_user_id: int | None = None
    currency_code: str | None = None


class OperationalAlertRead(BaseModel):
    code: str
    severity: str
    message: str
    reservation_id: int | None = None
    amount: Decimal | None = None
    currency_code: str | None = None
    room_id: int | None = None
    room_block_id: int | None = None
    cash_session_id: int | None = None



class DailyOperationalReportRead(BaseModel):
    hotel_id: int
    report_date: date
    generated_at: UTCDateTime
    arrivals: OperationalReservationGroup
    no_shows: OperationalReservationGroup = Field(default_factory=lambda: OperationalReservationGroup(count=0))
    departures: OperationalReservationGroup
    pending_payments: OperationalReservationGroup
    late_arrivals: list[OperationalReservationSummary] = Field(default_factory=list)
    available_with_review: list[AvailableWithReviewItem] = Field(default_factory=list)
    active_room_blocks: list[ActiveRoomBlockItem] = Field(default_factory=list)
    cash_session: CashSessionStatusRead
    alerts: list[OperationalAlertRead] = Field(default_factory=list)


class NightlyOperationalSummaryRead(BaseModel):
    hotel_id: int
    report_date: date
    generated_at: UTCDateTime
    alert_count: int
    pending_payment_count: int
    late_arrival_count: int
    available_with_review_count: int
    active_room_block_count: int
    cash_session_status: str
    alerts: list[OperationalAlertRead] = Field(default_factory=list)


class OperationalReportDeliveryRead(BaseModel):
    delivered: bool
    channel: str | None = None
    sender_email: str | None = None
    provider_message_id: str | None = None
    recipients: list[str] = Field(default_factory=list)


class RevenueCurrencyTotalRead(BaseModel):
    currency_code: str
    gross_collected: Decimal = Decimal("0.00")
    refunds: Decimal = Decimal("0.00")
    net_collected: Decimal = Decimal("0.00")
    transaction_count: int = 0


class RevenueBreakdownRead(RevenueCurrencyTotalRead):
    payment_method: str | None = None
    category_id: str | None = None
    category_name: str | None = None
    channel_code: str | None = None
    channel_label: str | None = None


class BookedValueCurrencyRead(BaseModel):
    currency_code: str
    amount: Decimal
    reservation_count: int
    booked_night_count: int = 0


class ExternalOtaCurrencyRead(BaseModel):
    currency_code: str
    amount: Decimal


class ExternalOtaChannelRead(ExternalOtaCurrencyRead):
    channel_code: str


class ExternalOtaCategoryRead(ExternalOtaCurrencyRead):
    category_name: str


class ExternalOtaCombinationRead(ExternalOtaCurrencyRead):
    channel_code: str
    category_name: str


class ReceivableCurrencyBucketsRead(BaseModel):
    currency_code: str
    overdue: Decimal
    due_at_check_in: Decimal
    due_today_company_nights: Decimal = Decimal("0.00")
    future: Decimal
    total: Decimal


class RevenueCollectedRead(BaseModel):
    currency_code: str | None = None
    # Legacy fields remain available for existing API consumers. For a mixed
    # currency interval, scalar totals are null and legacy maps are empty; the
    # additive *_by_currency fields are the complete source of truth.
    total: Decimal | None = None
    by_method: dict[str, Decimal] = Field(default_factory=dict)
    by_day: dict[str, Decimal] = Field(default_factory=dict)
    by_currency: list[RevenueCurrencyTotalRead] = Field(default_factory=list)
    by_method_by_currency: list[RevenueBreakdownRead] = Field(default_factory=list)
    by_category: list[RevenueBreakdownRead] = Field(default_factory=list)
    by_channel: list[RevenueBreakdownRead] = Field(default_factory=list)
    by_day_by_currency: list[dict] = Field(default_factory=list)
    by_combination: list[RevenueBreakdownRead] = Field(default_factory=list)
    transactions_count: int = 0


class ExpectedCurrencyRead(BaseModel):
    currency_code: str
    total: Decimal
    pending: Decimal
    reservations_count: int


class ExpectedReportRead(BaseModel):
    # Deprecated compatibility projection. `booked_value` and `receivables`
    # carry the explicitly named replacement metrics.
    total: Decimal | None = None
    pending: Decimal | None = None
    reservations_count: int = 0
    currency_code: str | None = None
    by_currency: list[ExpectedCurrencyRead] = Field(default_factory=list)


class BookedValueRead(BaseModel):
    total: Decimal | None = None
    currency_code: str | None = None
    by_currency: list[BookedValueCurrencyRead] = Field(default_factory=list)


class ExternalOtaCollectedRead(BaseModel):
    by_currency: list[ExternalOtaCurrencyRead] = Field(default_factory=list)
    by_channel: list[ExternalOtaChannelRead] = Field(default_factory=list)
    by_category: list[ExternalOtaCategoryRead] = Field(default_factory=list)
    by_combination: list[ExternalOtaCombinationRead] = Field(default_factory=list)


class ReceivablesRead(BaseModel):
    by_currency: list[ReceivableCurrencyBucketsRead] = Field(default_factory=list)


class RevenueReportRead(BaseModel):
    start_date: date
    end_date: date
    timezone: str
    receivables_as_of: date
    collected: RevenueCollectedRead
    expected: ExpectedReportRead = Field(default_factory=ExpectedReportRead)
    booked_value: BookedValueRead
    external_ota_collected: ExternalOtaCollectedRead
    receivables: ReceivablesRead
