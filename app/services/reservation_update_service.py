"""Application service for the reservations API PATCH mutation and audit."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Literal

from sqlalchemy.orm import Session

from app.models.audit_log import AuditActionEnum
from app.models.reservation import Reservation, ReservationStatusEnum
from app.schemas.reservation import ReservationUpdate
from app.services import audit_log_service
from app.services.financial_ledger import reservation_has_payment_or_deposit
from app.services.reservation_service import (
    ConfirmedReservationPriceLocked,
    ManualRatePolicyError,
    ReservationVersionConflict,
    reservation_has_deferred_company_billing,
    update_reservation_fields,
    validate_direct_individual_manual_rate_target,
)
from app.services.reservation_update_plan import (
    ReservationUpdatePlan,
    build_reservation_update_plan,
)


@dataclass(frozen=True)
class ReservationUpdateAuthorization:
    """Transport-provided permission checks used by the PATCH use case.

    The callbacks keep request/step-up details in the API adapter while this
    service controls when each permission is required.
    """

    company_management: Callable[[], None]
    paid_total_adjustment: Callable[[], None]
    manual_rate_scope: Callable[[], Literal["bounded", "unbounded"] | None]
    room_move: Callable[[], None]


class ReservationUpdatePreparationError(Exception):
    """Business/precondition failure raised before a reservation is mutated."""

    def __init__(
        self,
        code: str,
        *,
        detail: str | None = None,
        reservation_status: ReservationStatusEnum | None = None,
    ) -> None:
        self.code = code
        self.detail = detail
        self.reservation_status = reservation_status
        super().__init__(detail or code)


@dataclass(frozen=True)
class PreparedReservationUpdate:
    """Validated application command ready for the audited mutation step."""

    plan: ReservationUpdatePlan
    update_data: ReservationUpdate | None
    previous_allocation_interval: tuple[date, date]
    total_adjustment_kind: Literal["manual", "paid"] | None
    manual_rate_scope: Literal["bounded", "unbounded"] | None
    confirmed_price_change_review_required: bool


def prepare_reservation_update(
    db: Session,
    reservation: Reservation,
    data: ReservationUpdate,
    hotel_id: int,
    *,
    actor_is_manager: bool,
    authorization: ReservationUpdateAuthorization,
) -> PreparedReservationUpdate:
    """Resolve a reservation PATCH into an authorized, validated command.

    Keep the existing decision order here: it is observable when a request
    could fail more than one check. Permission callbacks run at the same
    points as the former router checks, retaining request-bound step-up
    authorization without making this service depend on FastAPI.
    """
    submitted_data = data.model_dump(exclude_unset=True)
    plan = build_reservation_update_plan(
        reservation,
        submitted_data,
        control_fields={
            "client_version",
            "restriction_override",
            "paid_total_change_reason",
            "confirm_large_total_adjustment",
        },
    )
    effective_data = plan.changes

    if reservation.company_id is not None and effective_data:
        authorization.company_management()

    total_adjustment_kind: Literal["manual", "paid"] | None = None
    manual_rate_scope: Literal["bounded", "unbounded"] | None = None
    confirmed_price_change_review_required = False
    if "total_amount" in effective_data:
        if reservation_has_deferred_company_billing(db, reservation, hotel_id=hotel_id):
            raise ReservationUpdatePreparationError(
                "deferred_company_billing",
                detail=(
                    "El alojamiento de esta empresa se factura fuera del PMS y no admite "
                    "correcciones de importe aquí."
                ),
            )

        has_payment_or_deposit = reservation_has_payment_or_deposit(
            db,
            hotel_id=hotel_id,
            reservation=reservation,
        )
        confirmed_price_change_review_required = (
            reservation.room_id is not None and has_payment_or_deposit
        )
        if confirmed_price_change_review_required:
            raise ConfirmedReservationPriceLocked(
                "La reserva tiene habitación y pago asignados. El cambio de tarifa quedó bloqueado; "
                "solicitá una revisión manual."
            )
        if has_payment_or_deposit:
            # Existing paid-total corrections keep their stricter financial
            # permission and never rewrite the original transaction ledger.
            total_adjustment_kind = "paid"
            authorization.paid_total_adjustment()
        else:
            try:
                validate_direct_individual_manual_rate_target(reservation, hotel_id=hotel_id)
            except ManualRatePolicyError as exc:
                raise ReservationUpdatePreparationError(
                    "manual_rate_target",
                    detail=str(exc),
                ) from exc
            total_adjustment_kind = "manual"
            manual_rate_scope = authorization.manual_rate_scope()

    if "room_id" in effective_data and effective_data["room_id"] is not None:
        # This legacy edit path only supports a same-category (tier 1) move.
        authorization.room_move()

    dates_changed = plan.dates_changed
    occupancy_changed = plan.occupancy_changed
    if (
        (dates_changed or occupancy_changed)
        and reservation_has_payment_or_deposit(db, hotel_id=hotel_id, reservation=reservation)
        and not actor_is_manager
    ):
        raise ReservationUpdatePreparationError(
            "paid_dates_require_manager",
            detail="Modificar fechas u ocupación de una reserva con pagos requiere gerente, dueño o codueño.",
        )

    restricted_fields = plan.status_restricted_fields(
        reservation.status,
        metadata_fields={"arrival_time_hint", "reservation_comment"},
        additionally_allowed_fields={"total_amount"},
    )
    if restricted_fields:
        raise ReservationUpdatePreparationError(
            "status_restricted",
            reservation_status=reservation.status,
        )

    if data.client_version is not None and reservation.version != data.client_version:
        raise ReservationVersionConflict(
            "La reserva fue modificada por otra persona. Recargá e intentá de nuevo."
        )

    previous_allocation_interval = (reservation.check_in_date, reservation.check_out_date)
    if not effective_data:
        return PreparedReservationUpdate(
            plan=plan,
            update_data=None,
            previous_allocation_interval=previous_allocation_interval,
            total_adjustment_kind=total_adjustment_kind,
            manual_rate_scope=manual_rate_scope,
            confirmed_price_change_review_required=confirmed_price_change_review_required,
        )

    if data.client_version is None:
        raise ReservationUpdatePreparationError(
            "client_version_required",
            detail="client_version es obligatorio para modificar una reserva. Recargá e intentá nuevamente.",
        )

    update_payload = {**effective_data, "client_version": data.client_version}
    for control_field in (
        "restriction_override",
        "paid_total_change_reason",
        "confirm_large_total_adjustment",
    ):
        if control_field in submitted_data:
            update_payload[control_field] = submitted_data[control_field]

    update_data = ReservationUpdate.model_validate(update_payload)
    return PreparedReservationUpdate(
        plan=plan,
        update_data=update_data,
        previous_allocation_interval=previous_allocation_interval,
        total_adjustment_kind=total_adjustment_kind,
        manual_rate_scope=manual_rate_scope,
        confirmed_price_change_review_required=confirmed_price_change_review_required,
    )


def apply_reservation_update(
    db: Session,
    reservation: Reservation,
    data: ReservationUpdate,
    hotel_id: int,
    *,
    actor_user_id: int,
    actor_role: str | None,
    total_adjustment_kind: Literal["manual", "paid"] | None,
    manual_rate_scope: Literal["bounded", "unbounded"] | None,
    confirmed_price_change_review_required: bool,
) -> Reservation:
    """Mutate, audit, and commit one reservation PATCH in the same session.

    HTTP authorization, tenant-scoped loading/locking, exception mapping, and
    post-commit effects stay in the API adapter. A caller must roll back the
    session if the mutator or commit raises, as it does for the existing route.
    """
    before = audit_log_service.model_snapshot(reservation)
    update_reservation_fields(
        db,
        reservation,
        data,
        hotel_id,
        changed_by_user_id=actor_user_id,
        actor_role=actor_role,
        room_move_reason_code="manual_update",
        room_move_notes="Cambio manual desde API de reservas",
        client_version=data.client_version,
        preserve_unclassified_price=True,
        total_adjustment_kind=total_adjustment_kind,
        manual_rate_scope=manual_rate_scope,
        confirmed_price_change_review_required=confirmed_price_change_review_required,
    )

    after = {
        **(audit_log_service.model_snapshot(reservation) or {}),
        "source": "reservations_api",
    }
    if "total_amount" in data.model_dump(exclude_unset=True):
        adjustment_payload = {
            "previous_total_amount": str(
                Decimal(str(before.get("total_amount") or 0)).quantize(Decimal("0.01"))
            ),
            "updated_total_amount": str(
                Decimal(str(reservation.total_amount or 0)).quantize(Decimal("0.01"))
            ),
            "reason": data.paid_total_change_reason,
            "actor_user_id": actor_user_id,
        }
        if total_adjustment_kind == "manual":
            try:
                pricing_snapshot = json.loads(reservation.pricing_snapshot or "{}")
            except (TypeError, json.JSONDecodeError):
                pricing_snapshot = {}
            history = pricing_snapshot.get("manual_total_adjustments", [])
            latest_adjustment = history[-1] if isinstance(history, list) and history else {}
            manual_rate_context = latest_adjustment.get("manual_rate")
            if isinstance(manual_rate_context, dict):
                adjustment_payload["manual_rate"] = manual_rate_context
        after["total_adjustment"] = adjustment_payload
        if total_adjustment_kind == "paid":
            # Retain the established audit key for existing readers.
            after["paid_total_adjustment"] = adjustment_payload

    audit_log_service.safe_create_audit_log(
        db,
        hotel_id=hotel_id,
        table_name="reservations",
        record_id=reservation.id,
        action=AuditActionEnum.UPDATE,
        actor_user_id=actor_user_id,
        payload_before=before,
        payload_after=after,
    )
    db.commit()
    db.refresh(reservation)
    return reservation
