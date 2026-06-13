from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field


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


class OperationalReservationGroup(BaseModel):
    count: int
    reservations: list[OperationalReservationSummary] = Field(default_factory=list)


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
    opened_at: datetime | None = None
    opened_by_user_id: int | None = None
    currency_code: str | None = None


class OperationalAlertRead(BaseModel):
    code: str
    severity: str
    message: str
    reservation_id: int | None = None
    room_id: int | None = None
    room_block_id: int | None = None
    cash_session_id: int | None = None


class DailyOperationalReportRead(BaseModel):
    hotel_id: int
    report_date: date
    generated_at: datetime
    arrivals: OperationalReservationGroup
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
    generated_at: datetime
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
