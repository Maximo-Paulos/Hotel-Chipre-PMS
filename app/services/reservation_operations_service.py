"""
Reservation operations service.

Handles operational scenarios that go beyond a plain reservation update:
- OTA reservation moved to a direct reservation
- manual room moves with audit trail
- billing adjustments associated with operational changes
- commercial previews for OTA-to-direct rebooks
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

from app.models.commercial import RatePlan, SellableProduct, TaxPolicy
from app.models.hotel_config import HotelConfiguration
from app.models.ota_core import OTAReservationLifecycleEnum, OTAReservationLink
from app.models.operations import (
    BillingAdjustment,
    BillingAdjustmentTypeEnum,
    ReservationAdjustment,
    ReservationAdjustmentKindEnum,
    ReservationAdjustmentStatusEnum,
    RoomMoveEvent,
    RoomMoveTypeEnum,
)
from app.models.reservation import Reservation, ReservationSourceEnum, ReservationStatusEnum
from app.models.room import Room, RoomCategory
from app.services.allocation_policy_service import record_manual_override_feedback
from app.schemas.reservation import ReservationCreate
from app.services.pricing_policy_service import PricingPolicyError, quote_rate_plan_stay
from app.services.reservation_service import (
    ReservationError,
    check_room_availability,
    compute_reservation_pricing,
    create_reservation,
    transition_reservation_status,
)


class ReservationOperationsError(ReservationError):
    """Operational exception with business-friendly semantics."""


def _hotel_default_currency(db: Session, hotel_id: int) -> str:
    config = db.query(HotelConfiguration).filter(HotelConfiguration.id == hotel_id).first()
    return str(getattr(config, "default_currency", None) or "ARS").strip().upper()[:3] or "ARS"


@dataclass(slots=True)
class OTARebookPreview:
    target_category_id: int
    target_rate_plan_id: int | None
    target_tax_policy_id: int | None
    target_sellable_product_id: int | None
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
    fx_rate_snapshot: float | None


@dataclass(slots=True)
class OTARebookResult:
    adjustment: ReservationAdjustment
    original_reservation: Reservation
    new_reservation: Reservation
    billing_adjustment: BillingAdjustment | None
    preview: OTARebookPreview


def move_reservation_room(
    db: Session,
    *,
    reservation: Reservation,
    to_room_id: int,
    hotel_id: int,
    moved_by_user_id: Optional[int] = None,
    reason_code: Optional[str] = None,
    notes: Optional[str] = None,
    move_type: RoomMoveTypeEnum = RoomMoveTypeEnum.MANUAL_MOVE,
) -> RoomMoveEvent:
    room = db.query(Room).filter(Room.id == to_room_id, Room.hotel_id == hotel_id).first()
    if not room:
        raise ReservationOperationsError("La habitacion destino no existe para este hotel")

    if not check_room_availability(
        db,
        room.id,
        reservation.check_in_date,
        reservation.check_out_date,
        hotel_id=hotel_id,
        exclude_reservation_id=reservation.id,
    ):
        raise ReservationOperationsError("La habitacion destino no esta disponible para esas fechas")

    previous_room_id = reservation.room_id
    reservation.room_id = room.id
    reservation.category_id = room.category_id
    event = RoomMoveEvent(
        hotel_id=hotel_id,
        reservation_id=reservation.id,
        from_room_id=previous_room_id,
        to_room_id=room.id,
        move_type=move_type,
        reason_code=reason_code,
        notes=notes,
        created_by_user_id=moved_by_user_id,
    )
    db.add(event)
    db.flush()
    record_manual_override_feedback(
        db,
        hotel_id=hotel_id,
        reservation_id=reservation.id,
        override_type="room_move",
        reason_code=reason_code,
        notes=notes or f"Room move to {room.room_number}",
        created_by_user_id=moved_by_user_id,
    )
    return event


def preview_ota_rebook_as_direct(
    db: Session,
    *,
    reservation: Reservation,
    hotel_id: int,
    target_category_id: int,
    target_rate_plan_id: Optional[int] = None,
    target_tax_policy_id: Optional[int] = None,
    pricing_channel_code: Optional[str] = None,
    guest_scope: str = "all",
    target_currency: Optional[str] = None,
    discount_pct: float = 0.0,
    total_override: Optional[float] = None,
) -> OTARebookPreview:
    if reservation.hotel_id != hotel_id:
        raise ReservationOperationsError("La reserva no pertenece al hotel activo")
    if reservation.source == ReservationSourceEnum.DIRECT:
        raise ReservationOperationsError("Esta operacion esta pensada para reservas de canales externos")

    target_category = (
        db.query(RoomCategory)
        .filter(RoomCategory.id == target_category_id, RoomCategory.hotel_id == hotel_id)
        .first()
    )
    if not target_category:
        raise ReservationOperationsError("La categoria destino no existe en este hotel")

    target_sellable_product = _resolve_target_sellable_product(
        db,
        hotel_id=hotel_id,
        target_category=target_category,
    )
    target_rate_plan = _resolve_target_rate_plan(
        db,
        hotel_id=hotel_id,
        target_rate_plan_id=target_rate_plan_id,
        target_sellable_product=target_sellable_product,
    )
    target_tax_policy = _resolve_target_tax_policy(
        db,
        hotel_id=hotel_id,
        target_tax_policy_id=target_tax_policy_id,
    )

    if total_override is not None:
        quoted_total_amount = round(total_override, 2)
        subtotal_amount = quoted_total_amount
        tax_amount = 0.0
        fee_amount = 0.0
        commission_amount = 0.0
        net_amount = quoted_total_amount
        currency_code = target_currency or reservation.currency_code or _hotel_default_currency(db, hotel_id)
        fx_rate_snapshot = None
        pricing_source = "manual_override"
    elif target_rate_plan is not None:
        try:
            quote = quote_rate_plan_stay(
                db,
                hotel_id=hotel_id,
                rate_plan_id=target_rate_plan.id,
                check_in=reservation.check_in_date,
                check_out=reservation.check_out_date,
                occupancy=max(reservation.num_adults + reservation.num_children, 1),
                channel_code=pricing_channel_code or reservation.source_provider_code or "direct",
                provider_code=None,
                guest_scope=guest_scope,
                target_currency=target_currency,
                tax_policy_id=target_tax_policy.id if target_tax_policy else None,
            )
        except PricingPolicyError as exc:
            raise ReservationOperationsError(str(exc))

        multiplier = 1 - max(discount_pct, 0.0) / 100.0
        quoted_total_amount = round(quote.gross_total * multiplier, 2)
        subtotal_amount = round(quote.subtotal_amount * multiplier, 2)
        tax_amount = round(quote.tax_amount * multiplier, 2)
        fee_amount = round(quote.fee_amount * multiplier, 2)
        commission_amount = 0.0
        net_amount = quoted_total_amount
        currency_code = quote.output_currency
        fx_rate_snapshot = quote.fx_rate_snapshot
        pricing_source = "commercial_quote"
    else:
        _, _, computed_total, _ = compute_reservation_pricing(
            db,
            target_category_id,
            reservation.check_in_date,
            reservation.check_out_date,
            hotel_id=hotel_id,
        )
        quoted_total_amount = round(computed_total * (1 - max(discount_pct, 0.0) / 100.0), 2)
        subtotal_amount = quoted_total_amount
        tax_amount = 0.0
        fee_amount = 0.0
        commission_amount = 0.0
        net_amount = quoted_total_amount
        currency_code = reservation.currency_code or _hotel_default_currency(db, hotel_id)
        fx_rate_snapshot = None
        pricing_source = "category_fallback"

    deposit_amount = _compute_deposit_amount(db, hotel_id=hotel_id, gross_total=quoted_total_amount)
    amount_delta = round(quoted_total_amount - reservation.total_amount, 2)
    return OTARebookPreview(
        target_category_id=target_category_id,
        target_rate_plan_id=target_rate_plan.id if target_rate_plan else None,
        target_tax_policy_id=target_tax_policy.id if target_tax_policy else None,
        target_sellable_product_id=target_sellable_product.id if target_sellable_product else None,
        pricing_source=pricing_source,
        currency_code=currency_code,
        original_total_amount=reservation.total_amount,
        quoted_total_amount=quoted_total_amount,
        subtotal_amount=subtotal_amount,
        tax_amount=tax_amount,
        fee_amount=fee_amount,
        commission_amount=commission_amount,
        net_amount=net_amount,
        deposit_amount=deposit_amount,
        amount_delta=amount_delta,
        fx_rate_snapshot=fx_rate_snapshot,
    )


def rebook_ota_reservation_as_direct(
    db: Session,
    *,
    reservation: Reservation,
    hotel_id: int,
    target_category_id: int,
    target_rate_plan_id: Optional[int] = None,
    target_tax_policy_id: Optional[int] = None,
    created_by_user_id: Optional[int] = None,
    target_room_id: Optional[int] = None,
    pricing_channel_code: Optional[str] = None,
    guest_scope: str = "all",
    target_currency: Optional[str] = None,
    discount_pct: float = 0.0,
    total_override: Optional[float] = None,
    notes: Optional[str] = None,
) -> OTARebookResult:
    if reservation.hotel_id != hotel_id:
        raise ReservationOperationsError("La reserva no pertenece al hotel activo")
    if reservation.source == ReservationSourceEnum.DIRECT:
        raise ReservationOperationsError("Esta operacion esta pensada para reservas de canales externos")
    if reservation.status in (ReservationStatusEnum.CHECKED_IN, ReservationStatusEnum.CHECKED_OUT):
        raise ReservationOperationsError("No se puede rebookear una reserva ya check-in o check-out")
    if reservation.status == ReservationStatusEnum.CANCELLED:
        raise ReservationOperationsError("La reserva original ya esta cancelada")

    preview = preview_ota_rebook_as_direct(
        db,
        reservation=reservation,
        hotel_id=hotel_id,
        target_category_id=target_category_id,
        target_rate_plan_id=target_rate_plan_id,
        target_tax_policy_id=target_tax_policy_id,
        pricing_channel_code=pricing_channel_code,
        guest_scope=guest_scope,
        target_currency=target_currency,
        discount_pct=discount_pct,
        total_override=total_override,
    )
    delta_amount = preview.amount_delta

    adjustment = ReservationAdjustment(
        hotel_id=hotel_id,
        reservation_id=reservation.id,
        kind=ReservationAdjustmentKindEnum.OTA_CANCEL_AND_REBOOK,
        status=ReservationAdjustmentStatusEnum.DRAFT,
        reason_code="ota_rebook_direct",
        request_source="hotel",
        notes=notes,
        amount_delta=delta_amount,
        currency_code=preview.currency_code,
        external_resolution_status="manual_resolution_required",
        created_by_user_id=created_by_user_id,
    )
    db.add(adjustment)
    db.flush()
    ota_link = _resolve_ota_reservation_link(db, reservation=reservation, hotel_id=hotel_id)
    if ota_link is not None:
        adjustment.ota_reservation_link_id = ota_link.id

    original_note = notes or "Reserva OTA migrada a reserva directa"
    transition_reservation_status(
        db,
        reservation,
        ReservationStatusEnum.CANCELLED,
        hotel_id,
        reason_code="ota_rebook_direct",
        notes=original_note,
        changed_by_user_id=created_by_user_id,
    )

    direct_payload = ReservationCreate(
        guest_id=reservation.guest_id,
        category_id=target_category_id,
        room_id=target_room_id,
        sellable_product_id=preview.target_sellable_product_id,
        rate_plan_id=preview.target_rate_plan_id,
        tax_policy_id=preview.target_tax_policy_id,
        check_in_date=reservation.check_in_date,
        check_out_date=reservation.check_out_date,
        num_adults=reservation.num_adults,
        num_children=reservation.num_children,
        notes=((reservation.notes or "") + "\n[DIRECT REBOOK] " + original_note).strip(),
        source=ReservationSourceEnum.DIRECT,
        external_id=None,
        pricing_channel_code=pricing_channel_code or "direct",
        guest_scope=guest_scope,
        target_currency=preview.currency_code,
    )
    new_reservation = create_reservation(db, direct_payload, hotel_id=hotel_id)
    new_reservation.sellable_product_id = preview.target_sellable_product_id
    new_reservation.rate_plan_id = preview.target_rate_plan_id
    new_reservation.tax_policy_id = preview.target_tax_policy_id
    new_reservation.total_amount = preview.quoted_total_amount
    new_reservation.subtotal_amount = preview.subtotal_amount
    new_reservation.tax_amount = preview.tax_amount
    new_reservation.fee_amount = preview.fee_amount
    new_reservation.commission_amount = preview.commission_amount
    new_reservation.net_amount = preview.net_amount
    new_reservation.currency_code = preview.currency_code
    new_reservation.fx_rate_snapshot = preview.fx_rate_snapshot
    new_reservation.deposit_amount = preview.deposit_amount
    new_reservation.source_provider_code = None
    new_reservation.external_confirmation_code = None
    new_reservation.payment_collection_model = "hotel_collect"
    new_reservation.settlement_status = "pending_hotel_collection"

    adjustment.resulting_reservation_id = new_reservation.id
    adjustment.status = ReservationAdjustmentStatusEnum.APPLIED
    adjustment.external_resolution_status = "pending_hotel_action"
    reservation.settlement_status = "manual_resolution_required"
    if ota_link is not None:
        ota_link.provider_state = OTAReservationLifecycleEnum.MANUAL_RESOLUTION_REQUIRED
        ota_link.sync_status = "manual_resolution_required"
        ota_link.error_message = "Reservation was internally rebooked as direct and requires channel-side cancellation handling"

    record_manual_override_feedback(
        db,
        hotel_id=hotel_id,
        reservation_id=reservation.id,
        override_type="ota_rebook_direct",
        reason_code="ota_rebook_direct",
        notes=original_note,
        created_by_user_id=created_by_user_id,
    )

    billing_adjustment = None
    if abs(delta_amount) > 0.01:
        adjustment_type = BillingAdjustmentTypeEnum.CHARGE if delta_amount > 0 else BillingAdjustmentTypeEnum.CREDIT
        billing_adjustment = BillingAdjustment(
            hotel_id=hotel_id,
            reservation_id=new_reservation.id,
            reservation_adjustment_id=adjustment.id,
            adjustment_type=adjustment_type,
            amount=abs(delta_amount),
            currency_code=new_reservation.currency_code,
            total_amount=delta_amount,
            notes=original_note,
            created_by_user_id=created_by_user_id,
        )
        db.add(billing_adjustment)

    db.flush()
    return OTARebookResult(
        adjustment=adjustment,
        original_reservation=reservation,
        new_reservation=new_reservation,
        billing_adjustment=billing_adjustment,
        preview=preview,
    )


def _resolve_target_sellable_product(
    db: Session,
    *,
    hotel_id: int,
    target_category: RoomCategory,
) -> SellableProduct | None:
    return (
        db.query(SellableProduct)
        .filter(
            SellableProduct.hotel_id == hotel_id,
            SellableProduct.primary_room_category_id == target_category.id,
            SellableProduct.is_active == True,
        )
        .order_by(SellableProduct.sort_order.asc(), SellableProduct.id.asc())
        .first()
    )


def _resolve_target_rate_plan(
    db: Session,
    *,
    hotel_id: int,
    target_rate_plan_id: Optional[int],
    target_sellable_product: SellableProduct | None,
) -> RatePlan | None:
    if target_rate_plan_id is not None:
        rate_plan = (
            db.query(RatePlan)
            .filter(RatePlan.id == target_rate_plan_id, RatePlan.hotel_id == hotel_id, RatePlan.is_active == True)
            .first()
        )
        if not rate_plan:
            raise ReservationOperationsError("La tarifa destino no existe en este hotel")
        return rate_plan
    if target_sellable_product is None:
        return None
    return (
        db.query(RatePlan)
        .filter(
            RatePlan.hotel_id == hotel_id,
            RatePlan.sellable_product_id == target_sellable_product.id,
            RatePlan.is_active == True,
        )
        .order_by(RatePlan.id.asc())
        .first()
    )


def _resolve_target_tax_policy(
    db: Session,
    *,
    hotel_id: int,
    target_tax_policy_id: Optional[int],
) -> TaxPolicy | None:
    query = db.query(TaxPolicy).filter(TaxPolicy.hotel_id == hotel_id, TaxPolicy.is_active == True)
    if target_tax_policy_id is not None:
        policy = query.filter(TaxPolicy.id == target_tax_policy_id).first()
        if not policy:
            raise ReservationOperationsError("La politica impositiva destino no existe en este hotel")
        return policy
    return query.order_by(TaxPolicy.id.asc()).first()


def _compute_deposit_amount(db: Session, *, hotel_id: int, gross_total: float) -> float:
    config = db.query(HotelConfiguration).filter(HotelConfiguration.id == hotel_id).first()
    deposit_pct = config.deposit_percentage if config else 30.0
    return round(gross_total * (deposit_pct / 100.0), 2)


def _resolve_ota_reservation_link(
    db: Session,
    *,
    reservation: Reservation,
    hotel_id: int,
) -> OTAReservationLink | None:
    return (
        db.query(OTAReservationLink)
        .filter(
            OTAReservationLink.hotel_id == hotel_id,
            OTAReservationLink.reservation_id == reservation.id,
        )
        .order_by(OTAReservationLink.id.asc())
        .first()
    )
