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

from app.models.audit_log import AuditActionEnum
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
from app.services import audit_log_service
from app.services.allocation_policy_service import record_manual_override_feedback
from app.services.guest_room_avoidance_service import record_guest_room_avoidance
from app.services.analytics_facts import touch_reservation_fact_window
from app.schemas.payment_link import PaymentLinkCreate
from app.schemas.reservation import ReservationCreate, ReservationUpdate
from app.schemas.transaction import PaymentRequest
from app.services.payment_link_service import PaymentLinkError, create_link
from app.services.payment_service import PaymentError, process_payment
from app.services.permission_service import (
    PERMISSION_RESERVATION_MOVE,
    PERMISSION_RESERVATION_MOVE_CAPACITY,
    PERMISSION_RESERVATION_MOVE_CATEGORY,
    RESERVATION_MOVE_TIER_PERMISSIONS,
    audit_permission_denied,
    resolve,
)
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
    _apply_pricing_result_to_reservation,
    _validate_reservation_occupancy,
)
from app.services.room_movement_group_service import create_grouped_room_move
from app.services.timezones import hotel_today


class ReservationOperationsError(ReservationError):
    """Operational exception with business-friendly semantics."""


class RoomMovePermissionError(ReservationOperationsError):
    """A caller lacks the permission tier required by a room move's shape."""


_ROOM_MOVE_PERMISSION_DETAILS = {
    PERMISSION_RESERVATION_MOVE: "Para mover dentro de la misma categoría necesitás el permiso 'Mover dentro de categoría'.",
    PERMISSION_RESERVATION_MOVE_CATEGORY: "Para mover a otra categoría necesitás el permiso 'Cambiar de categoría'.",
    PERMISSION_RESERVATION_MOVE_CAPACITY: "Para mover a una categoría con distinta capacidad necesitás el permiso 'Cambiar de capacidad'.",
}


def required_room_move_permission(
    current_category: RoomCategory,
    destination_category: RoomCategory,
) -> str:
    """Return the minimum permission tier for this category-to-category move."""
    if current_category.id == destination_category.id:
        return PERMISSION_RESERVATION_MOVE
    if current_category.max_occupancy == destination_category.max_occupancy:
        return PERMISSION_RESERVATION_MOVE_CATEGORY
    return PERMISSION_RESERVATION_MOVE_CAPACITY


def _room_move_permission_candidates(required_permission: str) -> tuple[str, ...]:
    try:
        required_index = RESERVATION_MOVE_TIER_PERMISSIONS.index(required_permission)
    except ValueError as exc:  # defensive boundary for future tiers
        raise ValueError(f"Unknown room move permission tier: {required_permission}") from exc
    return RESERVATION_MOVE_TIER_PERMISSIONS[required_index:]


def _room_move_categories(
    db: Session,
    *,
    reservation: Reservation,
    destination_room: Room,
    hotel_id: int,
) -> tuple[RoomCategory, RoomCategory]:
    """Load source and destination categories through tenant-scoped rows."""
    if reservation.hotel_id != hotel_id:
        raise ReservationOperationsError("La reserva no pertenece al hotel activo")
    if destination_room.hotel_id != hotel_id:
        raise ReservationOperationsError("La habitacion destino no existe para este hotel")

    current_category_id = reservation.category_id
    if reservation.room_id is not None:
        current_room = (
            db.query(Room)
            .filter(Room.id == reservation.room_id, Room.hotel_id == hotel_id)
            .first()
        )
        if current_room is None:
            raise ReservationOperationsError("La habitacion actual no existe para este hotel")
        current_category_id = current_room.category_id

    current_category = (
        db.query(RoomCategory)
        .filter(RoomCategory.id == current_category_id, RoomCategory.hotel_id == hotel_id)
        .first()
    )
    destination_category = (
        db.query(RoomCategory)
        .filter(RoomCategory.id == destination_room.category_id, RoomCategory.hotel_id == hotel_id)
        .first()
    )
    if current_category is None:
        raise ReservationOperationsError("La categoria de la habitacion actual no existe para este hotel")
    if destination_category is None:
        raise ReservationOperationsError("La categoria de la habitacion destino no existe para este hotel")
    return current_category, destination_category


def enforce_room_move_permission(
    db: Session,
    *,
    reservation: Reservation,
    destination_room: Room,
    hotel_id: int,
    actor_role: str | None,
    actor_user_id: int | None,
) -> tuple[RoomCategory, RoomCategory, str]:
    """Classify a move and enforce its tier for a user-initiated operation.

    Internal allocation paths have no actor role and remain governed by their
    own orchestration policies. Every HTTP move supplies an actor role here.
    """
    current_category, destination_category = _room_move_categories(
        db,
        reservation=reservation,
        destination_room=destination_room,
        hotel_id=hotel_id,
    )
    required_permission = required_room_move_permission(current_category, destination_category)
    if actor_role is None:
        return current_category, destination_category, required_permission

    if any(
        resolve(db, hotel_id, actor_role, permission, user_id=actor_user_id)
        for permission in _room_move_permission_candidates(required_permission)
    ):
        return current_category, destination_category, required_permission

    audit_permission_denied(
        db,
        hotel_id=hotel_id,
        user_id=actor_user_id,
        role=actor_role,
        permission_code=required_permission,
    )
    raise RoomMovePermissionError(_ROOM_MOVE_PERMISSION_DETAILS[required_permission])


def _invalidate_availability_cache(hotel_id: int) -> None:
    try:
        invalidate_hotel_operational_caches(hotel_id)
    except Exception:
        pass


def _touch_facts(db: Session, hotel_id: int, date_from: date, date_to: date) -> None:
    """Same convention as _invalidate_availability_cache: these orchestration
    functions mutate reservation dates/room/total_amount directly instead of
    going through create_reservation/update_reservation_fields (which already
    carry this hook), so they need their own call.
    """
    touch_reservation_fact_window(db, hotel_id=hotel_id, date_from=date_from, date_to=date_to)


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
    status_transitioned: bool = False


@dataclass(slots=True)
class ReservationExtensionResult:
    reservation: Reservation
    extension_amount: Decimal
    transaction: Transaction | None = None
    payment_link: object | None = None
    success: bool = True
    conflicts: list[dict] | None = None


@dataclass(slots=True)
class RoomMoveResult:
    event: "RoomMoveEvent"
    category_changed: bool
    price_action: str
    previous_total_amount: Decimal
    quoted_total_amount: Decimal
    amount_delta: Decimal
    currency_code: str


def add_reservation_charge(
    db: Session,
    *,
    reservation: Reservation,
    hotel_id: int,
    amount: Decimal,
    currency_code: str,
    description: str,
    actor_user_id: int | None = None,
) -> BillingAdjustment:
    """Add a hotel-created consumption or extra charge to an active reservation.

    Charges are stored as billing adjustments, so the financial ledger remains the
    source of truth and the existing checkout-balance guard sees the new amount.
    """
    if reservation.hotel_id != hotel_id:
        raise ReservationOperationsError("La reserva no pertenece al hotel activo")
    if reservation.status in (
        ReservationStatusEnum.CHECKED_OUT,
        ReservationStatusEnum.CANCELLED,
        ReservationStatusEnum.NO_SHOW,
    ):
        raise ReservationOperationsError("Solo se pueden cargar consumos durante una estadia activa")

    normalized_description = description.strip()
    if not normalized_description:
        raise ReservationOperationsError("El detalle del consumo es obligatorio")
    normalized_amount = Decimal(str(amount)).quantize(Decimal("0.01"))
    if normalized_amount <= Decimal("0.00"):
        raise ReservationOperationsError("El importe del consumo debe ser positivo")
    normalized_currency = (currency_code or reservation.currency_code or "ARS").strip().upper()
    if len(normalized_currency) != 3 or not normalized_currency.isalpha():
        raise ReservationOperationsError("La moneda del consumo debe tener tres letras")

    charge = BillingAdjustment(
        hotel_id=hotel_id,
        reservation_id=reservation.id,
        adjustment_type=BillingAdjustmentTypeEnum.CHARGE,
        amount=normalized_amount,
        currency_code=normalized_currency,
        total_amount=normalized_amount,
        notes=normalized_description,
        created_by_user_id=actor_user_id,
    )
    db.add(charge)
    db.flush()
    audit_log_service.safe_create_audit_log(
        db,
        hotel_id=hotel_id,
        table_name="billing_adjustments",
        record_id=charge.id,
        action=AuditActionEnum.CREATE,
        actor_user_id=actor_user_id,
        payload_after=audit_log_service.model_snapshot(charge),
    )
    _invalidate_availability_cache(hotel_id)
    return charge


def _has_transactions(db: Session, *, hotel_id: int, reservation_id: int) -> bool:
    return (
        db.query(Transaction.id)
        .filter(Transaction.hotel_id == hotel_id, Transaction.reservation_id == reservation_id)
        .first()
        is not None
    )


def _reservation_has_payment_or_deposit(db: Session, *, hotel_id: int, reservation: Reservation) -> bool:
    return (
        reservation.status in (ReservationStatusEnum.DEPOSIT_PAID, ReservationStatusEnum.FULLY_PAID)
        or Decimal(str(reservation.amount_paid or 0)) > Decimal("0")
        or _has_transactions(db, hotel_id=hotel_id, reservation_id=reservation.id)
    )


def _extension_conflicts(
    db: Session,
    *,
    reservation: Reservation,
    hotel_id: int,
    new_checkout_date: date,
) -> list[Reservation]:
    if reservation.room_id is None:
        return []
    return (
        db.query(Reservation)
        .filter(
            Reservation.hotel_id == hotel_id,
            Reservation.room_id == reservation.room_id,
            Reservation.id != reservation.id,
            Reservation.deleted_at.is_(None),
            Reservation.status.notin_(
                [
                    ReservationStatusEnum.CANCELLED,
                    ReservationStatusEnum.CHECKED_OUT,
                ]
            ),
            Reservation.check_in_date < new_checkout_date,
            Reservation.check_out_date > reservation.check_out_date,
        )
        .order_by(Reservation.check_in_date.asc(), Reservation.id.asc())
        .all()
    )


def _is_auto_assignable_future_reservation(conflict: Reservation) -> bool:
    return (
        not bool(conflict.allocation_locked)
        and conflict.status
        not in (
            ReservationStatusEnum.CHECKED_IN,
            ReservationStatusEnum.CHECKED_OUT,
            ReservationStatusEnum.CANCELLED,
            ReservationStatusEnum.NO_SHOW,
        )
    )


def _available_room_for_conflict(
    db: Session,
    *,
    hotel_id: int,
    conflict: Reservation,
    extension_room_id: int,
    superior: bool,
) -> Room | None:
    current_category = (
        db.query(RoomCategory)
        .filter(RoomCategory.id == conflict.category_id, RoomCategory.hotel_id == hotel_id)
        .first()
    )
    if current_category is None:
        return None

    category_query = db.query(RoomCategory).filter(RoomCategory.hotel_id == hotel_id)
    if superior:
        category_query = category_query.filter(RoomCategory.base_price_per_night > current_category.base_price_per_night)
    else:
        category_query = category_query.filter(RoomCategory.id == current_category.id)

    categories = category_query.order_by(RoomCategory.base_price_per_night.asc(), RoomCategory.id.asc()).all()
    for category in categories:
        rooms = (
            db.query(Room)
            .filter(
                Room.hotel_id == hotel_id,
                Room.category_id == category.id,
                Room.deleted_at.is_(None),
                Room.is_active == True,
                Room.id != extension_room_id,
            )
            .order_by(Room.room_number.asc(), Room.id.asc())
            .all()
        )
        for room in rooms:
            if check_room_availability(
                db,
                room.id,
                conflict.check_in_date,
                conflict.check_out_date,
                hotel_id=hotel_id,
                exclude_reservation_id=conflict.id,
            ):
                return room
    return None


def resolve_extension_conflict(
    db: Session,
    *,
    reservation: Reservation,
    hotel_id: int,
    new_checkout_date: date,
    actor_user_id: int | None = None,
) -> dict:
    conflicts = _extension_conflicts(
        db,
        reservation=reservation,
        hotel_id=hotel_id,
        new_checkout_date=new_checkout_date,
    )
    if not conflicts:
        return {"resolved": True, "conflicts": [], "actions": []}

    unresolved: list[dict] = []
    actions: list[dict] = []
    extension_room_id = reservation.room_id
    if extension_room_id is None:
        return {"resolved": True, "conflicts": [], "actions": []}

    for conflict in conflicts:
        details = {
            "reservation_id": conflict.id,
            "confirmation_code": conflict.confirmation_code,
            "room_id": conflict.room_id,
            "check_in_date": conflict.check_in_date.isoformat(),
            "check_out_date": conflict.check_out_date.isoformat(),
        }
        if _reservation_has_payment_or_deposit(db, hotel_id=hotel_id, reservation=conflict):
            unresolved.append(
                {
                    **details,
                    "reason": "future_reservation_has_payment_or_deposit",
                    "message": "La reserva futura tiene pago o sena y no puede ser desplazada automaticamente",
                }
            )
            continue

        if _is_auto_assignable_future_reservation(conflict):
            equivalent = _available_room_for_conflict(
                db,
                hotel_id=hotel_id,
                conflict=conflict,
                extension_room_id=extension_room_id,
                superior=False,
            )
            if equivalent is not None:
                reason = (
                    "Reserva futura movida a habitacion equivalente para resolver conflicto "
                    f"por extension de reserva {reservation.confirmation_code}"
                )
                group, event = create_grouped_room_move(
                    db,
                    hotel_id=hotel_id,
                    reservation=conflict,
                    to_room=equivalent,
                    trigger_reason="extension_conflict",
                    reason_code="extension_conflict_equivalent",
                    reason_note=reason,
                    move_type=RoomMoveTypeEnum.AUTO_ASSIGNMENT,
                    trigger_event="extension_conflict",
                    created_by_user_id=actor_user_id,
                    group_notes=reason,
                )
                actions.append(
                    {
                        **details,
                        "action": "moved_equivalent",
                        "to_room_id": equivalent.id,
                        "movement_group_id": group.id,
                        "move_event_id": event.id,
                    }
                )
                continue

            superior = _available_room_for_conflict(
                db,
                hotel_id=hotel_id,
                conflict=conflict,
                extension_room_id=extension_room_id,
                superior=True,
            )
            if superior is not None:
                reason = (
                    "Reserva futura actualizada a habitacion superior para resolver conflicto "
                    f"por extension de reserva {reservation.confirmation_code}"
                )
                group, event = create_grouped_room_move(
                    db,
                    hotel_id=hotel_id,
                    reservation=conflict,
                    to_room=superior,
                    trigger_reason="extension_conflict",
                    reason_code="extension_conflict_upgrade",
                    reason_note=reason,
                    move_type=RoomMoveTypeEnum.UPGRADE,
                    trigger_event="extension_conflict",
                    created_by_user_id=actor_user_id,
                    group_notes=reason,
                )
                actions.append(
                    {
                        **details,
                        "action": "moved_superior",
                        "to_room_id": superior.id,
                        "movement_group_id": group.id,
                        "move_event_id": event.id,
                    }
                )
                continue

        before = audit_log_service.model_snapshot(conflict)
        previous_room_id = conflict.room_id
        conflict.room_id = None
        conflict.allocation_status = "pending_assignment"
        conflict.requires_manual_review = True
        conflict.notes = (
            (conflict.notes or "")
            + f"\n[EXTENSION CONFLICT] Room assignment released for extension of {reservation.confirmation_code}"
        ).strip()
        conflict.version = (conflict.version or 0) + 1
        audit_log_service.queue_audit_log(
            db,
            hotel_id=hotel_id,
            table_name="reservations",
            record_id=conflict.id,
            action=AuditActionEnum.UPDATE,
            actor_user_id=actor_user_id,
            payload_before=before,
            payload_after=audit_log_service.model_snapshot(conflict),
        )
        actions.append(
            {
                **details,
                "action": "assignment_released",
                "from_room_id": previous_room_id,
                "message": "Reserva futura sin pago liberada para revision manual",
            }
        )

    return {"resolved": not unresolved, "conflicts": unresolved, "actions": actions}


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
    if check_in_date < hotel_today(db, hotel_id):
        raise ReservationOperationsError("No se puede cambiar la fecha de check-in a una fecha en el pasado")
    original_check_in = reservation.check_in_date
    original_check_out = reservation.check_out_date
    if reservation.status in (
        ReservationStatusEnum.CHECKED_IN,
        ReservationStatusEnum.CHECKED_OUT,
        ReservationStatusEnum.CANCELLED,
        ReservationStatusEnum.NO_SHOW,
    ):
        raise ReservationOperationsError("No se pueden cambiar fechas en el estado actual")

    tiene_pago = (
        reservation.status in (ReservationStatusEnum.DEPOSIT_PAID, ReservationStatusEnum.FULLY_PAID)
        or Decimal(str(reservation.amount_paid or 0)) > Decimal("0")
        or _has_transactions(db, hotel_id=hotel_id, reservation_id=reservation.id)
    )
    target_room_id = room_id if room_id is not None else reservation.room_id

    if not tiene_pago:
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
        # create_reservation() below only touches the *new* reservation's
        # window; this one is now cancelled and must disappear from its
        # original window's facts immediately (revenue was previously
        # counted there).
        _touch_facts(db, hotel_id, original_check_in, original_check_out)
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
    status_transitioned = False
    if (
        reservation.status != ReservationStatusEnum.FULLY_PAID
        and Decimal(str(reservation.total_amount or 0)) <= Decimal(str(reservation.amount_paid or 0))
    ):
        transition_reservation_status(
            db,
            reservation,
            ReservationStatusEnum.FULLY_PAID,
            hotel_id,
            reason_code="date_change_auto_fully_paid",
            notes="Date change recalculated total below or equal to paid amount",
            changed_by_user_id=changed_by_user_id,
        )
        status_transitioned = True
    reservation.notes = ((reservation.notes or "") + f"\n[DATE CHANGE] {reason or 'Date changed with payments preserved'}").strip()
    db.flush()
    # update_reservation_fields() already touched the union of old/new dates,
    # but a keep_current_total override (or the FULLY_PAID transition above)
    # changes revenue/status *after* that touch ran -- re-touch with the
    # final values so the fact rows don't lag behind this request.
    _touch_facts(
        db,
        hotel_id,
        min(original_check_in, reservation.check_in_date),
        max(original_check_out, reservation.check_out_date),
    )
    return ReservationDateChangeResult(
        original_reservation=reservation,
        reservation=reservation,
        recreated=False,
        status_transitioned=status_transitioned,
    )


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
    if new_checkout_date <= reservation.check_out_date:
        raise ReservationOperationsError("New checkout must be after current checkout")
    conflict_resolution = resolve_extension_conflict(
        db,
        reservation=reservation,
        hotel_id=hotel_id,
        new_checkout_date=new_checkout_date,
        actor_user_id=changed_by_user_id,
    )
    if not conflict_resolution["resolved"]:
        return ReservationExtensionResult(
            reservation=reservation,
            extension_amount=Decimal("0.00"),
            success=False,
            conflicts=conflict_resolution["conflicts"],
        )
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
    original_check_out = reservation.check_out_date
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
            transaction = process_payment(db, immediate_payment, hotel_id=hotel_id, actor_user_id=changed_by_user_id)
            if original_status == ReservationStatusEnum.CHECKED_IN and reservation.status != ReservationStatusEnum.CHECKED_IN:
                reservation.status = ReservationStatusEnum.CHECKED_IN
        else:
            link = create_link(db, hotel_id, payment_link)
    except (PaymentError, PaymentLinkError) as exc:
        raise ReservationOperationsError(str(exc)) from exc

    db.flush()
    _invalidate_availability_cache(hotel_id)
    _touch_facts(db, hotel_id, reservation.check_in_date, max(original_check_out, reservation.check_out_date))
    return ReservationExtensionResult(
        reservation=reservation,
        extension_amount=amount,
        transaction=transaction,
        payment_link=link,
        success=True,
        conflicts=None,
    )


def move_reservation_room(
    db: Session,
    *,
    reservation: Reservation,
    to_room_id: int,
    hotel_id: int,
    moved_by_user_id: Optional[int] = None,
    actor_role: Optional[str] = None,
    reason_code: Optional[str] = None,
    notes: Optional[str] = None,
    move_type: RoomMoveTypeEnum = RoomMoveTypeEnum.MANUAL_MOVE,
    price_action: str = "keep",
) -> RoomMoveResult:
    if price_action not in ("keep", "reprice"):
        raise ReservationOperationsError("price_action debe ser 'keep' o 'reprice'")
    if reason_code is None or not reason_code.strip():
        raise ReservationOperationsError("reason_code is required for room moves")
    reason_code = reason_code.strip()

    room = (
        db.query(Room)
        .filter(Room.id == to_room_id, Room.hotel_id == hotel_id)
        .enable_eagerloads(False)
        .with_for_update()
        .first()
    )
    if not room:
        raise ReservationOperationsError("La habitacion destino no existe para este hotel")

    current_category, destination_category, _required_permission = enforce_room_move_permission(
        db,
        reservation=reservation,
        destination_room=room,
        hotel_id=hotel_id,
        actor_role=actor_role,
        actor_user_id=moved_by_user_id,
    )

    if not check_room_availability(
        db,
        room.id,
        reservation.check_in_date,
        reservation.check_out_date,
        hotel_id=hotel_id,
        exclude_reservation_id=reservation.id,
    ):
        raise ReservationOperationsError("La habitacion destino no esta disponible para esas fechas")

    category_changed = destination_category.id != current_category.id
    if category_changed:
        try:
            _validate_reservation_occupancy(destination_category, reservation.num_adults, reservation.num_children)
        except ReservationError as exc:
            raise ReservationOperationsError(str(exc)) from exc

    previous_total = Decimal(str(reservation.total_amount or 0)).quantize(Decimal("0.01"))
    # sellable_product_id/rate_plan_id are tied to the *current* category's commercial
    # setup; when the category changes they may not be compatible with the new one, so
    # let calculate_reservation_pricing re-infer them for the destination category.
    pricing = calculate_reservation_pricing(
        db,
        category_id=room.category_id,
        check_in=reservation.check_in_date,
        check_out=reservation.check_out_date,
        hotel_id=hotel_id,
        sellable_product_id=None if category_changed else reservation.sellable_product_id,
        rate_plan_id=None if category_changed else reservation.rate_plan_id,
        tax_policy_id=reservation.tax_policy_id,
        pricing_channel_code=reservation.source_provider_code or reservation.source.value,
        target_currency=reservation.currency_code,
        occupancy=reservation.num_adults + reservation.num_children,
    )
    quoted_total = Decimal(str(pricing.total_amount)).quantize(Decimal("0.01"))
    amount_delta = (quoted_total - previous_total).quantize(Decimal("0.01"))

    previous_room_id = reservation.room_id
    status_value = reservation.status.value if hasattr(reservation.status, "value") else str(reservation.status)
    reservation.room_id = room.id
    reservation.category_id = room.category_id
    if price_action == "reprice":
        _apply_pricing_result_to_reservation(reservation, pricing)
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
        reason_note=notes,
        trigger_event="manual" if move_type == RoomMoveTypeEnum.MANUAL_MOVE else None,
        state_before=f"status={status_value};room_id={previous_room_id}",
        state_after=f"status={status_value};room_id={room.id}",
        notes=notes,
        created_by_user_id=moved_by_user_id,
    )
    db.add(event)
    db.flush()
    if move_type == RoomMoveTypeEnum.MANUAL_MOVE and reason_code == "guest_complaint" and previous_room_id is not None:
        record_guest_room_avoidance(
            db,
            hotel_id=hotel_id,
            guest_id=reservation.guest_id,
            room_id=previous_room_id,
            source_move_event_id=event.id,
            reason=notes,
            created_by_user_id=moved_by_user_id,
        )
    _invalidate_availability_cache(hotel_id)
    _touch_facts(db, hotel_id, reservation.check_in_date, reservation.check_out_date)
    record_manual_override_feedback(
        db,
        hotel_id=hotel_id,
        reservation_id=reservation.id,
        override_type="room_move",
        reason_code=reason_code,
        notes=notes or f"Room move to {room.room_number}",
        created_by_user_id=moved_by_user_id,
    )
    return RoomMoveResult(
        event=event,
        category_changed=category_changed,
        price_action=price_action,
        previous_total_amount=previous_total,
        quoted_total_amount=quoted_total,
        amount_delta=amount_delta,
        currency_code=pricing.currency_code,
    )


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
