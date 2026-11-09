"""Durable, non-blocking room-optimization proposal requests."""
from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta, timezone
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
PENDING_ALLOCATION_STALE_AFTER = timedelta(minutes=15)
PENDING_ALLOCATION_STALE_REASON = (
    "La solicitud no fue tomada por el procesador dentro de 15 minutos. "
    "Volvé a ejecutar la asignación."
)
RESERVATION_CREATED_ALLOCATION_TRIGGER = "reservation_created_auto_proposal"
ALLOCATION_PROPOSAL_TRIGGER_TYPES = frozenset(
    {
        RESERVATION_CREATED_ALLOCATION_TRIGGER,
        "new_reservation",
        "reservation_date_change",
        "reservation_update",
        "reservation_room_move",
        "reservation_group_created",
        "manual_api_recalculate",
        "manual_api_preview",
    }
)


class AllocationRequestInProgress(RuntimeError):
    """A hotel already has a pending allocation request."""


def _pending_proposal_query(db: Session, hotel_id: int):
    return db.query(AllocationRun).filter(
        AllocationRun.hotel_id == hotel_id,
        AllocationRun.trigger_type.in_(ALLOCATION_PROPOSAL_TRIGGER_TYPES),
        AllocationRun.status == AllocationRunStatusEnum.PENDING,
    )


def fail_stale_pending_allocation_requests(
    db: Session,
    *,
    hotel_id: int,
    now: datetime | None = None,
) -> int:
    """Fail unclaimed requests after three five-minute processing cycles.

    ``SKIP LOCKED`` leaves a request alone while a worker is claiming it. The
    caller owns the transaction so reservation-triggered requests stay atomic
    with their business write.
    """
    now_utc = now or datetime.now(timezone.utc)
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=timezone.utc)
    now_utc = now_utc.astimezone(timezone.utc)
    database_now = now_utc.replace(tzinfo=None)
    stale_before = (now_utc - PENDING_ALLOCATION_STALE_AFTER).replace(tzinfo=None)
    stale_requests = (
        _pending_proposal_query(db, hotel_id)
        .filter(AllocationRun.created_at <= stale_before)
        .order_by(AllocationRun.created_at.asc(), AllocationRun.id.asc())
        .enable_eagerloads(False)
        .with_for_update(skip_locked=True, of=AllocationRun)
        .all()
    )
    for request in stale_requests:
        request.status = AllocationRunStatusEnum.FAILED
        request.finished_at = database_now
        request.error_message = PENDING_ALLOCATION_STALE_REASON
    if stale_requests:
        db.flush()
    return len(stale_requests)


def _request_allocation_proposal(
    db: Session,
    *,
    hotel_id: int,
    trigger_type: str,
    now: datetime | None = None,
) -> AllocationRun:
    """Coalesce automatic invalidations into one pending hotel proposal."""
    if trigger_type not in ALLOCATION_PROPOSAL_TRIGGER_TYPES:
        raise ValueError("Unsupported automatic allocation trigger")

    fail_stale_pending_allocation_requests(db, hotel_id=hotel_id, now=now)
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


def request_manual_allocation(
    db: Session,
    *,
    hotel_id: int,
    apply: bool,
    horizon_start: date | None,
    horizon_end: date | None,
    now: datetime | None = None,
) -> AllocationRun:
    """Persist a manual run request so the HTTP request never runs the solver."""
    trigger_type = "manual_api_recalculate" if apply else "manual_api_preview"
    fail_stale_pending_allocation_requests(db, hotel_id=hotel_id, now=now)
    pending_query = _pending_proposal_query(db, hotel_id)
    if pending_query.first() is not None:
        raise AllocationRequestInProgress("An allocation request is already queued for this hotel")

    request = AllocationRun(
        hotel_id=hotel_id,
        trigger_type=trigger_type,
        horizon_start=datetime.combine(horizon_start, time.min) if horizon_start else None,
        horizon_end=datetime.combine(horizon_end, time.min) if horizon_end else None,
        status=AllocationRunStatusEnum.PENDING,
    )
    try:
        # The partial unique index also serializes two simultaneous manual
        # requests and automatic reservation-triggered requests.
        with db.begin_nested():
            db.add(request)
            db.flush()
    except IntegrityError as exc:
        raise AllocationRequestInProgress(
            "An allocation request is already queued for this hotel"
        ) from exc
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
    The scheduled PostgreSQL processor creates a reviewable proposal after
    commit. First-fit assigns the new reservation immediately; suggestions that
    move existing bookings require an authenticated operator's approval.
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

    Call this only after the business transaction commits. The scheduled
    PostgreSQL processor is the recovery path if no broker is configured; this
    function never runs the CP-SAT solver or changes a reservation assignment.
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

    from app.config import get_settings

    runtime_settings = get_settings()
    configured_fields = getattr(runtime_settings, "model_fields_set", set())
    if (
        not isinstance(configured_fields, (set, frozenset))
        or "CELERY_BROKER_URL" not in configured_fields
    ):
        logger.debug(
            "allocation_trigger.dispatch_skipped hotel_id=%s reason=broker_not_configured",
            hotel_id,
        )
        return

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
