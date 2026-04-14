"""
Schemas for operational reservation actions.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


class RoomMoveRequest(BaseModel):
    to_room_id: int
    reason_code: Optional[str] = None
    notes: Optional[str] = None


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
