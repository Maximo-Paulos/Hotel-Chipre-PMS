"""
Reservation operations service.

Handles operational scenarios that go beyond a plain reservation update:
- OTA reservation moved to a direct reservation
- manual room moves with audit trail
- billing adjustments associated with operational changes
- commercial previews for OTA-to-direct rebooks
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from hashlib import sha256
from typing import Optional

from sqlalchemy.orm import Session

from app.models.audit_log import AuditActionEnum
from app.models.commercial import RatePlan, SellableProduct, TaxPolicy
from app.models.company import Company
from app.models.hotel_config import HotelConfiguration
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
from app.models.ota_core import OTAReservationLifecycleEnum, OTAReservationLink
from app.models.reservation import (
    Reservation,
    ReservationSourceEnum,
    ReservationStatusEnum,
)
from app.models.room import Room, RoomCategory
from app.models.transaction import PaymentMethodEnum, Transaction, TransactionTypeEnum
from app.schemas.payment_link import PaymentLinkCreate
from app.schemas.reservation import ReservationCreate, ReservationUpdate
from app.schemas.transaction import PaymentRequest
from app.services import audit_log_service
from app.services.allocation_policy_service import record_manual_override_feedback
from app.services.analytics_facts import touch_reservation_fact_window
from app.services.financial_ledger import (
    reservation_has_any_transaction,
    reservation_has_payment_or_deposit,
)
from app.services.guest_room_avoidance_service import record_guest_room_avoidance
from app.services.housekeeping_checklist_policy import (
    open_housekeeping_checklist_exists,
)
from app.services.payment_link_service import PaymentLinkError, create_link
from app.services.payment_service import (
    MANUAL_REFERENCE_METHODS,
    PaymentError,
    process_payment,
    sync_reservation_financial_status,
)
from app.services.permission_service import (
    PERMISSION_COMPANY_MANAGE,
    PERMISSION_RESERVATION_MOVE,
    PERMISSION_RESERVATION_MOVE_CAPACITY,
    PERMISSION_RESERVATION_MOVE_CATEGORY,
    PERMISSION_RESERVATION_RATE_ADJUST,
    PERMISSION_RESERVATION_ROOM_DIRTY_OVERRIDE,
    RESERVATION_MOVE_TIER_PERMISSIONS,
    audit_permission_denied,
    resolve,
)
from app.services.pricing_policy_service import PricingPolicyError, quote_rate_plan_stay
from app.services.read_model_cache import invalidate_hotel_operational_caches
from app.services.reservation_service import (
    ReservationError,
    _apply_corporate_pricing,
    _apply_pricing_result_to_reservation,
    _notify_reservation_event,
    _validate_reservation_occupancy,
    calculate_reservation_pricing,
    check_room_availability,
    compute_reservation_pricing,
    create_reservation,
    lock_reservation_version,
    manual_override_total_for_nights,
    transition_reservation_status,
    update_reservation_fields,
)
from app.services.room_block_service import room_has_active_block
from app.services.room_movement_group_service import (
    create_grouped_room_move,
    lock_room_for_movement,
    reservation_actual_guest_count,
    sync_room_statuses_after_move,
)
from app.services.row_locks import lock_query
from app.services.timezones import hotel_today


class ReservationOperationsError(ReservationError):
    """Operational exception with business-friendly semantics."""


class RoomMovePermissionError(ReservationOperationsError):
    """A caller lacks the permission tier required by a room move's shape."""


class ReservationExtensionImpactConfirmationError(ReservationOperationsError):
    """The room reallocation plan changed or was not explicitly confirmed."""

    def __init__(self, code: str, impact_plan: dict | None = None):
        self.code = code
        self.impact_plan = impact_plan
        if code == "impact_confirmation_required":
            message = "Confirmá el impacto de reasignación antes de aplicar la extensión."
        else:
            message = "El impacto cambió desde la vista previa. Revisá el plan actualizado."
        super().__init__(message)


def _validate_direct_individual_extension_target(
    db: Session,
    *,
    reservation: Reservation,
    hotel_id: int,
) -> None:
    """Allow the private-stay quote/extension path only for unlinked direct stays."""
    if reservation.hotel_id != hotel_id:
        raise ReservationOperationsError("La reserva no pertenece al hotel activo")
    if (
        reservation.company_id is not None
        or reservation.group_id is not None
        or reservation.source != ReservationSourceEnum.DIRECT
        or reservation.source_provider_code
        or reservation.external_id
    ):
        raise ReservationOperationsError(
            "La extensión individual solo está disponible para reservas directas sin empresa, grupo ni vínculo externo"
        )
    linked_ota = (
        db.query(OTAReservationLink.id)
        .filter(
            OTAReservationLink.hotel_id == hotel_id,
            OTAReservationLink.reservation_id == reservation.id,
        )
        .first()
    )
    if linked_ota is not None:
        raise ReservationOperationsError(
            "La extensión individual no está disponible para reservas vinculadas a un canal externo"
        )


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
    actor_role: str,
    actor_user_id: int | None,
) -> tuple[RoomCategory, RoomCategory, str]:
    """Classify a move and enforce its tier for a user-initiated operation.

    The caller must supply a resolved actor role. Missing identity context is
    denied rather than treated as an implicit internal/system authorization.
    """
    current_category, destination_category = _room_move_categories(
        db,
        reservation=reservation,
        destination_room=destination_room,
        hotel_id=hotel_id,
    )
    required_permission = required_room_move_permission(current_category, destination_category)
    if not actor_role:
        audit_permission_denied(
            db,
            hotel_id=hotel_id,
            user_id=actor_user_id,
            role=None,
            permission_code=required_permission,
        )
        raise RoomMovePermissionError("No se pudo determinar el rol para autorizar el cambio de habitacion.")

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


def _touch_facts(
    db: Session,
    hotel_id: int,
    date_from: date,
    date_to: date,
    *,
    reservation_id: int | None = None,
    previous_room_id: int | None = None,
) -> None:
    """Same convention as _invalidate_availability_cache: these orchestration
    functions mutate reservation dates/room/total_amount directly instead of
    going through create_reservation/update_reservation_fields (which already
    carry this hook), so they need their own call.
    """
    touch_reservation_fact_window(
        db,
        hotel_id=hotel_id,
        date_from=date_from,
        date_to=date_to,
        reservation_id=reservation_id,
        previous_room_id=previous_room_id,
    )


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
    impact_plan: dict | None = None


@dataclass(slots=True)
class RoomMoveResult:
    event: "RoomMoveEvent"
    category_changed: bool
    price_action: str
    previous_total_amount: Decimal
    quoted_total_amount: Decimal
    amount_delta: Decimal
    currency_code: str
    origin_room_disposition: str | None = None
    origin_room_disposition_note: str | None = None
    origin_room_status_before: str | None = None
    origin_room_status_after: str | None = None


def add_reservation_charge(
    db: Session,
    *,
    reservation: Reservation,
    hotel_id: int,
    amount: Decimal,
    currency_code: str | None,
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
    reservation_currency = (reservation.currency_code or "ARS").strip().upper()
    normalized_currency = (currency_code or reservation_currency).strip().upper()
    if (
        len(normalized_currency) != 3
        or not normalized_currency.isascii()
        or not normalized_currency.isalpha()
    ):
        raise ReservationOperationsError("La moneda del consumo debe tener tres letras")
    if normalized_currency != reservation_currency:
        raise ReservationOperationsError(
            f"La moneda del consumo ({normalized_currency}) debe coincidir con la reserva ({reservation_currency})"
        )

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
    audit_log_service.create_audit_log(
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


def _extension_conflicts(
    db: Session,
    *,
    reservation: Reservation,
    hotel_id: int,
    new_checkout_date: date,
    for_update: bool = True,
) -> list[Reservation]:
    if reservation.room_id is None:
        return []
    overlapping_query = (
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
                    ReservationStatusEnum.NO_SHOW,
                ]
            ),
            Reservation.check_in_date < new_checkout_date,
            Reservation.check_out_date > reservation.check_out_date,
        )
        .order_by(Reservation.check_in_date.asc(), Reservation.id.asc())
        .populate_existing()
    )
    if for_update:
        overlapping_query = lock_query(overlapping_query, Reservation)
    return overlapping_query.all()


def _extension_no_show_reservations(
    db: Session,
    *,
    reservation: Reservation,
    hotel_id: int,
    new_checkout_date: date,
    for_update: bool,
) -> list[Reservation]:
    if reservation.room_id is None:
        return []
    query = (
        db.query(Reservation)
        .filter(
            Reservation.hotel_id == hotel_id,
            Reservation.room_id == reservation.room_id,
            Reservation.id != reservation.id,
            Reservation.deleted_at.is_(None),
            Reservation.status == ReservationStatusEnum.NO_SHOW,
            Reservation.check_in_date < new_checkout_date,
            Reservation.check_out_date > reservation.check_out_date,
        )
        .order_by(Reservation.check_in_date.asc(), Reservation.id.asc())
        .populate_existing()
    )
    if for_update:
        query = lock_query(query, Reservation)
    return query.all()


def _is_auto_assignable_future_reservation(conflict: Reservation) -> bool:
    return (
        not bool(conflict.allocation_locked)
        and conflict.status
        not in (
            ReservationStatusEnum.PARTIAL_CHECK_IN,
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
    lock_for_update: bool = False,
    planned_assignments: list[tuple[int, date, date]] | None = None,
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
            if any(
                planned_room_id == room.id
                and planned_start < conflict.check_out_date
                and planned_end > conflict.check_in_date
                for planned_room_id, planned_start, planned_end in (planned_assignments or [])
            ):
                continue
            if not check_room_availability(
                db,
                room.id,
                conflict.check_in_date,
                conflict.check_out_date,
                hotel_id=hotel_id,
                exclude_reservation_id=conflict.id,
            ):
                continue
            if lock_for_update:
                room = lock_room_for_movement(db, hotel_id=hotel_id, room_id=room.id)
                if room is None or not check_room_availability(
                    db,
                    room.id,
                    conflict.check_in_date,
                    conflict.check_out_date,
                    hotel_id=hotel_id,
                    exclude_reservation_id=conflict.id,
                    known_room=room,
                ):
                    continue
            return room
    return None


def _extension_room_label(db: Session, *, hotel_id: int, room_id: int | None) -> str | None:
    if room_id is None:
        return None
    return (
        db.query(Room.room_number)
        .filter(Room.id == room_id, Room.hotel_id == hotel_id)
        .scalar()
    )


def _public_extension_action(
    *,
    action: str,
    room_label: str | None,
    conflict: Reservation,
    reason_code: str | None = None,
) -> dict:
    result = {
        "action": action,
        "room_label": room_label or "Sin habitación asignada",
        "check_in_date": conflict.check_in_date.isoformat(),
        "check_out_date": conflict.check_out_date.isoformat(),
    }
    if conflict.confirmation_code:
        result["confirmation_code"] = conflict.confirmation_code
    if reason_code:
        result["reason_code"] = reason_code
    return result


def _extension_impact_fingerprint(
    *,
    root_room_label: str | None,
    reservation: Reservation,
    new_checkout_date: date,
    can_manage_company_reservations: bool,
    root_room_blocked: bool,
    planned: list[dict],
) -> str:
    canonical = {
        "hotel_id": reservation.hotel_id,
        "reservation_id": reservation.id,
        "reservation_version": reservation.version or 0,
        "reservation_status": str(getattr(reservation.status, "value", reservation.status)),
        "current_checkout_date": reservation.check_out_date.isoformat(),
        "new_checkout_date": new_checkout_date.isoformat(),
        "room_id": reservation.room_id,
        "room_label": root_room_label,
        "can_manage_company_reservations": can_manage_company_reservations,
        "root_room_blocked": root_room_blocked,
        "actions": [
            {
                "reservation_id": item["reservation"].id,
                "version": item["reservation"].version or 0,
                "status": str(
                    getattr(item["reservation"].status, "value", item["reservation"].status)
                ),
                "company_id": item["reservation"].company_id,
                "allocation_locked": bool(item["reservation"].allocation_locked),
                "check_in_date": item["reservation"].check_in_date.isoformat(),
                "check_out_date": item["reservation"].check_out_date.isoformat(),
                "confirmation_code": item["reservation"].confirmation_code,
                "room_id": item["reservation"].room_id,
                "room_label": item.get("from_room_label"),
                "has_payment_or_deposit": item["has_payment_or_deposit"],
                "action": item["action"],
                "reason_code": item.get("reason_code"),
                "to_room_id": item["to_room"].id if item.get("to_room") else None,
                "to_room_label": item["to_room"].room_number if item.get("to_room") else None,
            }
            for item in planned
        ],
    }
    payload = json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return sha256(payload.encode("utf-8")).hexdigest()


def _build_extension_impact_plan(
    db: Session,
    *,
    reservation: Reservation,
    hotel_id: int,
    new_checkout_date: date,
    can_manage_company_reservations: bool,
    lock_rows: bool,
) -> dict:
    conflicts = _extension_conflicts(
        db,
        reservation=reservation,
        hotel_id=hotel_id,
        new_checkout_date=new_checkout_date,
        for_update=lock_rows,
    )
    no_show_reservations = _extension_no_show_reservations(
        db,
        reservation=reservation,
        hotel_id=hotel_id,
        new_checkout_date=new_checkout_date,
        for_update=lock_rows,
    )
    conflicts.extend(no_show_reservations)
    conflicts.sort(key=lambda item: (item.check_in_date, item.id))
    if not conflicts or reservation.room_id is None:
        return {
            "resolved": True,
            "conflicts": [],
            "planned_actions": [],
            "impact_plan": None,
        }

    unresolved: list[dict] = []
    planned: list[dict] = []
    public_actions: list[dict] = []
    planned_assignments: list[tuple[int, date, date]] = []
    extension_room_id = reservation.room_id

    for conflict in conflicts:
        details = {
            "reservation_id": conflict.id,
            "confirmation_code": conflict.confirmation_code,
            "room_id": conflict.room_id,
            "check_in_date": conflict.check_in_date.isoformat(),
            "check_out_date": conflict.check_out_date.isoformat(),
        }
        has_payment_or_deposit = reservation_has_payment_or_deposit(
            db,
            hotel_id=hotel_id,
            reservation=conflict,
        )
        plan_item = {
            "reservation": conflict,
            "has_payment_or_deposit": has_payment_or_deposit,
            "from_room_label": _extension_room_label(
                db, hotel_id=hotel_id, room_id=conflict.room_id
            ),
            "to_room": None,
        }
        if conflict.status == ReservationStatusEnum.NO_SHOW:
            reason_code = "no_show_reservation_blocks_extension"
            unresolved.append(
                {
                    **details,
                    "reason": reason_code,
                    "message": "La reserva marcada como no-show requiere revisión antes de extender esta habitación.",
                }
            )
            plan_item.update(action="blocked", reason_code=reason_code)
            public_actions.append(
                _public_extension_action(
                    action="blocked",
                    room_label=plan_item["from_room_label"],
                    conflict=conflict,
                    reason_code=reason_code,
                )
            )
            planned.append(plan_item)
            continue
        if conflict.company_id is not None and not can_manage_company_reservations:
            reason_code = "company_reservation_requires_management_permission"
            unresolved.append(
                {
                    **details,
                    "reason": reason_code,
                    "message": "Se necesita permiso para reasignar una reserva de empresa en conflicto.",
                }
            )
            plan_item.update(action="blocked", reason_code=reason_code)
            public_actions.append(
                _public_extension_action(
                    action="blocked",
                    room_label=plan_item["from_room_label"],
                    conflict=conflict,
                    reason_code=reason_code,
                )
            )
            planned.append(plan_item)
            continue
        if has_payment_or_deposit:
            reason_code = "future_reservation_has_payment_or_deposit"
            unresolved.append(
                {
                    **details,
                    "reason": reason_code,
                    "message": "La reserva futura tiene pago o seña y no puede ser desplazada automáticamente.",
                }
            )
            plan_item.update(action="blocked", reason_code=reason_code)
            public_actions.append(
                _public_extension_action(
                    action="blocked",
                    room_label=plan_item["from_room_label"],
                    conflict=conflict,
                    reason_code=reason_code,
                )
            )
            planned.append(plan_item)
            continue

        if not _is_auto_assignable_future_reservation(conflict):
            if conflict.status in {
                ReservationStatusEnum.PARTIAL_CHECK_IN,
                ReservationStatusEnum.CHECKED_IN,
            }:
                reason_code = "checked_in_reservation_cannot_be_reallocated"
                message = "La reserva en estadía no puede ser reasignada por una extensión."
            elif conflict.allocation_locked:
                reason_code = "reservation_allocation_locked"
                message = "La asignación de habitación está bloqueada y requiere revisión manual."
            else:
                reason_code = "reservation_not_reallocatable"
                message = "La reserva requiere revisión antes de cambiar su asignación."
            unresolved.append({**details, "reason": reason_code, "message": message})
            plan_item.update(action="blocked", reason_code=reason_code)
            public_actions.append(
                _public_extension_action(
                    action="blocked",
                    room_label=plan_item["from_room_label"],
                    conflict=conflict,
                    reason_code=reason_code,
                )
            )
            planned.append(plan_item)
            continue

        if _is_auto_assignable_future_reservation(conflict):
            equivalent = _available_room_for_conflict(
                db,
                hotel_id=hotel_id,
                conflict=conflict,
                extension_room_id=extension_room_id,
                superior=False,
                lock_for_update=lock_rows,
                planned_assignments=planned_assignments,
            )
            if equivalent is not None:
                plan_item.update(action="moved_equivalent", to_room=equivalent)
                planned_assignments.append(
                    (equivalent.id, conflict.check_in_date, conflict.check_out_date)
                )
                public_actions.append(
                    _public_extension_action(
                        action="moved_equivalent",
                        room_label=f"{plan_item['from_room_label'] or 'Sin habitación'} → {equivalent.room_number}",
                        conflict=conflict,
                    )
                )
                planned.append(plan_item)
                continue

            superior = _available_room_for_conflict(
                db,
                hotel_id=hotel_id,
                conflict=conflict,
                extension_room_id=extension_room_id,
                superior=True,
                lock_for_update=lock_rows,
                planned_assignments=planned_assignments,
            )
            if superior is not None:
                plan_item.update(action="moved_superior", to_room=superior)
                planned_assignments.append(
                    (superior.id, conflict.check_in_date, conflict.check_out_date)
                )
                public_actions.append(
                    _public_extension_action(
                        action="moved_superior",
                        room_label=f"{plan_item['from_room_label'] or 'Sin habitación'} → {superior.room_number}",
                        conflict=conflict,
                    )
                )
                planned.append(plan_item)
                continue

        plan_item.update(action="assignment_released")
        public_actions.append(
            _public_extension_action(
                action="assignment_released",
                room_label=plan_item["from_room_label"],
                conflict=conflict,
            )
        )
        planned.append(plan_item)

    root_room_blocked = room_has_active_block(
        db,
        hotel_id=hotel_id,
        room_id=extension_room_id,
        start_date=reservation.check_out_date,
        end_date=new_checkout_date,
    )
    fingerprint = _extension_impact_fingerprint(
        root_room_label=_extension_room_label(db, hotel_id=hotel_id, room_id=reservation.room_id),
        reservation=reservation,
        new_checkout_date=new_checkout_date,
        can_manage_company_reservations=can_manage_company_reservations,
        root_room_blocked=root_room_blocked,
        planned=planned,
    )
    return {
        "resolved": not unresolved and not root_room_blocked,
        "conflicts": unresolved,
        "planned_actions": planned,
        "impact_plan": {"fingerprint": fingerprint, "actions": public_actions},
        "root_room_blocked": root_room_blocked,
    }


def plan_reservation_extension_impact(
    db: Session,
    *,
    reservation: Reservation,
    hotel_id: int,
    new_checkout_date: date,
    can_manage_company_reservations: bool = False,
) -> dict | None:
    """Return a read-only, PII-minimized extension impact plan when conflicts exist."""
    if reservation.room_id is None:
        return None
    if room_has_active_block(
        db,
        hotel_id=hotel_id,
        room_id=reservation.room_id,
        start_date=reservation.check_out_date,
        end_date=new_checkout_date,
    ):
        raise ReservationOperationsError("La habitación no está disponible para la extensión")
    return _build_extension_impact_plan(
        db,
        reservation=reservation,
        hotel_id=hotel_id,
        new_checkout_date=new_checkout_date,
        can_manage_company_reservations=can_manage_company_reservations,
        lock_rows=False,
    )["impact_plan"]


def resolve_extension_conflict(
    db: Session,
    *,
    reservation: Reservation,
    hotel_id: int,
    new_checkout_date: date,
    actor_user_id: int | None = None,
    can_manage_company_reservations: bool = False,
    confirmed_impact_fingerprint: str | None = None,
) -> dict:
    if reservation.room_id is not None and room_has_active_block(
        db,
        hotel_id=hotel_id,
        room_id=reservation.room_id,
        start_date=reservation.check_out_date,
        end_date=new_checkout_date,
    ):
        raise ReservationOperationsError("La habitación no está disponible para la extensión")

    plan = _build_extension_impact_plan(
        db,
        reservation=reservation,
        hotel_id=hotel_id,
        new_checkout_date=new_checkout_date,
        can_manage_company_reservations=can_manage_company_reservations,
        lock_rows=True,
    )
    impact_plan = plan["impact_plan"]
    if confirmed_impact_fingerprint is not None and (
        impact_plan is None or confirmed_impact_fingerprint != impact_plan["fingerprint"]
    ):
        raise ReservationExtensionImpactConfirmationError(
            "impact_plan_stale",
            impact_plan,
        )
    if plan["conflicts"] or plan.get("root_room_blocked"):
        return {
            "resolved": False,
            "conflicts": plan["conflicts"],
            "actions": [],
            "impact_plan": impact_plan,
        }

    planned_actions = plan["planned_actions"]
    has_mutations = any(
        item["action"] in {"moved_equivalent", "moved_superior", "assignment_released"}
        for item in planned_actions
    )
    if has_mutations and confirmed_impact_fingerprint is None:
        raise ReservationExtensionImpactConfirmationError(
            "impact_confirmation_required",
            impact_plan,
        )

    actions: list[dict] = []
    for item in planned_actions:
        conflict = item["reservation"]
        details = {
            "reservation_id": conflict.id,
            "confirmation_code": conflict.confirmation_code,
            "room_id": conflict.room_id,
            "check_in_date": conflict.check_in_date.isoformat(),
            "check_out_date": conflict.check_out_date.isoformat(),
        }
        action = item["action"]
        destination = item.get("to_room")
        if action == "moved_equivalent" and destination is not None:
            reason = (
                "Reserva futura movida a habitacion equivalente para resolver conflicto "
                f"por extension de reserva {reservation.confirmation_code}"
            )
            group, event = create_grouped_room_move(
                db,
                hotel_id=hotel_id,
                reservation=conflict,
                to_room=destination,
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
                    "to_room_id": destination.id,
                    "movement_group_id": group.id,
                    "move_event_id": event.id,
                }
            )
        elif action == "moved_superior" and destination is not None:
            reason = (
                "Reserva futura actualizada a habitacion superior para resolver conflicto "
                f"por extension de reserva {reservation.confirmation_code}"
            )
            group, event = create_grouped_room_move(
                db,
                hotel_id=hotel_id,
                reservation=conflict,
                to_room=destination,
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
                    "to_room_id": destination.id,
                    "movement_group_id": group.id,
                    "move_event_id": event.id,
                }
            )
        elif action == "assignment_released":
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
                    "message": "Reserva futura sin pago liberada para revisión manual",
                }
            )

    return {
        "resolved": True,
        "conflicts": [],
        "actions": actions,
        "impact_plan": impact_plan,
    }


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
    lock_reservation_version(
        db,
        reservation,
        hotel_id=hotel_id,
        client_version=client_version,
    )
    if check_out_date <= check_in_date:
        raise ReservationOperationsError("La fecha de salida debe ser posterior a la fecha de entrada")
    if check_in_date < hotel_today(db, hotel_id):
        raise ReservationOperationsError("No se puede cambiar la fecha de check-in a una fecha en el pasado")
    original_check_in = reservation.check_in_date
    original_check_out = reservation.check_out_date
    if reservation.status in (
        ReservationStatusEnum.PARTIAL_CHECK_IN,
        ReservationStatusEnum.CHECKED_IN,
        ReservationStatusEnum.CHECKED_OUT,
        ReservationStatusEnum.CANCELLED,
        ReservationStatusEnum.NO_SHOW,
    ):
        raise ReservationOperationsError("No se pueden cambiar fechas en el estado actual")

    tiene_pago = (
        reservation.status in (ReservationStatusEnum.DEPOSIT_PAID, ReservationStatusEnum.FULLY_PAID)
        or Decimal(str(reservation.amount_paid or 0)) > Decimal("0")
        or reservation_has_any_transaction(
            db,
            hotel_id=hotel_id,
            reservation_id=reservation.id,
        )
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
        _touch_facts(
            db,
            hotel_id,
            original_check_in,
            original_check_out,
            reservation_id=reservation.id,
        )
        requested_nights = (check_out_date - check_in_date).days
        if pricing_mode == "keep_current_total":
            explicit_total = reservation.total_amount
        else:
            explicit_total = manual_override_total_for_nights(
                reservation,
                nights=requested_nights,
            )
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
                total_amount=explicit_total,
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
        recalculate_pricing=pricing_mode == "recalculate",
        recalculate_explicit_price=pricing_mode == "recalculate",
        refresh_facts=False,
    )
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
            refresh_facts=False,
        )
        status_transitioned = True
    reservation.notes = ((reservation.notes or "") + f"\n[DATE CHANGE] {reason or 'Date changed with payments preserved'}").strip()
    db.flush()
    # Update and status transition deferred their individual refreshes so the
    # final values are materialized once for the union of old/new stay dates.
    _touch_facts(
        db,
        hotel_id,
        min(original_check_in, reservation.check_in_date),
        max(original_check_out, reservation.check_out_date),
        reservation_id=reservation.id,
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
    company: Company | None = None,
) -> Decimal:
    extra_nights = (new_checkout_date - reservation.check_out_date).days
    if extra_nights <= 0:
        raise ReservationOperationsError("La nueva fecha de salida debe ser posterior a la fecha de salida actual")
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
        company_id=company.id if company is not None else None,
    )
    if company is not None:
        pricing = _apply_corporate_pricing(
            db,
            hotel_id=hotel_id,
            pricing=pricing,
            company=company,
            explicit_total=None,
        )
    return Decimal(str(pricing.total_amount)).quantize(Decimal("0.01"))


def preview_reservation_stay_extension(
    db: Session,
    *,
    reservation: Reservation,
    hotel_id: int,
    new_checkout_date: date,
    payment_action: str = "individual",
) -> Decimal | None:
    """Return a read-only quote for individual extensions or validate deferred company terms.

    The committing extension flow rechecks the reservation version, state,
    impact and current rate while holding the reservation lock.
    """
    if reservation.hotel_id != hotel_id:
        raise ReservationOperationsError("La reserva no pertenece al hotel activo")
    if new_checkout_date <= reservation.check_out_date:
        raise ReservationOperationsError("La nueva fecha de salida debe ser posterior a la fecha de salida actual")

    if payment_action == "company_account":
        if reservation.company_id is None:
            raise ReservationOperationsError("La extensión a cuenta solo está disponible para reservas de empresa")
        company = (
            db.query(Company)
            .filter(
                Company.id == reservation.company_id,
                Company.hotel_id == hotel_id,
                Company.is_active.is_(True),
            )
            .first()
        )
        is_deferred = reservation.settlement_status == "deferred" or bool(
            company and company.payment_deferred
        )
        if company is None or not is_deferred:
            raise ReservationOperationsError("La empresa no está activa o no tiene habilitada la cuenta diferida")
        if int(company.deferred_days or 0) < 0:
            raise ReservationOperationsError("La empresa tiene un plazo de cuenta diferida inválido")
        if reservation.status not in {
            ReservationStatusEnum.PARTIAL_CHECK_IN,
            ReservationStatusEnum.CHECKED_IN,
        }:
            raise ReservationOperationsError("La extensión a cuenta solo está disponible para una reserva activa")
        if reservation.settlement_status != "deferred" and not company.payment_deferred:
            raise ReservationOperationsError("La reserva no utiliza cuenta diferida")
        if reservation.room_id and room_has_active_block(
            db,
            hotel_id=hotel_id,
            room_id=reservation.room_id,
            start_date=reservation.check_out_date,
            end_date=new_checkout_date,
        ):
            raise ReservationOperationsError("La habitación no está disponible para la extensión")
        return None

    if payment_action != "individual":
        raise ReservationOperationsError("Acción de preview de extensión inválida")
    _validate_direct_individual_extension_target(db, reservation=reservation, hotel_id=hotel_id)
    if reservation.settlement_status == "deferred":
        raise ReservationOperationsError("Las reservas con cuenta diferida no admiten una cotización de cobro individual")
    if reservation.status not in (
        ReservationStatusEnum.PARTIAL_CHECK_IN,
        ReservationStatusEnum.CHECKED_IN,
        ReservationStatusEnum.FULLY_PAID,
    ):
        raise ReservationOperationsError("Solo se pueden extender reservas en estadía o pagadas por completo")
    if reservation.room_id and room_has_active_block(
        db,
        hotel_id=hotel_id,
        room_id=reservation.room_id,
        start_date=reservation.check_out_date,
        end_date=new_checkout_date,
    ):
        raise ReservationOperationsError("La habitación no está disponible para la extensión")

    amount = _extension_amount(
        db,
        reservation=reservation,
        hotel_id=hotel_id,
        new_checkout_date=new_checkout_date,
        pricing_mode="current_rate",
    )
    if amount <= Decimal("0.00"):
        raise ReservationOperationsError("La extension debe tener importe positivo")
    return amount


def set_company_extension_request(
    db: Session,
    *,
    reservation: Reservation,
    hotel_id: int,
    pending: bool,
    note: str | None,
    client_version: int,
    actor_user_id: int | None,
) -> Reservation:
    """Record a company extension request without changing stay or billing data."""
    if reservation.hotel_id != hotel_id:
        raise ReservationOperationsError("La reserva no pertenece al hotel activo")
    if reservation.company_id is None:
        raise ReservationOperationsError("La solicitud de extensión solo está disponible para reservas de empresa")
    company = (
        db.query(Company)
        .filter(
            Company.id == reservation.company_id,
            Company.hotel_id == hotel_id,
            Company.is_active.is_(True),
        )
        .first()
    )
    if company is None:
        raise ReservationOperationsError("La empresa no está activa en el hotel")
    if reservation.status in (
        ReservationStatusEnum.CHECKED_OUT,
        ReservationStatusEnum.CANCELLED,
        ReservationStatusEnum.NO_SHOW,
    ):
        raise ReservationOperationsError("Solo se puede registrar una extensión en una reserva activa")

    lock_reservation_version(
        db,
        reservation,
        hotel_id=hotel_id,
        client_version=client_version,
    )
    normalized_note = (note or "").strip() or None
    if pending and normalized_note is None:
        raise ReservationOperationsError("Indicá qué extensión pidió la empresa o qué falta confirmar")
    if not pending:
        raise ReservationOperationsError(
            "La solicitud solo se completa al aplicar una extensión autorizada"
        )
    if reservation.company_extension_request_pending == pending and (
        not pending or reservation.company_extension_request_note == normalized_note
    ):
        return reservation

    reservation.company_extension_request_pending = pending
    if pending:
        reservation.company_extension_request_note = normalized_note
    reservation.version = (reservation.version or 0) + 1
    db.flush()
    _notify_reservation_event(
        db,
        hotel_id=hotel_id,
        reservation=reservation,
        event_type="reservation.company_extension_request_updated",
        title="Extensión de empresa pendiente",
        dedupe_suffix=f"company-extension:{reservation.version}",
    )
    return reservation


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
    can_manage_company_reservations: bool = False,
    confirmed_impact_fingerprint: str | None = None,
) -> ReservationExtensionResult:
    if reservation.hotel_id != hotel_id:
        raise ReservationOperationsError("La reserva no pertenece al hotel activo")

    if payment_action != "company_account" and reservation.company_id is None:
        _validate_direct_individual_extension_target(
            db,
            reservation=reservation,
            hotel_id=hotel_id,
        )

    company = None
    if reservation.company_id is not None:
        company = (
            db.query(Company)
            .filter(Company.id == reservation.company_id, Company.hotel_id == hotel_id)
            .with_for_update()
            .first()
        )
    is_deferred_company_reservation = (
        reservation.settlement_status == "deferred"
        or bool(company and company.payment_deferred)
    )
    deferred_company = None
    if is_deferred_company_reservation and payment_action != "company_account":
        raise ReservationOperationsError(
            "Las extensiones de empresas con cuenta diferida deben registrarse fuera del PMS"
        )
    if payment_action == "company_account":
        if reservation.company_id is None:
            raise ReservationOperationsError("La extensión a cuenta solo está disponible para reservas de empresa")
        if company is None or not company.is_active or not is_deferred_company_reservation:
            raise ReservationOperationsError("La empresa no está activa o no tiene habilitada la cuenta diferida")
        deferred_company = company
        if int(deferred_company.deferred_days or 0) < 0:
            raise ReservationOperationsError("La empresa tiene un plazo de cuenta diferida inválido")
        if reservation.status not in {
            ReservationStatusEnum.PARTIAL_CHECK_IN,
            ReservationStatusEnum.CHECKED_IN,
        }:
            raise ReservationOperationsError("La extensión a cuenta solo está disponible para una reserva activa")
        if pricing_mode != "current_rate":
            raise ReservationOperationsError("La extensión a cuenta debe usar la tarifa vigente")
        if immediate_payment is not None or payment_link is not None:
            raise ReservationOperationsError("La extensión a cuenta no admite datos de cobro")
    elif payment_action == "pending_balance" and (immediate_payment is not None or payment_link is not None):
        raise ReservationOperationsError("La extensión con saldo pendiente no admite datos de cobro")

    lock_reservation_version(
        db,
        reservation,
        hotel_id=hotel_id,
        client_version=client_version,
    )
    if reservation.status not in (
        ReservationStatusEnum.PARTIAL_CHECK_IN,
        ReservationStatusEnum.CHECKED_IN,
        ReservationStatusEnum.FULLY_PAID,
    ):
        raise ReservationOperationsError("Solo se pueden extender reservas en estadía o pagadas por completo")
    if new_checkout_date <= reservation.check_out_date:
        raise ReservationOperationsError("La nueva fecha de salida debe ser posterior a la fecha de salida actual")
    if reservation.room_id is not None:
        extension_room = (
            db.query(Room)
            .filter(Room.id == reservation.room_id, Room.hotel_id == hotel_id)
            .with_for_update(of=Room)
            .first()
        )
        if extension_room is None:
            raise ReservationOperationsError("La habitación de la reserva no pertenece al hotel activo")
    conflict_resolution = resolve_extension_conflict(
        db,
        reservation=reservation,
        hotel_id=hotel_id,
        new_checkout_date=new_checkout_date,
        actor_user_id=changed_by_user_id,
        can_manage_company_reservations=can_manage_company_reservations,
        confirmed_impact_fingerprint=confirmed_impact_fingerprint,
    )
    if not conflict_resolution["resolved"]:
        return ReservationExtensionResult(
            reservation=reservation,
            extension_amount=Decimal("0.00"),
            success=False,
            conflicts=conflict_resolution["conflicts"],
            impact_plan=conflict_resolution.get("impact_plan"),
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

    # Deferred company base nights are invoiced outside the PMS. Do not even
    # calculate their rate here: only the explicitly selected company night
    # extras are billable in the PMS.
    amount = Decimal("0.00")
    if payment_action != "company_account":
        amount = _extension_amount(
            db,
            reservation=reservation,
            hotel_id=hotel_id,
            new_checkout_date=new_checkout_date,
            pricing_mode=pricing_mode,
            company=company if company is not None and not is_deferred_company_reservation else None,
        )
        if amount <= Decimal("0.00"):
            raise ReservationOperationsError("La extension debe tener importe positivo")

    if payment_action == "immediate_payment":
        if immediate_payment is None:
            raise ReservationOperationsError("La extension requiere datos de pago inmediato")
        if immediate_payment.transaction_type == TransactionTypeEnum.REFUND:
            raise ReservationOperationsError("No se permiten devoluciones como pago de extension")
        if immediate_payment.reservation_id != reservation.id:
            raise ReservationOperationsError("El pago inmediato debe pertenecer a esta reserva")
        if Decimal(str(immediate_payment.amount)) < amount:
            raise ReservationOperationsError("El pago inmediato debe cubrir el importe de la extension")
        if immediate_payment.payment_method not in {PaymentMethodEnum.CASH, *MANUAL_REFERENCE_METHODS}:
            raise ReservationOperationsError(
                "El pago inmediato solo admite efectivo o un pago presencial confirmado; para una pasarela genera un link de pago"
            )
        if (
            immediate_payment.payment_method in MANUAL_REFERENCE_METHODS
            and not immediate_payment.manual_reference
        ):
            raise ReservationOperationsError(
                "La confirmacion de tarjeta, debito o transferencia requiere el cupon u operacion de referencia"
            )
    elif payment_action == "payment_link":
        if payment_link is None:
            raise ReservationOperationsError("La extension requiere generar link de pago")
        if payment_link.reservation_id != reservation.id:
            raise ReservationOperationsError("El link de pago debe pertenecer a esta reserva")
        if Decimal(str(payment_link.requested_amount)) < amount:
            raise ReservationOperationsError("El link de pago debe cubrir el importe de la extension")
    elif payment_action == "pending_balance":
        pass
    elif payment_action != "company_account":
        raise ReservationOperationsError("Accion de pago de extension invalida")

    original_status = reservation.status
    original_check_out = reservation.check_out_date
    reservation.check_out_date = new_checkout_date
    if payment_action != "company_account":
        reservation.total_amount = (Decimal(str(reservation.total_amount or 0)) + amount).quantize(Decimal("0.01"))
        reservation.subtotal_amount = (Decimal(str(reservation.subtotal_amount or 0)) + amount).quantize(Decimal("0.01"))
        reservation.net_amount = (Decimal(str(reservation.net_amount or 0)) + amount).quantize(Decimal("0.01"))
    reservation.notes = ((reservation.notes or "") + f"\n[EXTENSION] {notes or f'Extended to {new_checkout_date}'}").strip()
    reservation.version = (reservation.version or 0) + 1
    if payment_action != "company_account" and original_status == ReservationStatusEnum.FULLY_PAID:
        sync_reservation_financial_status(
            db,
            reservation,
            hotel_id=hotel_id,
            reason_code="stay_extension_balance",
        )

    transaction = None
    link = None
    try:
        if payment_action == "company_account":
            deferred_days = int(deferred_company.deferred_days or 0)
            reservation.settlement_status = "deferred"
            reservation.settlement_due_date = new_checkout_date + timedelta(days=deferred_days)
        elif payment_action == "immediate_payment":
            transaction = process_payment(
                db,
                immediate_payment,
                hotel_id=hotel_id,
                actor_user_id=changed_by_user_id,
                manual_confirmation=immediate_payment.payment_method in MANUAL_REFERENCE_METHODS,
            )
            if original_status == ReservationStatusEnum.CHECKED_IN and reservation.status != ReservationStatusEnum.CHECKED_IN:
                reservation.status = ReservationStatusEnum.CHECKED_IN
        elif payment_action == "payment_link":
            link = create_link(db, hotel_id, payment_link)
        elif payment_action == "pending_balance":
            pass
        else:  # defensive for direct service callers bypassing request validation
            raise ReservationOperationsError("Accion de pago de extension invalida")
    except (PaymentError, PaymentLinkError) as exc:
        raise ReservationOperationsError(str(exc)) from exc

    # The extension request remains pending if validation, availability,
    # pricing, or payment-link creation fails. Clear it only after this
    # operation has successfully changed the reservation dates in memory and
    # produced the requested payment action; the surrounding route commits
    # both changes together.
    reservation.company_extension_request_pending = False

    db.flush()
    _invalidate_availability_cache(hotel_id)
    _touch_facts(
        db,
        hotel_id,
        reservation.check_in_date,
        max(original_check_out, reservation.check_out_date),
        reservation_id=reservation.id,
    )
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
    client_version: int,
    moved_by_user_id: Optional[int] = None,
    actor_role: str,
    reason_code: Optional[str] = None,
    notes: Optional[str] = None,
    move_type: RoomMoveTypeEnum = RoomMoveTypeEnum.MANUAL_MOVE,
    price_action: str = "keep",
    origin_room_disposition: str | None = None,
    origin_room_disposition_note: str | None = None,
) -> RoomMoveResult:
    if reservation.company_id is not None and not resolve(
        db,
        hotel_id,
        actor_role,
        PERMISSION_COMPANY_MANAGE,
        user_id=moved_by_user_id,
    ):
        audit_permission_denied(
            db,
            hotel_id=hotel_id,
            user_id=moved_by_user_id,
            role=actor_role,
            permission_code=PERMISSION_COMPANY_MANAGE,
        )
        raise RoomMovePermissionError(
            "Para mover una reserva de empresa necesitás el permiso 'Administrar empresas'."
        )

    lock_reservation_version(
        db,
        reservation,
        hotel_id=hotel_id,
        client_version=client_version,
    )
    if price_action not in ("keep", "reprice"):
        raise ReservationOperationsError("price_action debe ser 'keep' o 'reprice'")
    if reason_code is None or not reason_code.strip():
        raise ReservationOperationsError("reason_code is required for room moves")
    reason_code = reason_code.strip()
    is_checked_in = reservation.status in {
        ReservationStatusEnum.PARTIAL_CHECK_IN,
        ReservationStatusEnum.CHECKED_IN,
    }
    allowed_dispositions = {"cleaning", "available", "maintenance"}
    if is_checked_in and origin_room_disposition not in allowed_dispositions:
        raise ReservationOperationsError("Para trasladar una reserva alojada debes elegir el estado de la habitación origen")
    if not is_checked_in and origin_room_disposition is not None:
        raise ReservationOperationsError("La decisión sobre la habitación origen sólo aplica a reservas alojadas")
    if is_checked_in and origin_room_disposition != "cleaning" and not (origin_room_disposition_note or "").strip():
        raise ReservationOperationsError("Si la habitación origen no va a limpieza debes dejar una justificación")

    room = lock_room_for_movement(db, hotel_id=hotel_id, room_id=to_room_id)
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

    checklist_override_reason: str | None = None
    allow_checklist_override = False
    if is_checked_in and open_housekeeping_checklist_exists(
        db,
        hotel_id=hotel_id,
        room_id=room.id,
    ):
        checklist_override_reason = (notes or "").strip()
        if not checklist_override_reason:
            raise ReservationOperationsError(
                "Para trasladar a una habitación con checklist de limpieza pendiente, ingresá un motivo."
            )
        if len(checklist_override_reason) > 500:
            raise ReservationOperationsError("El motivo del override no puede superar 500 caracteres.")
        if not resolve(
            db,
            hotel_id,
            actor_role,
            PERMISSION_RESERVATION_ROOM_DIRTY_OVERRIDE,
            user_id=moved_by_user_id,
        ):
            audit_permission_denied(
                db,
                hotel_id=hotel_id,
                user_id=moved_by_user_id,
                role=actor_role,
                permission_code=PERMISSION_RESERVATION_ROOM_DIRTY_OVERRIDE,
            )
            raise RoomMovePermissionError(
                "Para autorizar el traslado a una habitación con limpieza pendiente necesitás el permiso "
                "'Autorizar traslado a habitación con checklist pendiente'."
            )
        allow_checklist_override = True

    category_changed = destination_category.id != current_category.id
    try:
        _validate_reservation_occupancy(
            destination_category,
            reservation_actual_guest_count(reservation),
            0,
        )
    except ReservationError as exc:
        raise ReservationOperationsError(str(exc)) from exc

    previous_total = Decimal(str(reservation.total_amount or 0)).quantize(Decimal("0.01"))
    if reservation.company_id is not None and price_action == "reprice":
        raise ReservationOperationsError(
            "El cambio de habitación de una reserva de empresa conserva la categoría y tarifa contratadas; "
            "registrá el adicional de persona por separado."
        )

    # sellable_product_id/rate_plan_id are tied to the *current* category's commercial
    # setup; when the category changes they may not be compatible with the new one, so
    # let calculate_reservation_pricing re-infer them for the destination category.
    if reservation.company_id is not None:
        pricing = None
        quoted_total = previous_total
        amount_delta = Decimal("0.00")
        currency_code = reservation.currency_code
    else:
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
        currency_code = pricing.currency_code

    # A cross-category move that keeps a more expensive quote is a
    # complimentary upgrade. Repricing also changes the reservation's
    # commercial total. Both are separately configurable from the hotel's
    # permission settings; a room-movement permission alone must not grant
    # authority over the reservation price.
    changes_price = amount_delta != Decimal("0.00") and price_action == "reprice"
    complimentary_upgrade = (
        category_changed
        and price_action == "keep"
        and amount_delta > Decimal("0.00")
    )
    if changes_price or complimentary_upgrade:
        if not resolve(
            db,
            hotel_id,
            actor_role,
            PERMISSION_RESERVATION_RATE_ADJUST,
            user_id=moved_by_user_id,
        ):
            audit_permission_denied(
                db,
                hotel_id=hotel_id,
                user_id=moved_by_user_id,
                role=actor_role,
                permission_code=PERMISSION_RESERVATION_RATE_ADJUST,
            )
            raise RoomMovePermissionError(
                "Para aplicar un cambio de tarifa o una mejora sin cargo necesitás el permiso "
                "'Ajustar tarifa de reserva'."
            )

    previous_room_id = reservation.room_id
    status_value = reservation.status.value if hasattr(reservation.status, "value") else str(reservation.status)
    reservation.room_id = room.id
    if reservation.company_id is None:
        reservation.category_id = room.category_id
    reservation.version = (reservation.version or 0) + 1
    if price_action == "reprice" and pricing is not None:
        _apply_pricing_result_to_reservation(reservation, pricing)
    if move_type == RoomMoveTypeEnum.MANUAL_MOVE:
        reservation.requires_manual_review = False
    origin_room_status_before, origin_room_status_after = sync_room_statuses_after_move(
        db,
        hotel_id=hotel_id,
        reservation=reservation,
        from_room_id=previous_room_id,
        to_room=room,
        origin_room_disposition=origin_room_disposition,
        origin_room_disposition_note=origin_room_disposition_note,
        actor_user_id=moved_by_user_id,
        allow_open_checklist_occupancy_override=allow_checklist_override,
        checklist_override_reason=checklist_override_reason,
    )
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
        origin_room_disposition=origin_room_disposition,
        origin_room_disposition_note=origin_room_disposition_note,
        origin_room_status_before=origin_room_status_before,
        origin_room_status_after=origin_room_status_after,
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
    _touch_facts(
        db,
        hotel_id,
        reservation.check_in_date,
        reservation.check_out_date,
        reservation_id=reservation.id,
        previous_room_id=previous_room_id,
    )
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
        currency_code=currency_code,
        origin_room_disposition=origin_room_disposition,
        origin_room_disposition_note=origin_room_disposition_note,
        origin_room_status_before=origin_room_status_before,
        origin_room_status_after=origin_room_status_after,
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
    amount_delta = float(
        (Decimal(str(quoted_total_amount)) - Decimal(str(reservation.total_amount or 0))).quantize(
            Decimal("0.01")
        )
    )
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
    reservation_query = (
        db.query(Reservation)
        .filter(
            Reservation.id == reservation.id,
            Reservation.hotel_id == hotel_id,
            Reservation.deleted_at.is_(None),
        )
        .populate_existing()
    )
    reservation = lock_query(reservation_query, Reservation).first()
    if reservation is None:
        raise ReservationOperationsError("La reserva no existe o ya no está activa")
    if reservation.source == ReservationSourceEnum.DIRECT:
        raise ReservationOperationsError("Esta operacion esta pensada para reservas de canales externos")
    if reservation.status in {
        ReservationStatusEnum.PARTIAL_CHECK_IN,
        ReservationStatusEnum.CHECKED_IN,
        ReservationStatusEnum.CHECKED_OUT,
    }:
        raise ReservationOperationsError("No se puede rebookear una reserva ya check-in o check-out")
    if reservation.status == ReservationStatusEnum.CANCELLED:
        raise ReservationOperationsError("La reserva original ya esta cancelada")
    if reservation_has_payment_or_deposit(db, hotel_id=hotel_id, reservation=reservation):
        raise ReservationOperationsError(
            "La reserva tiene pagos o intentos registrados; la conversión directa no transfiere ni reconcilia fondos"
        )

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
    _touch_facts(
        db,
        hotel_id,
        new_reservation.check_in_date,
        new_reservation.check_out_date,
        reservation_id=new_reservation.id,
    )
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
