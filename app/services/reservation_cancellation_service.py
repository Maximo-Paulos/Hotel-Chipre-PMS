"""Transactional reservation cancellation requests and Manager review."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal

from sqlalchemy.orm import Session

from app.models.audit_log import AuditActionEnum
from app.models.cancellation_review import ReservationCancellationReview
from app.models.hotel_config import HotelConfiguration
from app.models.reservation import Reservation, ReservationStatusEnum
from app.schemas.cancellation_review import CancellationReviewRead
from app.services import audit_log_service
from app.services.cancellation_policy_service import (
    CancellationEvaluation,
    evaluate_cancellation_policy,
)
from app.services.reservation_service import transition_reservation_status
from app.services.row_locks import lock_query

logger = logging.getLogger(__name__)


class CancellationReviewError(ValueError):
    """A cancellation request or review cannot be applied safely."""


class CancellationConfigurationRequired(CancellationReviewError):
    def __init__(self, reason_code: str):
        self.reason_code = reason_code
        super().__init__(reason_code)


class CancellationReviewNotFound(CancellationReviewError):
    pass


class CancellationReviewConflict(CancellationReviewError):
    pass


@dataclass(frozen=True, slots=True)
class CancellationPreparation:
    requested_at: datetime
    evaluation: CancellationEvaluation
    check_in_time: str | None
    hotel_timezone: str | None


@dataclass(frozen=True, slots=True)
class CancellationRequestResult:
    outcome: Literal["cancelled", "approval_required", "manager_review_required"]
    review: ReservationCancellationReview | None = None


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def get_pending_cancellation_review(
    db: Session,
    *,
    hotel_id: int,
    reservation_id: int,
    lock: bool = False,
) -> ReservationCancellationReview | None:
    query = db.query(ReservationCancellationReview).filter(
        ReservationCancellationReview.hotel_id == hotel_id,
        ReservationCancellationReview.reservation_id == reservation_id,
        ReservationCancellationReview.status == "pending",
    )
    if lock:
        query = lock_query(query, ReservationCancellationReview)
    return query.order_by(ReservationCancellationReview.id.desc()).first()


def prepare_cancellation_request(
    reservation: Reservation,
    configuration: HotelConfiguration | None,
    *,
    requested_at: datetime | None = None,
) -> CancellationPreparation:
    instant = requested_at or utc_now()
    evaluation = evaluate_cancellation_policy(
        check_in_date=reservation.check_in_date,
        total_amount=reservation.total_amount,
        reservation_currency=reservation.currency_code,
        policy_snapshot=reservation.cancellation_policy_snapshot,
        check_in_time=configuration.check_in_time if configuration else None,
        hotel_timezone=configuration.hotel_timezone if configuration else None,
        requested_at=instant,
    )
    if evaluation.decision == "hotel_configuration_required":
        raise CancellationConfigurationRequired(evaluation.reason)
    return CancellationPreparation(
        requested_at=instant,
        evaluation=evaluation,
        check_in_time=configuration.check_in_time if configuration else None,
        hotel_timezone=configuration.hotel_timezone if configuration else None,
    )


def request_reservation_cancellation(
    db: Session,
    reservation: Reservation,
    *,
    user_id: int,
    source: Literal["reservations_api", "bookings_api"],
    preparation: CancellationPreparation | None,
) -> CancellationRequestResult:
    """Cancel inside the saved free window or create one durable pending review.

    The reservation row is expected to be locked by the API before calling.
    A retry returns the existing pending record instead of creating another.
    """
    if reservation.status in {
        ReservationStatusEnum.PARTIAL_CHECK_IN,
        ReservationStatusEnum.CHECKED_IN,
        ReservationStatusEnum.CHECKED_OUT,
        ReservationStatusEnum.CANCELLED,
        ReservationStatusEnum.NO_SHOW,
    }:
        raise CancellationReviewConflict("reservation_no_longer_cancellable")

    existing = get_pending_cancellation_review(
        db,
        hotel_id=reservation.hotel_id,
        reservation_id=reservation.id,
        lock=True,
    )
    if existing is not None:
        return CancellationRequestResult(
            outcome=_outcome_for_review(existing),
            review=existing,
        )

    if preparation is None:
        raise CancellationReviewConflict("cancellation_request_requires_policy_evaluation")

    evaluation = preparation.evaluation
    if evaluation.decision == "cancel_without_penalty":
        before = audit_log_service.model_snapshot(reservation)
        transition_reservation_status(
            db,
            reservation,
            ReservationStatusEnum.CANCELLED,
            reservation.hotel_id,
            reason_code="cancelled_within_saved_free_window",
            changed_by_user_id=user_id,
        )
        audit_log_service.safe_create_audit_log(
            db,
            hotel_id=reservation.hotel_id,
            table_name="reservations",
            record_id=reservation.id,
            action=AuditActionEnum.STATUS_CHANGE,
            actor_user_id=user_id,
            payload_before=before,
            payload_after=audit_log_service.model_snapshot(reservation),
        )
        _cancel_active_payment_links(db, reservation)
        return CancellationRequestResult(outcome="cancelled")

    if evaluation.decision not in {"manager_approval_required", "manager_review_required"}:
        raise CancellationReviewConflict("unsupported_cancellation_decision")

    if evaluation.decision == "manager_approval_required":
        review_type = "penalty"
    elif evaluation.reason == "missing_booking_policy_snapshot":
        review_type = "historical_policy_missing"
    else:
        review_type = "policy_needs_review"

    snapshot = reservation.cancellation_policy_snapshot
    snapshot = dict(snapshot) if isinstance(snapshot, dict) else None
    try:
        free_hours = int(snapshot["free_cancellation_hours"]) if snapshot is not None else None
    except (KeyError, TypeError, ValueError):
        free_hours = None

    review = ReservationCancellationReview(
        hotel_id=reservation.hotel_id,
        reservation_id=reservation.id,
        review_type=review_type,
        status="pending",
        reason_code=evaluation.reason,
        policy_snapshot=snapshot,
        reservation_total=_decimal_or_none(reservation.total_amount),
        reservation_currency_code=_currency(reservation.currency_code),
        free_cancellation_hours=free_hours,
        check_in_time=preparation.check_in_time,
        hotel_timezone=preparation.hotel_timezone,
        cancellation_cutoff_at=evaluation.cutoff_at,
        penalty_amount=evaluation.penalty_amount,
        penalty_currency_code=evaluation.currency_code if evaluation.penalty_amount is not None else None,
        requested_by_user_id=user_id,
        requested_at=preparation.requested_at,
    )
    db.add(review)
    db.flush()
    audit_log_service.safe_create_audit_log(
        db,
        hotel_id=reservation.hotel_id,
        table_name="reservation_cancellation_reviews",
        record_id=review.id,
        action=AuditActionEnum.CREATE,
        actor_user_id=user_id,
        payload_after=_review_audit_payload(review),
    )
    return CancellationRequestResult(
        outcome=_outcome_for_review(review),
        review=review,
    )


def resolve_cancellation_review(
    db: Session,
    *,
    hotel_id: int,
    review_id: int,
    user_id: int,
    decision: Literal["approve", "reject"],
    reason: str,
) -> tuple[ReservationCancellationReview, Reservation]:
    review = lock_query(
        db.query(ReservationCancellationReview).filter(
            ReservationCancellationReview.id == review_id,
            ReservationCancellationReview.hotel_id == hotel_id,
        ),
        ReservationCancellationReview,
    ).first()
    if review is None:
        raise CancellationReviewNotFound("cancellation_review_not_found")

    desired_status = "approved" if decision == "approve" else "rejected"
    if review.status == desired_status:
        reservation = _get_review_reservation(db, hotel_id=hotel_id, reservation_id=review.reservation_id, lock=True)
        return review, reservation
    if review.status != "pending":
        raise CancellationReviewConflict("cancellation_review_already_resolved")

    reservation = _get_review_reservation(db, hotel_id=hotel_id, reservation_id=review.reservation_id, lock=True)
    if reservation.status in {
        ReservationStatusEnum.PARTIAL_CHECK_IN,
        ReservationStatusEnum.CHECKED_IN,
        ReservationStatusEnum.CHECKED_OUT,
        ReservationStatusEnum.CANCELLED,
        ReservationStatusEnum.NO_SHOW,
    }:
        raise CancellationReviewConflict("reservation_no_longer_cancellable")

    before_review = _review_audit_payload(review)
    review.status = desired_status
    review.reviewed_by_user_id = user_id
    review.reviewed_at = utc_now()
    review.review_reason = reason

    if decision == "approve":
        before_reservation = audit_log_service.model_snapshot(reservation)
        transition_reservation_status(
            db,
            reservation,
            ReservationStatusEnum.CANCELLED,
            hotel_id,
            reason_code="cancellation_review_approved",
            notes=reason,
            changed_by_user_id=user_id,
        )
        audit_log_service.safe_create_audit_log(
            db,
            hotel_id=hotel_id,
            table_name="reservations",
            record_id=reservation.id,
            action=AuditActionEnum.STATUS_CHANGE,
            actor_user_id=user_id,
            payload_before=before_reservation,
            payload_after=audit_log_service.model_snapshot(reservation),
        )
        _cancel_active_payment_links(db, reservation)

    db.flush()
    audit_log_service.safe_create_audit_log(
        db,
        hotel_id=hotel_id,
        table_name="reservation_cancellation_reviews",
        record_id=review.id,
        action=AuditActionEnum.STATUS_CHANGE,
        actor_user_id=user_id,
        payload_before=before_review,
        payload_after=_review_audit_payload(review),
    )
    return review, reservation


def review_read_payload(
    review: ReservationCancellationReview,
    reservation: Reservation,
) -> CancellationReviewRead:
    return CancellationReviewRead(
        id=review.id,
        reservation_id=review.reservation_id,
        confirmation_code=reservation.confirmation_code,
        check_in_date=reservation.check_in_date,
        check_out_date=reservation.check_out_date,
        reservation_total=review.reservation_total,
        reservation_currency_code=review.reservation_currency_code,
        review_type=review.review_type,
        status=review.status,
        reason_code=review.reason_code,
        policy_snapshot=review.policy_snapshot,
        free_cancellation_hours=review.free_cancellation_hours,
        check_in_time=review.check_in_time,
        hotel_timezone=review.hotel_timezone,
        cancellation_cutoff_at=review.cancellation_cutoff_at,
        penalty_amount=review.penalty_amount,
        penalty_currency_code=review.penalty_currency_code,
        requested_by_user_id=review.requested_by_user_id,
        requested_at=review.requested_at,
        reviewed_by_user_id=review.reviewed_by_user_id,
        reviewed_at=review.reviewed_at,
        review_reason=review.review_reason,
    )


def list_pending_cancellation_reviews(
    db: Session,
    *,
    hotel_id: int,
    limit: int,
) -> list[tuple[ReservationCancellationReview, Reservation]]:
    return (
        db.query(ReservationCancellationReview, Reservation)
        .join(
            Reservation,
            (Reservation.hotel_id == ReservationCancellationReview.hotel_id)
            & (Reservation.id == ReservationCancellationReview.reservation_id),
        )
        .filter(
            ReservationCancellationReview.hotel_id == hotel_id,
            ReservationCancellationReview.status == "pending",
            Reservation.hotel_id == hotel_id,
            Reservation.deleted_at.is_(None),
        )
        .order_by(ReservationCancellationReview.requested_at.asc(), ReservationCancellationReview.id.asc())
        .limit(limit)
        .all()
    )


def process_payment_link_revocations_after_commit(
    db: Session,
    *,
    hotel_id: int,
    reservation_id: int,
) -> None:
    """Attempt the existing link-revocation adapter after the DB commit."""
    try:
        from app.services.payment_link_service import process_payment_link_revocations

        process_payment_link_revocations(db, hotel_id, reservation_id=reservation_id)
        db.commit()
    except Exception as exc:  # noqa: BLE001 - cancellation is already durable
        db.rollback()
        logger.warning(
            "payment_link.revocation_attempt_unavailable hotel_id=%s reservation_id=%s error_type=%s",
            hotel_id,
            reservation_id,
            type(exc).__name__,
        )


def _get_review_reservation(
    db: Session,
    *,
    hotel_id: int,
    reservation_id: int,
    lock: bool,
) -> Reservation:
    query = db.query(Reservation).filter(
        Reservation.id == reservation_id,
        Reservation.hotel_id == hotel_id,
        Reservation.deleted_at.is_(None),
    )
    if lock:
        query = lock_query(query, Reservation)
    reservation = query.populate_existing().first()
    if reservation is None:
        raise CancellationReviewNotFound("reservation_not_found")
    return reservation


def _cancel_active_payment_links(db: Session, reservation: Reservation) -> None:
    try:
        from app.services.payment_link_service import cancel_active_links_for_reservation

        cancel_active_links_for_reservation(
            db,
            reservation.hotel_id,
            reservation.id,
            reason="reservation cancellation requested",
        )
    except Exception as exc:  # noqa: BLE001 - preserve cancellation workflow
        logger.error(
            "payment_link.cancel_request_unavailable hotel_id=%s reservation_id=%s error_type=%s",
            reservation.hotel_id,
            reservation.id,
            type(exc).__name__,
        )


def _outcome_for_review(review: ReservationCancellationReview) -> Literal[
    "approval_required", "manager_review_required"
]:
    if review.review_type == "penalty":
        return "approval_required"
    return "manager_review_required"


def _review_audit_payload(review: ReservationCancellationReview) -> dict[str, str | int | None]:
    amount = review.penalty_amount
    return {
        "review_id": review.id,
        "reservation_id": review.reservation_id,
        "review_type": review.review_type,
        "status": review.status,
        "reason_code": review.reason_code,
        "penalty_amount": str(amount) if amount is not None else None,
        "penalty_currency_code": review.penalty_currency_code,
        "reviewed_by_user_id": review.reviewed_by_user_id,
        "review_reason": review.review_reason,
    }


def _decimal_or_none(value: object) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value))


def _currency(value: str | None) -> str | None:
    normalized = str(value or "").strip().upper()
    if len(normalized) != 3 or not normalized.isascii() or not normalized.isalpha():
        return None
    return normalized
