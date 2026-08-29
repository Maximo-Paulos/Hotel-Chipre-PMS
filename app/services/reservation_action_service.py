from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.operations import BillingAdjustment, ReservationAdjustment, ReservationAdjustmentStatusEnum, RoomMoveEvent
from app.models.ota_core import OTAReservationLink, OTAReservationLifecycleEnum
from app.models.reservation import Reservation, ReservationSourceEnum, ReservationStatusEnum
from app.models.transaction import Transaction, TransactionStatusEnum, TransactionTypeEnum
from app.services.payment_service import get_reservation_financial_summary
from app.services.reservation_service import active_reservations, active_reservations_select


class ReservationActionError(Exception):
    """Raised when operational action state cannot be resolved."""


_PRIORITY_SCORE = {
    "critical": 4,
    "high": 3,
    "medium": 2,
    "low": 1,
}

# Mirrors the trigger conditions read by `_build_pending_actions` /
# `_recommended_financial_action` so the SQL-level prefilter below can't drift
# silently from the actual candidates for an action.
_TERMINAL_STATUSES = {ReservationStatusEnum.CANCELLED, ReservationStatusEnum.CHECKED_OUT}
_PROBLEM_ALLOCATION_STATUSES = {"manual_review", "unassigned", "error"}
_PROBLEM_SETTLEMENT_STATUSES = {"manual_resolution_required", "pending_hotel_action"}
_PENDING_ADJUSTMENT_STATUSES = {ReservationAdjustmentStatusEnum.DRAFT, ReservationAdjustmentStatusEnum.PENDING}
_ACTIVE_WINDOW_DAYS = 1
# ponytail: known ceiling -- if a hotel legitimately has more real candidates
# than this, only the first `_CANDIDATE_CAP_MULTIPLIER * limit` (min 100) get a
# full summary computed. Raise the multiplier if that ever clips a real hotel.
_CANDIDATE_CAP_MULTIPLIER = 5
_MIN_CANDIDATE_CAP = 100


@dataclass(slots=True)
class _ActionCandidate:
    action_key: str
    code: str
    priority: str
    title: str
    detail: str
    reference_type: str | None = None
    reference_id: int | None = None



def get_reservation_operations_summary(db: Session, *, hotel_id: int, reservation_id: int) -> dict[str, Any]:
    reservation = _get_reservation_or_error(db, hotel_id=hotel_id, reservation_id=reservation_id)
    financial_summary = get_reservation_financial_summary(db, hotel_id, reservation.id)
    ota_link = _get_latest_ota_link(db, hotel_id=hotel_id, reservation_id=reservation.id)
    related_adjustments = _get_related_adjustments(db, hotel_id=hotel_id, reservation_id=reservation.id)
    latest_room_move = _get_latest_room_move(db, hotel_id=hotel_id, reservation_id=reservation.id)
    pending_actions = _build_pending_actions(
        reservation=reservation,
        ota_link=ota_link,
        related_adjustments=related_adjustments,
        financial_summary=financial_summary,
    )

    return {
        "reservation_id": reservation.id,
        "confirmation_code": reservation.confirmation_code,
        "status": reservation.status.value,
        "source": reservation.source.value,
        "source_provider_code": reservation.source_provider_code,
        "allocation_status": reservation.allocation_status,
        "requires_manual_review": reservation.requires_manual_review,
        "payment_collection_model": reservation.payment_collection_model,
        "settlement_status": reservation.settlement_status,
        "pending_action_count": len(pending_actions),
        "pending_actions": pending_actions,
        "financial_summary": financial_summary,
        "ota_link": _serialize_ota_link(ota_link),
        "open_adjustments": [_serialize_adjustment(adjustment) for adjustment in related_adjustments],
        "latest_room_move": _serialize_room_move(latest_room_move),
    }



def list_pending_reservation_actions(
    db: Session,
    *,
    hotel_id: int,
    limit: int = 100,
) -> list[dict[str, Any]]:
    candidate_ids = _candidate_reservation_ids(db, hotel_id=hotel_id)
    cap = max(_MIN_CANDIDATE_CAP, limit * _CANDIDATE_CAP_MULTIPLIER)
    candidate_ids = candidate_ids[:cap]

    actions: list[dict[str, Any]] = []
    for reservation_id in candidate_ids:
        summary = get_reservation_operations_summary(db, hotel_id=hotel_id, reservation_id=reservation_id)
        actions.extend(summary["pending_actions"])

    actions.sort(
        key=lambda item: (
            -_PRIORITY_SCORE.get(item["priority"], 0),
            item["check_in_date"],
            item["reservation_id"],
            item["action_key"],
        )
    )
    return actions[:limit]


def _candidate_reservation_ids(db: Session, *, hotel_id: int) -> list[int]:
    """Bulk-compute reservation ids that could produce a pending action.

    A handful of grouped/EXISTS-style queries replace the old N per-reservation
    query fan-out. The predicate mirrors `_build_pending_actions` /
    `_recommended_financial_action` exactly (not a rough approximation) so no
    real action is silently dropped -- see tests/test_reservation_action_service.py
    for the before/after correctness comparison.
    """
    cutoff = date.today() - timedelta(days=_ACTIVE_WINDOW_DAYS)
    rows = db.execute(
        active_reservations_select(hotel_id)
        .with_only_columns(
            Reservation.id,
            Reservation.status,
            Reservation.source,
            Reservation.room_id,
            Reservation.allocation_status,
            Reservation.requires_manual_review,
            Reservation.settlement_status,
            Reservation.payment_collection_model,
            Reservation.amount_paid,
            Reservation.total_amount,
            Reservation.check_in_date,
        )
        .where(Reservation.check_out_date >= cutoff)
        .order_by(Reservation.check_in_date, Reservation.id)
    ).all()
    if not rows:
        return []

    ids = [row.id for row in rows]

    ota_manual_resolution_ids = {
        reservation_id
        for (reservation_id,) in db.execute(
            select(OTAReservationLink.reservation_id).where(
                OTAReservationLink.hotel_id == hotel_id,
                OTAReservationLink.reservation_id.in_(ids),
                OTAReservationLink.provider_state == OTAReservationLifecycleEnum.MANUAL_RESOLUTION_REQUIRED,
            )
        )
    }

    adjustment_flag_ids: set[int] = set()
    for reservation_id, resulting_reservation_id in db.execute(
        select(ReservationAdjustment.reservation_id, ReservationAdjustment.resulting_reservation_id).where(
            ReservationAdjustment.hotel_id == hotel_id,
            or_(
                ReservationAdjustment.reservation_id.in_(ids),
                ReservationAdjustment.resulting_reservation_id.in_(ids),
            ),
            or_(
                ReservationAdjustment.status.in_(_PENDING_ADJUSTMENT_STATUSES),
                ReservationAdjustment.external_resolution_status.in_(_PROBLEM_SETTLEMENT_STATUSES),
            ),
        )
    ):
        if reservation_id in ids:
            adjustment_flag_ids.add(reservation_id)
        if resulting_reservation_id in ids:
            adjustment_flag_ids.add(resulting_reservation_id)

    billing_adjustment_ids = {
        reservation_id
        for (reservation_id,) in db.execute(
            select(BillingAdjustment.reservation_id).where(
                BillingAdjustment.hotel_id == hotel_id,
                BillingAdjustment.reservation_id.in_(ids),
            )
        )
    }

    completed_paid_by_reservation: dict[int, Decimal] = {}
    for reservation_id, amount, transaction_type in db.execute(
        select(Transaction.reservation_id, Transaction.amount, Transaction.transaction_type).where(
            Transaction.hotel_id == hotel_id,
            Transaction.reservation_id.in_(ids),
            Transaction.status == TransactionStatusEnum.COMPLETED,
        )
    ):
        signed = -Decimal(str(amount)) if transaction_type == TransactionTypeEnum.REFUND else Decimal(str(amount))
        completed_paid_by_reservation[reservation_id] = completed_paid_by_reservation.get(reservation_id, Decimal("0")) + signed

    return [
        row.id
        for row in rows
        if _row_could_generate_action(
            row,
            ota_manual_resolution_ids=ota_manual_resolution_ids,
            adjustment_flag_ids=adjustment_flag_ids,
            billing_adjustment_ids=billing_adjustment_ids,
            completed_paid_by_reservation=completed_paid_by_reservation,
        )
    ]


def _row_could_generate_action(
    row: Any,
    *,
    ota_manual_resolution_ids: set[int],
    adjustment_flag_ids: set[int],
    billing_adjustment_ids: set[int],
    completed_paid_by_reservation: dict[int, Decimal],
) -> bool:
    if row.requires_manual_review:
        return True

    active = row.status not in _TERMINAL_STATUSES
    if active and row.room_id is None:
        return True
    if active and row.allocation_status in _PROBLEM_ALLOCATION_STATUSES:
        return True

    if row.status == ReservationStatusEnum.CANCELLED and row.source != ReservationSourceEnum.DIRECT:
        return True
    if row.settlement_status in _PROBLEM_SETTLEMENT_STATUSES:
        return True
    if row.payment_collection_model == "ota_prepaid" and row.settlement_status in {"pending", "unknown"}:
        return True
    if row.payment_collection_model == "hotel_collect" and (
        Decimal(str(row.amount_paid or 0)) < Decimal(str(row.total_amount or 0)) or row.id in billing_adjustment_ids
    ):
        return True

    if row.id in ota_manual_resolution_ids:
        return True
    if row.id in adjustment_flag_ids:
        return True

    materialized_paid = Decimal(str(row.amount_paid or 0))
    completed_total = completed_paid_by_reservation.get(row.id, Decimal("0"))
    if abs(materialized_paid - completed_total) > Decimal("0.01"):
        return True

    return False



def resolve_external_channel_follow_up(
    db: Session,
    *,
    hotel_id: int,
    reservation_id: int,
    resolved_by_user_id: int | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    reservation = _get_reservation_or_error(db, hotel_id=hotel_id, reservation_id=reservation_id)
    ota_link = _get_latest_ota_link(db, hotel_id=hotel_id, reservation_id=reservation.id)
    adjustments = _get_related_adjustments(db, hotel_id=hotel_id, reservation_id=reservation.id)

    changed_adjustments = 0
    for adjustment in adjustments:
        if adjustment.external_resolution_status in {"manual_resolution_required", "pending_hotel_action"}:
            adjustment.external_resolution_status = "resolved"
            adjustment.resolved_at = datetime.now(timezone.utc)
            if notes:
                adjustment.notes = ((adjustment.notes or "").strip() + f"\n[RESOLVED] {notes}").strip()
            changed_adjustments += 1

    ota_link_resolved = False
    if ota_link and (
        ota_link.provider_state == OTAReservationLifecycleEnum.MANUAL_RESOLUTION_REQUIRED
        or ota_link.sync_status == "manual_resolution_required"
    ):
        if reservation.status == ReservationStatusEnum.CANCELLED:
            ota_link.provider_state = OTAReservationLifecycleEnum.CANCELLED
        ota_link.sync_status = "resolved"
        ota_link.error_message = notes or None
        ota_link_resolved = True

    if reservation.settlement_status in {"manual_resolution_required", "pending_hotel_action"}:
        reservation.settlement_status = "resolved"

    db.flush()
    return {
        "reservation_id": reservation.id,
        "changed_adjustments": changed_adjustments,
        "ota_link_resolved": ota_link_resolved,
        "settlement_status": reservation.settlement_status,
        "resolved_by_user_id": resolved_by_user_id,
    }



def clear_reservation_manual_review(
    db: Session,
    *,
    hotel_id: int,
    reservation_id: int,
    reviewed_by_user_id: int | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    reservation = _get_reservation_or_error(db, hotel_id=hotel_id, reservation_id=reservation_id)
    reservation.requires_manual_review = False
    if reservation.allocation_status == "manual_review":
        reservation.allocation_status = "assigned" if reservation.room_id is not None else "unassigned"
    if notes:
        reservation.notes = ((reservation.notes or "").strip() + f"\n[MANUAL REVIEW CLEARED] {notes}").strip()
    db.flush()
    return {
        "reservation_id": reservation.id,
        "requires_manual_review": reservation.requires_manual_review,
        "allocation_status": reservation.allocation_status,
        "reviewed_by_user_id": reviewed_by_user_id,
    }



def _guest_display_name(reservation: Reservation) -> str:
    """B6.2: hotel-vocabulary titles need a human name, not a system code."""
    guest = reservation.guest
    return guest.full_name if guest is not None else f"Huésped #{reservation.guest_id}"


def _fmt_date(value: date) -> str:
    return value.strftime("%d/%m/%Y")


def _build_pending_actions(
    *,
    reservation: Reservation,
    ota_link: OTAReservationLink | None,
    related_adjustments: list[ReservationAdjustment],
    financial_summary: dict[str, Any],
) -> list[dict[str, Any]]:
    candidates: list[_ActionCandidate] = []
    guest_name = _guest_display_name(reservation)
    check_in = _fmt_date(reservation.check_in_date)
    check_out = _fmt_date(reservation.check_out_date)

    def add(candidate: _ActionCandidate) -> None:
        candidates.append(candidate)

    active_reservation = reservation.status not in {
        ReservationStatusEnum.CANCELLED,
        ReservationStatusEnum.CHECKED_OUT,
    }

    if reservation.requires_manual_review:
        add(
            _ActionCandidate(
                action_key="manual_review_required",
                code="manual_review_required",
                priority="critical",
                title=f"Revisar reserva de {guest_name} — llega {check_in}",
                detail="La reserva quedo marcada para revision manual antes de seguir operando.",
            )
        )

    if active_reservation and reservation.room_id is None:
        add(
            _ActionCandidate(
                action_key="assign_room",
                code="assign_room",
                priority="high" if reservation.check_in_date <= reservation.check_out_date else "medium",
                title=f"Asignar habitación a {guest_name} — llega {check_in}",
                detail="La reserva sigue sin habitacion asignada y requiere confirmacion operativa.",
            )
        )

    if active_reservation and reservation.allocation_status in {"manual_review", "unassigned", "error"}:
        add(
            _ActionCandidate(
                action_key=f"allocation:{reservation.allocation_status}",
                code="allocation_follow_up",
                priority="critical" if reservation.allocation_status == "error" else "high",
                title=f"Revisar asignación de habitación de {guest_name} — llega {check_in}",
                detail=f"El motor de asignacion dejo la reserva en estado '{reservation.allocation_status}'.",
            )
        )

    recommended_next_action = financial_summary.get("recommended_next_action")
    if recommended_next_action == "resolve_external_channel":
        add(
            _ActionCandidate(
                action_key="resolve_external_channel",
                code="resolve_external_channel",
                priority="critical",
                title=f"Resolver pago pendiente con el canal de {guest_name} — sale {check_out}",
                detail="La reserva requiere una accion pendiente contra la OTA o una resolucion manual del settlement.",
                reference_type="ota_link" if ota_link else None,
                reference_id=ota_link.id if ota_link else None,
            )
        )
    elif recommended_next_action == "collect_from_guest":
        add(
            _ActionCandidate(
                action_key="collect_from_guest",
                code="collect_from_guest",
                priority="high",
                title=f"Cobrar saldo pendiente a {guest_name} — sale {check_out}",
                detail="Queda saldo operativo por cobrar directamente en el hotel.",
            )
        )
    elif recommended_next_action == "await_channel_settlement":
        add(
            _ActionCandidate(
                action_key="await_channel_settlement",
                code="await_channel_settlement",
                priority="medium",
                title=f"Esperar liquidación del canal de {guest_name} — sale {check_out}",
                detail="La reserva esta marcada como OTA prepaga y todavia falta confirmar el settlement del canal.",
            )
        )
    elif recommended_next_action == "review_cancellation_settlement":
        add(
            _ActionCandidate(
                action_key="review_cancellation_settlement",
                code="review_cancellation_settlement",
                priority="high",
                title=f"Revisar cancelación y liquidación de {guest_name} — sale {check_out}",
                detail="La reserva fue cancelada pero todavia requiere revisar el settlement o devolucion con el canal.",
            )
        )

    if financial_summary.get("has_financial_reconciliation_gap"):
        add(
            _ActionCandidate(
                action_key="financial_reconciliation_gap",
                code="financial_reconciliation_gap",
                priority="critical",
                title=f"Conciliar diferencia de pagos de {guest_name} — sale {check_out}",
                detail="El monto pagado en la reserva no coincide con la suma de transacciones registradas.",
            )
        )

    if ota_link and ota_link.provider_state == OTAReservationLifecycleEnum.MANUAL_RESOLUTION_REQUIRED:
        add(
            _ActionCandidate(
                action_key=f"ota_link:{ota_link.id}:manual_resolution_required",
                code="resolve_external_channel",
                priority="critical",
                title=f"Cerrar estado en el canal externo de {guest_name} — sale {check_out}",
                detail="El vinculo OTA quedo en resolucion manual requerida y necesita cierre operativo.",
                reference_type="ota_link",
                reference_id=ota_link.id,
            )
        )

    for adjustment in related_adjustments:
        if adjustment.status in {ReservationAdjustmentStatusEnum.DRAFT, ReservationAdjustmentStatusEnum.PENDING}:
            add(
                _ActionCandidate(
                    action_key=f"adjustment:{adjustment.id}:review",
                    code="review_adjustment",
                    priority="high",
                    title=f"Revisar ajuste operativo de {guest_name} — sale {check_out}",
                    detail=f"Hay un ajuste '{adjustment.kind.value}' todavia en estado '{adjustment.status.value}'.",
                    reference_type="reservation_adjustment",
                    reference_id=adjustment.id,
                )
            )
        if adjustment.external_resolution_status in {"manual_resolution_required", "pending_hotel_action"}:
            add(
                _ActionCandidate(
                    action_key=f"adjustment:{adjustment.id}:external_resolution",
                    code="resolve_adjustment_external_action",
                    priority="high",
                    title=f"Resolver acción externa del ajuste de {guest_name} — sale {check_out}",
                    detail="El ajuste operativo requiere una accion pendiente sobre el canal o una confirmacion manual del hotel.",
                    reference_type="reservation_adjustment",
                    reference_id=adjustment.id,
                )
            )

    return [
        _decorate_action(reservation=reservation, candidate=candidate, guest_name=guest_name)
        for candidate in _dedupe_candidates(candidates)
    ]



def _decorate_action(*, reservation: Reservation, candidate: _ActionCandidate, guest_name: str) -> dict[str, Any]:
    return {
        "action_key": candidate.action_key,
        "code": candidate.code,
        "priority": candidate.priority,
        "title": candidate.title,
        "detail": candidate.detail,
        "reservation_id": reservation.id,
        "confirmation_code": reservation.confirmation_code,
        "guest_name": guest_name,
        "reservation_status": reservation.status.value,
        "source": reservation.source.value,
        "source_provider_code": reservation.source_provider_code,
        "payment_collection_model": reservation.payment_collection_model,
        "settlement_status": reservation.settlement_status,
        "check_in_date": reservation.check_in_date,
        "check_out_date": reservation.check_out_date,
        "reference_type": candidate.reference_type,
        "reference_id": candidate.reference_id,
    }



def _dedupe_candidates(candidates: list[_ActionCandidate]) -> list[_ActionCandidate]:
    deduped: dict[str, _ActionCandidate] = {}
    for candidate in candidates:
        existing = deduped.get(candidate.action_key)
        if existing is None or _PRIORITY_SCORE[candidate.priority] > _PRIORITY_SCORE[existing.priority]:
            deduped[candidate.action_key] = candidate
    return list(deduped.values())



def _get_reservation_or_error(db: Session, *, hotel_id: int, reservation_id: int) -> Reservation:
    reservation = active_reservations(db, hotel_id).filter(Reservation.id == reservation_id).first()
    if reservation is None:
        raise ReservationActionError(f"Reservation {reservation_id} not found")
    return reservation



def _get_latest_ota_link(db: Session, *, hotel_id: int, reservation_id: int) -> OTAReservationLink | None:
    return (
        db.query(OTAReservationLink)
        .filter(
            OTAReservationLink.hotel_id == hotel_id,
            OTAReservationLink.reservation_id == reservation_id,
        )
        .order_by(OTAReservationLink.updated_at.desc(), OTAReservationLink.id.desc())
        .first()
    )



def _get_related_adjustments(db: Session, *, hotel_id: int, reservation_id: int) -> list[ReservationAdjustment]:
    return (
        db.query(ReservationAdjustment)
        .filter(
            ReservationAdjustment.hotel_id == hotel_id,
            or_(
                ReservationAdjustment.reservation_id == reservation_id,
                ReservationAdjustment.resulting_reservation_id == reservation_id,
            ),
        )
        .order_by(ReservationAdjustment.requested_at.desc(), ReservationAdjustment.id.desc())
        .all()
    )



def _get_latest_room_move(db: Session, *, hotel_id: int, reservation_id: int) -> RoomMoveEvent | None:
    return (
        db.query(RoomMoveEvent)
        .filter(RoomMoveEvent.hotel_id == hotel_id, RoomMoveEvent.reservation_id == reservation_id)
        .order_by(RoomMoveEvent.occurred_at.desc(), RoomMoveEvent.id.desc())
        .first()
    )



def _serialize_ota_link(ota_link: OTAReservationLink | None) -> dict[str, Any] | None:
    if ota_link is None:
        return None
    return {
        "id": ota_link.id,
        "provider_id": ota_link.provider_id,
        "external_reservation_id": ota_link.external_reservation_id,
        "external_confirmation_code": ota_link.external_confirmation_code,
        "provider_state": ota_link.provider_state.value if hasattr(ota_link.provider_state, "value") else str(ota_link.provider_state),
        "sync_status": ota_link.sync_status,
        "error_message": ota_link.error_message,
    }



def _serialize_adjustment(adjustment: ReservationAdjustment) -> dict[str, Any]:
    return {
        "id": adjustment.id,
        "kind": adjustment.kind.value if hasattr(adjustment.kind, "value") else str(adjustment.kind),
        "status": adjustment.status.value if hasattr(adjustment.status, "value") else str(adjustment.status),
        "reason_code": adjustment.reason_code,
        "request_source": adjustment.request_source,
        "amount_delta": adjustment.amount_delta,
        "currency_code": adjustment.currency_code,
        "external_resolution_status": adjustment.external_resolution_status,
        "resulting_reservation_id": adjustment.resulting_reservation_id,
        "ota_reservation_link_id": adjustment.ota_reservation_link_id,
        "notes": adjustment.notes,
    }



def _serialize_room_move(room_move: RoomMoveEvent | None) -> dict[str, Any] | None:
    if room_move is None:
        return None
    return {
        "id": room_move.id,
        "move_type": room_move.move_type.value if hasattr(room_move.move_type, "value") else str(room_move.move_type),
        "reason_code": room_move.reason_code,
        "from_room_id": room_move.from_room_id,
        "to_room_id": room_move.to_room_id,
        "notes": room_move.notes,
        "occurred_at": room_move.occurred_at.isoformat() if room_move.occurred_at else None,
    }
