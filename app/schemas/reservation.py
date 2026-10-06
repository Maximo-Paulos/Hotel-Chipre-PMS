"""
Pydantic schemas for Reservation.
"""
import re

from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Literal, Optional
from datetime import date, datetime
from decimal import Decimal
from app.models.reservation import ReservationChannelCodeEnum, ReservationStatusEnum, ReservationSourceEnum
from app.schemas.payment_link import PaymentLinkCreate, PaymentLinkRead
from app.schemas.transaction import PaymentRequest, TransactionRead
from app.schemas.guest_restriction import GuestRestrictionOverrideRequest


_ARRIVAL_TIME_PATTERN = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")


def _normalize_arrival_time_hint(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("arrival_time_hint must use HH:MM format")
    cleaned = value.strip()
    if not cleaned:
        return None
    if not _ARRIVAL_TIME_PATTERN.fullmatch(cleaned):
        raise ValueError("arrival_time_hint must use HH:MM format")
    return cleaned


def _normalize_reservation_comment(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("reservation_comment must be text")
    cleaned = value.strip()
    return cleaned or None

class GuestSummary(BaseModel):
    id: int
    first_name: str
    last_name: str
    document_type: Optional[str] = None
    document_number: Optional[str] = None
    model_config = {"from_attributes": True}
class ReservationCreate(BaseModel):
    guest_id: int
    category_id: int
    room_id: Optional[int] = None
    sellable_product_id: Optional[int] = None
    rate_plan_id: Optional[int] = None
    tax_policy_id: Optional[int] = None
    company_id: Optional[int] = None
    check_in_date: date
    check_out_date: date
    num_adults: int = Field(default=1, gt=0)
    num_children: int = Field(default=0, ge=0)
    notes: Optional[str] = None
    arrival_time_hint: Optional[str] = None
    reservation_comment: Optional[str] = Field(default=None, max_length=1000)
    source: ReservationSourceEnum = ReservationSourceEnum.DIRECT
    channel_code: Optional[ReservationChannelCodeEnum] = None
    external_id: Optional[str] = None
    pricing_channel_code: Optional[str] = Field(default=None, max_length=50)
    pricing_payment_method: Optional[str] = Field(default=None, max_length=30)
    guest_scope: str = Field(default="all", max_length=30)
    target_currency: Optional[str] = Field(default=None, min_length=3, max_length=3)
    total_amount: Optional[Decimal] = Field(default=None, ge=0)
    manual_rate_reason: Optional[str] = Field(default=None, max_length=500)
    confirm_large_total_adjustment: bool = False
    deposit_amount: Optional[Decimal] = Field(default=None, ge=0)
    quote_token: Optional[str] = Field(default=None, min_length=20, max_length=24000)
    mobility_restriction: bool = False
    # Waitlist / overbooking (v72 §9)
    is_wait_listed: bool = False
    wait_list_reason: Optional[str] = Field(default=None, max_length=255)
    restriction_override: Optional[GuestRestrictionOverrideRequest] = None

    @field_validator("arrival_time_hint", mode="before")
    @classmethod
    def normalize_arrival_time_hint(cls, value: object) -> str | None:
        return _normalize_arrival_time_hint(value)

    @field_validator("reservation_comment", mode="before")
    @classmethod
    def normalize_reservation_comment(cls, value: object) -> str | None:
        return _normalize_reservation_comment(value)

    @field_validator("manual_rate_reason", mode="before")
    @classmethod
    def normalize_manual_rate_reason(cls, value: object) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("El motivo de la tarifa manual debe ser texto")
        cleaned = value.strip()
        return cleaned or None


class ReservationRead(BaseModel):
    id: int
    confirmation_code: str
    guest_id: int
    guest: Optional[GuestSummary] = None
    room_id: Optional[int]
    # Human-facing room number. Keep the internal room_id for relations only.
    room_number: Optional[str] = None
    category_id: int
    # Human-facing category name. Keep category_id only for relations and
    # filters; operators should not have to interpret internal identifiers.
    category_name: Optional[str] = None
    company_id: Optional[int] = None
    group_id: Optional[int] = None
    sellable_product_id: Optional[int] = None
    rate_plan_id: Optional[int] = None
    tax_policy_id: Optional[int] = None
    check_in_date: date
    check_out_date: date
    actual_check_in: Optional[datetime]
    actual_check_out: Optional[datetime]
    # Deferred-company lodging is invoiced outside the PMS, so amount fields
    # are nullable in reads and can be masked without suggesting a zero charge.
    total_amount: float | None
    amount_paid: float | None
    external_paid_amount: float | None = 0.0
    external_paid_currency: Optional[str] = None
    external_paid_balance_credit_applied: bool = False
    external_paid_reference: Optional[str] = None
    external_paid_confirmed: bool = False
    deposit_amount: float | None
    subtotal_amount: float | None = 0.0
    tax_amount: float | None = 0.0
    fee_amount: float | None = 0.0
    commission_amount: float | None = 0.0
    net_amount: float | None = 0.0
    currency_code: str = "ARS"
    fx_rate_snapshot: Optional[float] = None
    quoted_amount_ars: Optional[float] = None
    quoted_amount_usd: Optional[float] = None
    status: ReservationStatusEnum
    source: ReservationSourceEnum
    source_provider_code: Optional[str] = None
    external_id: Optional[str]
    external_confirmation_code: Optional[str] = None
    payment_collection_model: str = "hotel_collect"
    settlement_status: str = "not_applicable"
    company_billing_deferred: bool = False
    num_adults: int
    num_children: int
    notes: Optional[str]
    arrival_time_hint: Optional[str] = None
    reservation_comment: Optional[str] = None
    company_extension_request_pending: bool = False
    company_extension_request_note: Optional[str] = None
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    balance_due: float | None = 0.0
    nights: int = 0
    additional_guests: list[GuestSummary] = []
    allocation_status: str = "unassigned"
    requires_manual_review: bool = False
    mobility_restriction: bool = False
    is_wait_listed: bool = False
    wait_list_reason: Optional[str] = None
    manual_rate_reason: Optional[str] = None
    version: int = 0

    model_config = {"from_attributes": True}


class ReservationGroupCreate(BaseModel):
    reservations: list[ReservationCreate] = Field(min_length=2, max_length=10)

    @model_validator(mode="after")
    def reject_manual_rates(self):
        if any(
            reservation.total_amount is not None or reservation.manual_rate_reason is not None
            for reservation in self.reservations
        ):
            raise ValueError("Las reservas de grupo usan la cotización de Tarifas; no aceptan tarifas manuales.")
        return self


class ReservationGroupChildFinancialRead(BaseModel):
    id: int
    confirmation_code: str
    total_amount: Decimal | None
    amount_paid: Decimal | None
    balance_due: Decimal | None
    currency_code: str
    status: str
    company_billing_deferred: bool = False


class ReservationGroupRead(BaseModel):
    id: int
    hotel_id: int
    guest_id: int
    guest_name: str
    company_id: int | None = None
    company_name: str | None = None
    check_in_date: date
    check_out_date: date
    notes: str | None = None
    reservation_count: int
    room_count: int
    reservation_ids: list[int]
    reservation_codes: list[str]
    reservations: list[ReservationGroupChildFinancialRead] = Field(default_factory=list)
    total_amount: Decimal | None
    amount_paid: Decimal | None
    balance_due: Decimal | None
    company_billing_deferred: bool = False
    currency_code: str
    created_at: datetime

    model_config = {"from_attributes": True}




class ReservationUpdate(BaseModel):
    room_id: Optional[int] = None
    check_in_date: Optional[date] = None
    check_out_date: Optional[date] = None
    total_amount: Optional[Decimal] = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    paid_total_change_reason: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Required, non-blank reason when correcting total_amount; legacy field name retained for API compatibility.",
    )
    confirm_large_total_adjustment: bool = False
    num_adults: Optional[int] = None
    num_children: Optional[int] = None
    notes: Optional[str] = None
    arrival_time_hint: Optional[str] = None
    reservation_comment: Optional[str] = Field(default=None, max_length=1000)
    mobility_restriction: Optional[bool] = None
    client_version: Optional[int] = None
    restriction_override: Optional[GuestRestrictionOverrideRequest] = None

    @field_validator("paid_total_change_reason", mode="before")
    @classmethod
    def normalize_total_change_reason(cls, value: object) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("paid_total_change_reason must be text")
        cleaned = value.strip()
        return cleaned or None

    @model_validator(mode="after")
    def validate_total_change_reason(self):
        if self.total_amount is not None and not self.paid_total_change_reason:
            raise ValueError("El motivo es obligatorio para corregir el total de la reserva.")
        if self.total_amount is None and self.paid_total_change_reason is not None:
            raise ValueError("El motivo solo corresponde cuando se corrige el total de la reserva.")
        return self

    @field_validator("arrival_time_hint", mode="before")
    @classmethod
    def normalize_arrival_time_hint(cls, value: object) -> str | None:
        return _normalize_arrival_time_hint(value)

    @field_validator("reservation_comment", mode="before")
    @classmethod
    def normalize_reservation_comment(cls, value: object) -> str | None:
        return _normalize_reservation_comment(value)


class ReservationNoShowRequest(BaseModel):
    client_version: int
    notes: Optional[str] = Field(default=None, max_length=500)


class ReservationDateChangeRequest(BaseModel):
    check_in_date: date
    check_out_date: date
    client_version: int
    room_id: Optional[int] = None
    pricing_mode: str = Field(default="recalculate", pattern="^(recalculate|keep_current_total)$")
    reason: Optional[str] = Field(default=None, max_length=500)


class ReservationDateChangeResponse(BaseModel):
    original_reservation: ReservationRead
    reservation: ReservationRead
    recreated: bool
    status_transitioned: bool = False


class ReservationExtensionPreviewResponse(BaseModel):
    reservation_id: int
    current_checkout_date: date
    new_checkout_date: date
    client_version: int
    extension_amount: Decimal
    currency_code: str = Field(min_length=3, max_length=3)


class ReservationExtensionRequest(BaseModel):
    new_checkout_date: date
    client_version: int
    pricing_mode: str = Field(default="current_rate", pattern="^(current_rate|original_average)$")
    payment_action: Literal["immediate_payment", "payment_link", "company_account"] = "payment_link"
    immediate_payment: Optional[PaymentRequest] = None
    payment_link: Optional[PaymentLinkCreate] = None
    notes: Optional[str] = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_company_account_extension(self):
        if self.payment_action == "company_account":
            if self.immediate_payment is not None or self.payment_link is not None:
                raise ValueError("La extensión a cuenta empresa no admite datos de cobro")
            if self.pricing_mode != "current_rate":
                raise ValueError("La extensión a cuenta empresa usa la tarifa vigente")
        return self


class ReservationExtensionResponse(BaseModel):
    reservation: ReservationRead
    extension_amount: Decimal
    transaction: Optional[TransactionRead] = None
    payment_link: Optional[PaymentLinkRead] = None


class CompanyExtensionRequestUpdate(BaseModel):
    pending: bool
    note: Optional[str] = Field(default=None, max_length=1000)
    client_version: int = Field(..., ge=0)

    @field_validator("note", mode="before")
    @classmethod
    def normalize_note(cls, value: object) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("note must be text")
        normalized = value.strip()
        return normalized or None

    @model_validator(mode="after")
    def validate_request_note(self):
        if self.pending and not self.note:
            raise ValueError("Indicá qué extensión pidió la empresa o qué falta confirmar.")
        if not self.pending and self.note is not None:
            raise ValueError("No se admite una nota al quitar la solicitud pendiente.")
        return self
