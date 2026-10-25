"""Transactional review service for mutable company terms attached to bookings."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.reservation import Reservation, ReservationSourceEnum, ReservationStatusEnum
from app.models.reservation_company_terms_review import ReservationCompanyTermsReview
from app.services.company_reservation_terms import (
    COMPANY_TERM_FIELDS,
    build_company_terms_snapshot,
    company_terms_from_profile,
    get_company_terms_review_state,
    terms_fingerprint,
)
from app.services.row_locks import lock_query


class CompanyTermsReviewError(ValueError):
    """Expected validation, tenant, or stale-write failure for a review action."""


class CompanyTermsReviewNotFound(CompanyTermsReviewError):
    """The reservation is outside this tenant or does not exist."""


class CompanyTermsReviewConflict(CompanyTermsReviewError):
    """The booking changed or its company terms can no longer be reviewed safely."""


def get_company_terms_review(
    db: Session,
    *,
    hotel_id: int,
    reservation_id: int,
) -> tuple[dict, list[ReservationCompanyTermsReview]]:
    reservation = (
        db.query(Reservation)
        .filter(
            Reservation.hotel_id == hotel_id,
            Reservation.id == reservation_id,
            Reservation.deleted_at.is_(None),
        )
        .one_or_none()
    )
    if reservation is None:
        raise CompanyTermsReviewNotFound("No se encontró la reserva en el hotel activo")
    try:
        state = get_company_terms_review_state(db, reservation, hotel_id=hotel_id)
    except ValueError as exc:
        raise CompanyTermsReviewError(str(exc)) from exc
    events = (
        db.query(ReservationCompanyTermsReview)
        .filter(
            ReservationCompanyTermsReview.hotel_id == hotel_id,
            ReservationCompanyTermsReview.reservation_id == reservation_id,
        )
        .order_by(ReservationCompanyTermsReview.created_at.desc(), ReservationCompanyTermsReview.id.desc())
        .limit(20)
        .all()
    )
    return state, events


def review_company_reservation_terms(
    db: Session,
    *,
    hotel_id: int,
    reservation_id: int,
    actor_user_id: int,
    action: str,
    reason: str,
    expected_config_fingerprint: str,
    idempotency_key: UUID | str,
) -> tuple[dict, ReservationCompanyTermsReview]:
    if action not in {"keep_snapshot", "accept_current"}:
        raise CompanyTermsReviewError("La acción de revisión no es válida")
    normalized_reason = reason.strip()
    if not normalized_reason:
        raise CompanyTermsReviewError("Se requiere un motivo para revisar las condiciones de empresa")

    reservation = lock_query(
        db.query(Reservation)
        .filter(
            Reservation.hotel_id == hotel_id,
            Reservation.id == reservation_id,
            Reservation.deleted_at.is_(None),
        )
        .populate_existing(),
        Reservation,
    ).one_or_none()
    if reservation is None:
        raise CompanyTermsReviewNotFound("No se encontró la reserva en el hotel activo")
    if reservation.status in {
        ReservationStatusEnum.CANCELLED,
        ReservationStatusEnum.NO_SHOW,
        ReservationStatusEnum.CHECKED_OUT,
    }:
        raise CompanyTermsReviewConflict("Las condiciones de empresa no se pueden revisar en una reserva cerrada")
    if reservation.company_id is None:
        raise CompanyTermsReviewError("La reserva no está asociada a una empresa")
    if reservation.actual_check_in is not None:
        raise CompanyTermsReviewConflict("Las condiciones de empresa ya no pueden revisarse después del primer check-in")

    key = str(idempotency_key)
    prior_event = (
        db.query(ReservationCompanyTermsReview)
        .filter(
            ReservationCompanyTermsReview.hotel_id == hotel_id,
            ReservationCompanyTermsReview.reservation_id == reservation_id,
            ReservationCompanyTermsReview.idempotency_key == key,
        )
        .one_or_none()
    )
    if prior_event is not None:
        if prior_event.action != action or prior_event.reason != normalized_reason:
            raise CompanyTermsReviewError("La clave de idempotencia ya fue utilizada con otra decisión")
        return get_company_terms_review_state(db, reservation, hotel_id=hotel_id), prior_event

    company = (
        db.query(Company)
        .filter(Company.hotel_id == hotel_id, Company.id == reservation.company_id)
        .with_for_update()
        .one_or_none()
    )
    if company is None:
        raise CompanyTermsReviewNotFound("La empresa asociada a la reserva no está disponible en este hotel")

    current_terms = company_terms_from_profile(company)
    current_fingerprint = terms_fingerprint(current_terms)
    if current_fingerprint != expected_config_fingerprint:
        raise CompanyTermsReviewConflict(
            "La configuración de empresa cambió desde que se abrió la revisión. Actualizá la pantalla y revisá la diferencia vigente."
        )

    previous_snapshot = reservation.company_terms_snapshot
    previous_reviewed_config = reservation.company_terms_reviewed_config
    if action == "keep_snapshot" and not isinstance(previous_snapshot, dict):
        raise CompanyTermsReviewConflict(
            "Esta reserva no conserva una copia histórica de las condiciones. "
            "Gerencia debe revisar y aceptar explícitamente las condiciones vigentes para resolverla."
        )
    baseline = previous_reviewed_config
    if not isinstance(baseline, dict) and isinstance(previous_snapshot, dict):
        baseline = previous_snapshot.get("terms")
    changed_fields = (
        list(COMPANY_TERM_FIELDS)
        if not isinstance(baseline, dict)
        else [field for field in COMPANY_TERM_FIELDS if baseline.get(field) != current_terms.get(field)]
    )

    reservation_changes: dict[str, object] = {
        "previous_settlement_status": str(
            getattr(reservation.settlement_status, "value", reservation.settlement_status)
            or "not_applicable"
        ),
        "previous_settlement_due_date": (
            reservation.settlement_due_date.isoformat() if reservation.settlement_due_date else None
        ),
    }
    if action == "accept_current":
        previous_terms = (
            previous_snapshot.get("terms") if isinstance(previous_snapshot, dict) else None
        )
        was_deferred = bool(
            previous_terms.get("payment_deferred")
            if isinstance(previous_terms, dict)
            else False
        )
        becomes_deferred = bool(current_terms["payment_deferred"])
        # A historic invoice-after-stay booking deliberately stores zero in
        # the PMS. It cannot safely become a hotel-collected booking until a
        # separate, reviewed pricing action records an amount.
        if was_deferred and not becomes_deferred and Decimal(str(reservation.total_amount or 0)) <= Decimal("0"):
            raise CompanyTermsReviewConflict(
                "No se puede aceptar el cobro inmediato todavía: esta reserva factura fuera del PMS y no tiene un total registrado. Revisá primero el importe de la reserva."
            )
        reservation.company_terms_snapshot = build_company_terms_snapshot(
            company,
            reservation,
            captured_at=datetime.now(timezone.utc),
        )
        reservation.company_terms_review_state = "manager_accepted_current"
        if becomes_deferred:
            reservation.settlement_status = "deferred"
            reservation.settlement_due_date = reservation.check_out_date + timedelta(
                days=int(current_terms["deferred_days"] or 0)
            )
        else:
            reservation.settlement_status = (
                "not_applicable"
                if reservation.source == ReservationSourceEnum.DIRECT
                else "pending"
            )
            reservation.settlement_due_date = None
    else:
        reservation.company_terms_review_state = "manager_kept_snapshot"
    reservation.company_terms_reviewed_config = current_terms
    reservation_changes.update(
        {
            "settlement_status": str(
                getattr(reservation.settlement_status, "value", reservation.settlement_status)
                or "not_applicable"
            ),
            "settlement_due_date": (
                reservation.settlement_due_date.isoformat() if reservation.settlement_due_date else None
            ),
            "pricing_changed": False,
        }
    )

    event = ReservationCompanyTermsReview(
        hotel_id=hotel_id,
        reservation_id=reservation.id,
        company_id=company.id,
        actor_user_id=actor_user_id,
        action=action,
        reason=normalized_reason,
        idempotency_key=key,
        expected_config_fingerprint=current_fingerprint,
        changed_fields=changed_fields,
        previous_snapshot=previous_snapshot,
        previous_reviewed_config=previous_reviewed_config,
        current_company_terms=current_terms,
        resulting_snapshot=reservation.company_terms_snapshot,
        applied_reservation_changes=reservation_changes,
    )
    db.add(event)
    db.flush()
    state = get_company_terms_review_state(db, reservation, hotel_id=hotel_id, company=company)
    return state, event
