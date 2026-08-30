"""
Schemas for operational reservation actions.
"""
from __future__ import annotations

import enum
from datetime import date
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

from app.schemas.reservation import ReservationRead


class ManualRoomMoveReasonCodeEnum(str, enum.Enum):
    GUEST_COMPLAINT = "guest_complaint"
    GUEST_REQUEST = "guest_request"
    MAINTENANCE = "maintenance"
    OPERATIONAL = "operational"
    UPGRADE = "upgrade"


class RoomMoveRequest(BaseModel):
    to_room_id: int
    reason_code: str = Field(..., min_length=1)
    notes: Optional[str] = None
    price_action: Literal["keep", "reprice"] = "keep"

    @field_validator("reason_code")
    @classmethod
    def reason_code_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("reason_code is required")
        return value


class RoomMoveResponse(BaseModel):
    reservation: ReservationRead
    category_changed: bool
    price_action: Literal["keep", "reprice"]
    previous_total_amount: Decimal
    quoted_total_amount: Decimal
    amount_delta: Decimal
    currency_code: str


class ReservationChargeCreate(BaseModel):
    """Operator-created consumption or extra charge for an active stay."""

    amount: Decimal = Field(..., gt=0, max_digits=12, decimal_places=2)
    currency_code: str = Field(default="ARS", min_length=3, max_length=3)
    description: str = Field(..., min_length=1, max_length=240)

    @field_validator("currency_code")
    @classmethod
    def normalize_currency_code(cls, value: str) -> str:
        normalized = value.strip().upper()
        if len(normalized) != 3 or not normalized.isalpha():
            raise ValueError("currency_code must be a three-letter currency code")
        return normalized

    @field_validator("description")
    @classmethod
    def description_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("description is required")
        return value


class ReservationActionResolveRequest(BaseModel):
    notes: Optional[str] = None


class OTARebookToDirectRequest(BaseModel):
    target_category_id: int
    target_rate_plan_id: Optional[int] = None
    target_tax_policy_id: Optional[int] = None
    target_room_id: Optional[int] = None
    pricing_channel_code: Optional[str] = None
    guest_scope: str = Field(default="all")
    target_currency: Optional[str] = None
    discount_pct: float = Field(default=0.0, ge=0.0, le=100.0)
    total_override: Optional[float] = Field(default=None, ge=0.0)
    notes: Optional[str] = None


class OTARebookPreviewResponse(BaseModel):
    target_category_id: int
    target_rate_plan_id: Optional[int] = None
    target_sellable_product_id: Optional[int] = None
    pricing_source: str
    currency_code: str
    original_total_amount: float
    quoted_total_amount: float
    subtotal_amount: float
    tax_amount: float
    fee_amount: float
    commission_amount: float
    net_amount: float
    deposit_amount: float
    amount_delta: float
    fx_rate_snapshot: Optional[float] = None


class OTARebookToDirectResponse(BaseModel):
    adjustment_id: int
    original_reservation_id: int
    new_reservation_id: int
    billing_adjustment_id: Optional[int] = None
    amount_delta: float
    currency_code: Optional[str] = None
    quoted_total_amount: Optional[float] = None
    pricing_source: Optional[str] = None


class AllocationRunRequest(BaseModel):
    apply: bool = True
    horizon_start: Optional[date] = None
    horizon_end: Optional[date] = None


class AllocationRunResponse(BaseModel):
    run_id: int
    status: str
    objective_score: float = 0.0
    assignments_created: int
    unassigned_count: int
    moved_count: int


class ReservationTransactionSummaryRead(BaseModel):
    id: int
    amount: float
    gross_amount: Optional[float] = None
    fee_amount: Optional[float] = None
    currency: str
    method: str
    type: str
    status: str
    created_at: str


class ReservationBillingAdjustmentSummaryRead(BaseModel):
    id: int
    type: str
    amount: float
    tax_amount: Optional[float] = None
    total_amount: float
    currency_code: str
    notes: Optional[str] = None


class ReservationFinancialSummaryRead(BaseModel):
    reservation_id: int
    confirmation_code: str
    status: str
    currency_code: str
    total_amount: float
    deposit_required: float
    amount_paid: float
    balance_due: float
    operational_total_amount: float
    operational_balance_due: float
    billing_adjustment_total: float
    payment_collection_model: str
    settlement_status: str
    has_financial_reconciliation_gap: bool
    financial_reconciliation_gap: float
    recommended_next_action: Optional[str] = None
    transactions: list[ReservationTransactionSummaryRead]
    billing_adjustments: list[ReservationBillingAdjustmentSummaryRead]
    completed_payments: float


class ReservationPendingActionRead(BaseModel):
    action_key: str
    code: str
    priority: str
    title: str
    detail: str
    reservation_id: int
    confirmation_code: str
    guest_name: Optional[str] = None
    reservation_status: str
    source: str
    source_provider_code: Optional[str] = None
    payment_collection_model: Optional[str] = None
    settlement_status: Optional[str] = None
    check_in_date: date
    check_out_date: date
    reference_type: Optional[str] = None
    reference_id: Optional[int] = None


class ReservationAdjustmentSummaryRead(BaseModel):
    id: int
    kind: str
    status: str
    reason_code: Optional[str] = None
    request_source: Optional[str] = None
    amount_delta: Optional[float] = None
    currency_code: Optional[str] = None
    external_resolution_status: Optional[str] = None
    resulting_reservation_id: Optional[int] = None
    ota_reservation_link_id: Optional[int] = None
    notes: Optional[str] = None


class ReservationOTALinkSummaryRead(BaseModel):
    id: int
    provider_id: int
    external_reservation_id: str
    external_confirmation_code: Optional[str] = None
    provider_state: str
    sync_status: Optional[str] = None
    error_message: Optional[str] = None


class ReservationRoomMoveSummaryRead(BaseModel):
    id: int
    move_type: str
    reason_code: Optional[str] = None
    from_room_id: Optional[int] = None
    to_room_id: Optional[int] = None
    notes: Optional[str] = None
    occurred_at: Optional[str] = None


class ReservationOperationsSummaryRead(BaseModel):
    reservation_id: int
    confirmation_code: str
    status: str
    source: str
    source_provider_code: Optional[str] = None
    allocation_status: str
    requires_manual_review: bool
    payment_collection_model: str
    settlement_status: str
    pending_action_count: int
    pending_actions: list[ReservationPendingActionRead]
    financial_summary: ReservationFinancialSummaryRead
    ota_link: Optional[ReservationOTALinkSummaryRead] = None
    open_adjustments: list[ReservationAdjustmentSummaryRead]
    latest_room_move: Optional[ReservationRoomMoveSummaryRead] = None


class ReservationExternalResolutionResponse(BaseModel):
    reservation_id: int
    changed_adjustments: int
    ota_link_resolved: bool
    settlement_status: str
    resolved_by_user_id: Optional[int] = None


class ReservationManualReviewResponse(BaseModel):
    reservation_id: int
    requires_manual_review: bool
    allocation_status: str
    reviewed_by_user_id: Optional[int] = None


# ── B2: occupancy grid (planilla de ocupación) ──────────────────────────────


class OccupancyGridRoomRead(BaseModel):
    id: int
    room_number: str
    floor: int
    category_id: int
    category_name: str
    status: str


class OccupancyGridReservationRead(BaseModel):
    id: int
    room_id: Optional[int] = None
    confirmation_code: str
    check_in_date: date
    check_out_date: date
    status: str
    guest_name: str
    num_adults: int
    num_children: int
    operational_balance_due: float


class OccupancyGridBlockRead(BaseModel):
    room_id: int
    starts_at: date
    ends_at: Optional[date] = None
    reason_code: str


class OccupancyGridResponse(BaseModel):
    rooms: list[OccupancyGridRoomRead]
    reservations: list[OccupancyGridReservationRead]
    unassigned: list[OccupancyGridReservationRead]
    blocks: list[OccupancyGridBlockRead]
