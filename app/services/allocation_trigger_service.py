"""Durable, non-blocking room-optimization proposal requests."""
from __future__ import annotations

import logging
from datetime import date, timedelta
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.allocation import AllocationRun, AllocationRunStatusEnum
from app.models.reservation import (
    Reservation,
    ReservationSourceEnum,
    ReservationStatusEnum,
)
from app.services.timezones import hotel_today

logger = logging.getLogger(__name__)

DEFAULT_ALLOCATION_HORIZON_DAYS = 90
RESERVATION_CREATED_ALLOCATION_TRIGGER = "reservation_created_auto_proposal"
ALLOCATION_PROPOSAL_TRIGGER_TYPES = frozenset(
    {
        RESERVATION_CREATED_ALLOCATION_TRIGGER,
        "new_reservation",
        "reservation_date_change",
        "reservation_update",
        "reservation_room_move",
        "reservation_group_created",
    }
)


def _pending_proposal_query(db: Session, hotel_id: int):
    return db.query(AllocationRun).filter(
        AllocationRun.hotel_id == hotel_id,
        AllocationRun.trigger_type.in_(ALLOCATION_PROPOSAL_TRIGGER_TYPES),
        AllocationRun.status == AllocationRunStatusEnum.PENDING,
    )


def _request_allocation_proposal(
    db: Session,
    *,
    hotel_id: int,
    trigger_type: str,
) -> AllocationRun:
    """Coalesce automatic invalidations into one pending hotel proposal."""
    if trigger_type not in ALLOCATION_PROPOSAL_TRIGGER_TYPES:
        raise ValueError("Unsupported automatic allocation trigger")

    pending_query = _pending_proposal_query(db, hotel_id)
    existing = pending_query.order_by(AllocationRun.id.asc()).first()
    if existing is not None:
        return existing

    request = AllocationRun(
        hotel_id=hotel_id,
        trigger_type=trigger_type,
        status=AllocationRunStatusEnum.PENDING,
    )
    try:
        # The partial unique index handles concurrent requests without taking
        # a hotel-wide lock while booking or reservation changes are saved.
        with db.begin_nested():
            db.add(request)
            db.flush()
    except IntegrityError:
        existing = pending_query.order_by(AllocationRun.id.asc()).first()
        if existing is not None:
            return existing
        raise
    return request


def reservation_overlaps_allocation_horizon(
    db: Session,
    *,
    hotel_id: int,
    check_in_date: date,
    check_out_date: date,
) -> bool:
    """Return whether a stay can affect the normal hotel-local solver horizon."""
    today = hotel_today(db, hotel_id)
    horizon_end = today + timedelta(days=DEFAULT_ALLOCATION_HORIZON_DAYS)
    return check_in_date < horizon_end and check_out_date > today


def request_reservation_created_allocation(
    db: Session,
    reservation: Reservation,
) -> AllocationRun | None:
    """Queue one hotel-scoped automatic optimization run for a new reservation.

    The request is a pending AllocationRun row in the reservation's transaction.
    A periodic worker reoptimizes after commit and automatically applies only a
    complete, revalidated plan for reservations without an explicit lock or
    check-in. The first-fit assignment remains in place if optimization fails.
    """
    hotel_id = reservation.hotel_id
    if (
        hotel_id is None
        or reservation.deleted_at is not None
        or reservation.is_wait_listed
        or reservation.status in {
            ReservationStatusEnum.CANCELLED,
            ReservationStatusEnum.CHECKED_OUT,
            ReservationStatusEnum.NO_SHOW,
        }
        or reservation.source not in {
            ReservationSourceEnum.DIRECT,
            ReservationSourceEnum.BOOKING,
            ReservationSourceEnum.EXPEDIA,
            ReservationSourceEnum.OTHER_OTA,
        }
        or reservation.check_in_date is None
        or reservation.check_out_date is None
    ):
        return None

    if not reservation_overlaps_allocation_horizon(
        db,
        hotel_id=hotel_id,
        check_in_date=reservation.check_in_date,
        check_out_date=reservation.check_out_date,
    ):
        return None

    return _request_allocation_proposal(
        db,
        hotel_id=hotel_id,
        trigger_type=RESERVATION_CREATED_ALLOCATION_TRIGGER,
    )


def trigger_reoptimization_bg(
    hotel_id: int,
    trigger_type: str = "new_reservation",
    origin_key: str | None = None,
) -> None:
    """Persist a coalesced request, then best-effort wake the Celery worker.

    Call this only after the business transaction commits. The periodic worker
    is the recovery path if the broker is unavailable; this function never runs
    the CP-SAT solver and never changes a reservation assignment.
    """
    from app.database import get_session_factory
    from app.services.tenant_context import set_tenant_hotel_context
    from app.tasks.allocation_tasks import process_recalculation_requests

    if type(hotel_id) is not int or hotel_id <= 0:
        logger.warning("allocation_trigger.invalid_hotel_id")
        return
    if (
        not isinstance(trigger_type, str)
        or trigger_type not in ALLOCATION_PROPOSAL_TRIGGER_TYPES
    ):
        logger.warning("allocation_trigger.invalid_type hotel_id=%s", hotel_id)
        return

    try:
        normalized_origin_key = str(UUID(origin_key)) if origin_key else None
    except (AttributeError, TypeError, ValueError):
        normalized_origin_key = None

    db = None
    try:
        db = get_session_factory()()
        set_tenant_hotel_context(db, hotel_id)
        if normalized_origin_key:
            db.info["domain_event_origin_key"] = normalized_origin_key
        _request_allocation_proposal(
            db,
            hotel_id=hotel_id,
            trigger_type=trigger_type,
        )
        db.commit()
    except Exception as exc:
        if db is not None:
            db.rollback()
        logger.warning(
            "allocation_trigger.enqueue_failed hotel_id=%s error_type=%s",
            hotel_id,
            type(exc).__name__,
        )
        return
    finally:
        if db is not None:
            db.close()

    try:
        process_recalculation_requests.apply_async(
            kwargs={"hotel_id": hotel_id, "origin_key": normalized_origin_key},
            retry=False,
        )
    except Exception as exc:
        # A committed pending row is durable. The scheduled worker will pick it
        # up after broker recovery, so an unavailable wake-up cannot undo the
        # successful reservation update.
        logger.warning(
            "allocation_trigger.dispatch_failed hotel_id=%s error_type=%s",
            hotel_id,
            type(exc).__name__,
        )
