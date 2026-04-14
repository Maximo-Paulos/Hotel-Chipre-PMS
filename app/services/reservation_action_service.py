from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.operations import ReservationAdjustment, ReservationAdjustmentStatusEnum, RoomMoveEvent
from app.models.ota_core import OTAReservationLink, OTAReservationLifecycleEnum
from app.models.reservation import Reservation, ReservationStatusEnum
from app.services.payment_service import get_reservation_financial_summary


class ReservationActionError(Exception):
    """Raised when operational action state cannot be resolved."""


_PRIORITY_SCORE = {
    "critical": 4,
    "high": 3,
    "medium": 2,
    "low": 1,
}


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
    reservations = (
        db.query(Reservation)
        .filter(Reservation.hotel_id == hotel_id)
        .order_by(Reservation.check_in_date, Reservation.id)
        .all()
    )

    actions: list[dict[str, Any]] = []
    for reservation in reservations:
        summary = get_reservation_operations_summary(db, hotel_id=hotel_id, reservation_id=reservation.id)
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



def _build_pending_actions(
    *,
    reservation: Reservation,
    ota_link: OTAReservationLink | None,
    related_adjustments: list[ReservationAdjustment],
    financial_summary: dict[str, Any],
) -> list[dict[str, Any]]:
    candidates: list[_ActionCandidate] = []

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
                title="Revision manual requerida",
                detail="La reserva quedo marcada para revision manual antes de seguir operando.",
            )
        )

    if active_reservation and reservation.room_id is None:
        add(
            _ActionCandidate(
                action_key="assign_room",
                code="assign_room",
                priority="high" if reservation.check_in_date <= reservation.check_out_date else "medium",
                title="Asignar habitacion",
                detail="La reserva sigue sin habitacion asignada y requiere confirmacion operativa.",
            )
        )

    if active_reservation and reservation.allocation_status in {"manual_review", "unassigned", "error"}:
        add(
            _ActionCandidate(
                action_key=f"allocation:{reservation.allocation_status}",
                code="allocation_follow_up",
                priority="critical" if reservation.allocation_status == "error" else "high",
                title="Revisar asignacion",
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
                title="Resolver canal externo",
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
                title="Cobrar saldo al huesped",
                detail="Queda saldo operativo por cobrar directamente en el hotel.",
            )
        )
    elif recommended_next_action == "await_channel_settlement":
        add(
            _ActionCandidate(
                action_key="await_channel_settlement",
                code="await_channel_settlement",
                priority="medium",
                title="Esperar settlement del canal",
                detail="La reserva esta marcada como OTA prepaga y todavia falta confirmar el settlement del canal.",
            )
        )
    elif recommended_next_action == "review_cancellation_settlement":
        add(
            _ActionCandidate(
                action_key="review_cancellation_settlement",
                code="review_cancellation_settlement",
                priority="high",
                title="Revisar cancelacion y settlement",
                detail="La reserva fue cancelada pero todavia requiere revisar el settlement o devolucion con el canal.",
            )
        )

    if financial_summary.get("has_financial_reconciliation_gap"):
        add(
            _ActionCandidate(
                action_key="financial_reconciliation_gap",
                code="financial_reconciliation_gap",
                priority="critical",
                title="Conciliar diferencia financiera",
                detail="El monto pagado en la reserva no coincide con la suma de transacciones registradas.",
            )
        )

    if ota_link and ota_link.provider_state == OTAReservationLifecycleEnum.MANUAL_RESOLUTION_REQUIRED:
        add(
            _ActionCandidate(
                action_key=f"ota_link:{ota_link.id}:manual_resolution_required",
                code="resolve_external_channel",
                priority="critical",
                title="Cerrar estado en OTA",
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
                    title="Revisar ajuste operativo",
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
                    title="Resolver accion externa del ajuste",
                    detail="El ajuste operativo requiere una accion pendiente sobre el canal o una confirmacion manual del hotel.",
                    reference_type="reservation_adjustment",
                    reference_id=adjustment.id,
                )
            )

    return [
        _decorate_action(reservation=reservation, candidate=candidate)
        for candidate in _dedupe_candidates(candidates)
    ]



def _decorate_action(*, reservation: Reservation, candidate: _ActionCandidate) -> dict[str, Any]:
    return {
        "action_key": candidate.action_key,
        "code": candidate.code,
        "priority": candidate.priority,
        "title": candidate.title,
        "detail": candidate.detail,
        "reservation_id": reservation.id,
        "confirmation_code": reservation.confirmation_code,
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
    reservation = (
        db.query(Reservation)
        .filter(Reservation.id == reservation_id, Reservation.hotel_id == hotel_id)
        .first()
    )
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
