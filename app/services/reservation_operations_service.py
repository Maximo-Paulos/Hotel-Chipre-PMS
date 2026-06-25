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
from datetime import date, datetime, timezone
from decimal import Decimal
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
    ReservationStatusHistory,
    RoomMoveEvent,
    RoomMoveTypeEnum,
)
from app.models.reservation import Reservation, ReservationSourceEnum, ReservationStatusEnum
from app.models.room import Room, RoomCategory
from app.models.transaction import Transaction
from app.services.allocation_policy_service import record_manual_override_feedback
from app.schemas.payment_link import PaymentLinkCreate
from app.schemas.reservation import ReservationCreate, ReservationUpdate
from app.schemas.transaction import PaymentRequest
from app.services.payment_link_service import PaymentLinkError, create_link
from app.services.payment_service import PaymentError, process_payment
from app.services.pricing_policy_service import PricingPolicyError, quote_rate_plan_stay
from app.services.read_model_cache import invalidate_hotel_operational_caches
from app.services.reservation_service import (
    ReservationError,
    check_room_availability,
    calculate_reservation_pricing,
    compute_reservation_pricing,
    create_reservation,
    assert_reservation_version,
    transition_reservation_status,
    update_reservation_fields,
)


class ReservationOperationsError(ReservationError):
    """Operational exception with business-friendly semantics."""


def _invalidate_availability_cache(hotel_id: int) -> None:
    try:
        invalidate_hotel_operational_caches(hotel_id)
    except Exception:
        pass


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


@dataclass(slots=True)
class ReservationDateChangeResult:
    original_reservation: Reservation
    reservation: Reservation
    recreated: bool


@dataclass(slots=True)
class ReservationExtensionResult:
    reservation: Reservation
    extension_amount: Decimal
    transaction: Transaction | None = None
    payment_link: object | None = None


def _has_transactions(db: Session, *, hotel_id: int, reservation_id: int) -> bool:
    return (
        db.query(Transaction.id)
        .filter(Transaction.hotel_id == hotel_id, Transaction.reservation_id == reservation_id)
        .first()
        is not None
    )


def change_reservation_dates(
    db: Session,
    *,
    reservation: Reservation,
    hotel_id: int,
    check_in_date: date,
    check_out_date: date,
    client_version: int,
    room_id: int | None = None,
    pricing_mode: str = "recalculate",
    manager_authorized: bool = False,
    changed_by_user_id: int | None = None,
    reason: str | None = None,
) -> ReservationDateChangeResult:
    if reservation.hotel_id != hotel_id:
        raise ReservationOperationsError("La reserva no pertenece al hotel activo")
    assert_reservation_version(reservation, client_version)
    if check_out_date <= check_in_date:
        raise ReservationOperationsError("Check-out must be after check-in")
    if reservation.status in (
        ReservationStatusEnum.CHECKED_IN,
        ReservationStatusEnum.CHECKED_OUT,
        ReservationStatusEnum.CANCELLED,
        ReservationStatusEnum.NO_SHOW,
    ):
        raise ReservationOperationsError("No se pueden cambiar fechas en el estado actual")

    has_transactions = _has_transactions(db, hotel_id=hotel_id, reservation_id=reservation.id)
    target_room_id = room_id if room_id is not None else reservation.room_id

    if not has_transactions:
        previous_status = reservation.status
        reservation.status = ReservationStatusEnum.CANCELLED
        reservation.cancelled_at = datetime.now(timezone.utc)
        reservation.cancelled_by_user_id = changed_by_user_id
        reservation.cancellation_reason_note = reason or "Date change without payments: cancelled and recreated"
        reservation.version = (reservation.version or 0) + 1
        db.add(
            ReservationStatusHistory(
                hotel_id=hotel_id,
                reservation_id=reservation.id,
                from_status=previous_status.value if previous_status else None,
                to_status=ReservationStatusEnum.CANCELLED.value,
                reason_code="date_change_recreate",
                notes=reservation.cancellation_reason_note,
                changed_by_user_id=changed_by_user_id,
            )
        )
        db.flush()
        new_reservation = create_reservation(
            db,
            ReservationCreate(
                guest_id=reservation.guest_id,
                category_id=reservation.category_id,
                room_id=target_room_id,
                sellable_product_id=reservation.sellable_product_id,
                rate_plan_id=reservation.rate_plan_id,
                tax_policy_id=reservation.tax_policy_id,
                company_id=reservation.company_id,
                check_in_date=check_in_date,
                check_out_date=check_out_date,
                num_adults=reservation.num_adults,
                num_children=reservation.num_children,
                notes=((reservation.notes or "") + "\n[DATE CHANGE] Recreated from unpaid reservation").strip(),
                source=reservation.source,
                external_id=None,
                pricing_channel_code=reservation.source_provider_code or reservation.source.value,
                target_currency=reservation.currency_code,
            ),
            hotel_id=hotel_id,
        )
        db.flush()
        return ReservationDateChangeResult(original_reservation=reservation, reservation=new_reservation, recreated=True)

    if not manager_authorized:
        raise ReservationOperationsError("Modificar fechas con pagos requiere gerente, dueno o codueno")

    original_total = Decimal(str(reservation.total_amount or 0))
    update_reservation_fields(
        db,
        reservation,
        data=ReservationUpdate(
            check_in_date=check_in_date,
            check_out_date=check_out_date,
            room_id=room_id,
        ),
        hotel_id=hotel_id,
        changed_by_user_id=changed_by_user_id,
        room_move_reason_code="date_change",
        room_move_notes=reason,
        client_version=client_version,
    )
    if pricing_mode == "keep_current_total":
        reservation.total_amount = original_total
        reservation.subtotal_amount = original_total
        reservation.net_amount = original_total
    reservation.notes = ((reservation.notes or "") + f"\n[DATE CHANGE] {reason or 'Date changed with payments preserved'}").strip()
    db.flush()
    return ReservationDateChangeResult(original_reservation=reservation, reservation=reservation, recreated=False)


def _extension_amount(
    db: Session,
    *,
    reservation: Reservation,
    hotel_id: int,
    new_checkout_date: date,
    pricing_mode: str,
) -> Decimal:
    extra_nights = (new_checkout_date - reservation.check_out_date).days
    if extra_nights <= 0:
        raise ReservationOperationsError("New checkout must be after current checkout")
    if pricing_mode == "original_average":
        current_nights = max((reservation.check_out_date - reservation.check_in_date).days, 1)
        average = Decimal(str(reservation.total_amount or 0)) / Decimal(current_nights)
        return (average * Decimal(extra_nights)).quantize(Decimal("0.01"))
    pricing = calculate_reservation_pricing(
        db,
        category_id=reservation.category_id,
        check_in=reservation.check_out_date,
        check_out=new_checkout_date,
        hotel_id=hotel_id,
        sellable_product_id=reservation.sellable_product_id,
        rate_plan_id=reservation.rate_plan_id,
        tax_policy_id=reservation.tax_policy_id,
        pricing_channel_code=reservation.source_provider_code or reservation.source.value,
        target_currency=reservation.currency_code,
        occupancy=reservation.num_adults + reservation.num_children,
    )
    return Decimal(str(pricing.total_amount)).quantize(Decimal("0.01"))


def extend_reservation_stay(
    db: Session,
    *,
    reservation: Reservation,
    hotel_id: int,
    new_checkout_date: date,
    client_version: int,
    pricing_mode: str,
    payment_action: str,
    immediate_payment: PaymentRequest | None = None,
    payment_link: PaymentLinkCreate | None = None,
    changed_by_user_id: int | None = None,
    notes: str | None = None,
) -> ReservationExtensionResult:
    if reservation.hotel_id != hotel_id:
        raise ReservationOperationsError("La reserva no pertenece al hotel activo")
    assert_reservation_version(reservation, client_version)
    if reservation.status not in (ReservationStatusEnum.CHECKED_IN, ReservationStatusEnum.FULLY_PAID):
        raise ReservationOperationsError("Solo se pueden extender reservas checked-in o fully-paid")
    if reservation.room_id and not check_room_availability(
        db,
        reservation.room_id,
        reservation.check_out_date,
        new_checkout_date,
        hotel_id=hotel_id,
        exclude_reservation_id=reservation.id,
    ):
        raise ReservationOperationsError("La habitacion no esta disponible para la extension")

    amount = _extension_amount(
        db,
        reservation=reservation,
        hotel_id=hotel_id,
        new_checkout_date=new_checkout_date,
        pricing_mode=pricing_mode,
    )
    if amount <= Decimal("0.00"):
        raise ReservationOperationsError("La extension debe tener importe positivo")

    if payment_action == "immediate_payment":
        if immediate_payment is None:
            raise ReservationOperationsError("La extension requiere datos de pago inmediato")
        if immediate_payment.reservation_id != reservation.id:
            raise ReservationOperationsError("El pago inmediato debe pertenecer a esta reserva")
        if Decimal(str(immediate_payment.amount)) < amount:
            raise ReservationOperationsError("El pago inmediato debe cubrir el importe de la extension")
    elif payment_action == "payment_link":
        if payment_link is None:
            raise ReservationOperationsError("La extension requiere generar link de pago")
        if payment_link.reservation_id != reservation.id:
            raise ReservationOperationsError("El link de pago debe pertenecer a esta reserva")
        if Decimal(str(payment_link.requested_amount)) < amount:
            raise ReservationOperationsError("El link de pago debe cubrir el importe de la extension")
    else:
        raise ReservationOperationsError("Accion de pago de extension invalida")

    original_status = reservation.status
    reservation.check_out_date = new_checkout_date
    reservation.total_amount = (Decimal(str(reservation.total_amount or 0)) + amount).quantize(Decimal("0.01"))
    reservation.subtotal_amount = (Decimal(str(reservation.subtotal_amount or 0)) + amount).quantize(Decimal("0.01"))
    reservation.net_amount = (Decimal(str(reservation.net_amount or 0)) + amount).quantize(Decimal("0.01"))
    reservation.notes = ((reservation.notes or "") + f"\n[EXTENSION] {notes or f'Extended to {new_checkout_date}'}").strip()
    reservation.version = (reservation.version or 0) + 1

    transaction = None
    link = None
    try:
        if payment_action == "immediate_payment":
            transaction = process_payment(db, immediate_payment, hotel_id=hotel_id)
            if original_status == ReservationStatusEnum.CHECKED_IN and reservation.status != ReservationStatusEnum.CHECKED_IN:
                reservation.status = ReservationStatusEnum.CHECKED_IN
        else:
            link = create_link(db, hotel_id, payment_link)
    except (PaymentError, PaymentLinkError) as exc:
        raise ReservationOperationsError(str(exc)) from exc

    db.flush()
    _invalidate_availability_cache(hotel_id)
    return ReservationExtensionResult(
        reservation=reservation,
        extension_amount=amount,
        transaction=transaction,
        payment_link=link,
    )


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
    if move_type == RoomMoveTypeEnum.MANUAL_MOVE:
        reservation.allocation_locked = True
        reservation.requires_manual_review = False
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
    _invalidate_availability_cache(hotel_id)
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
