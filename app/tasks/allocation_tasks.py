"""Background processing for durable room-optimization requests."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Callable
from uuid import UUID

from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.database import get_engine
from app.models.allocation import (
    AllocationAssignment,
    AllocationAssignmentStatusEnum,
    AllocationRun,
    AllocationRunStatusEnum,
)
from app.services.allocation_trigger_service import (
    ALLOCATION_PROPOSAL_TRIGGER_TYPES,
)
from app.services.distributed_lock import (
    DistributedLockBusy,
    DistributedLockUnavailable,
)
from app.services.tenant_context import set_tenant_hotel_context
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

_STALE_REQUEST_AFTER = timedelta(minutes=5)


def _session(database_url: str | None = None) -> Session:
    settings = get_settings()
    engine = get_engine(database_url or settings.DATABASE_URL)
    return sessionmaker(bind=engine)()


def _claim_request(
    db: Session, *, hotel_id: int, now: datetime
) -> tuple[int, str] | None:
    """Claim one committed request and release the booking transaction lock."""
    stale_before = now - _STALE_REQUEST_AFTER
    stale_running = (
        db.query(AllocationRun)
        .filter(
            AllocationRun.hotel_id == hotel_id,
            AllocationRun.trigger_type.in_(ALLOCATION_PROPOSAL_TRIGGER_TYPES),
            AllocationRun.status == AllocationRunStatusEnum.RUNNING,
            AllocationRun.started_at.is_not(None),
            AllocationRun.started_at < stale_before,
        )
        .all()
    )
    for row in stale_running:
        row.status = AllocationRunStatusEnum.PENDING
        row.started_at = None
        row.error_message = None
    if stale_running:
        db.commit()

    request = (
        db.query(AllocationRun)
        .filter(
            AllocationRun.hotel_id == hotel_id,
            AllocationRun.trigger_type.in_(ALLOCATION_PROPOSAL_TRIGGER_TYPES),
            AllocationRun.status == AllocationRunStatusEnum.PENDING,
        )
        .order_by(AllocationRun.created_at.asc(), AllocationRun.id.asc())
        .enable_eagerloads(False)
        .with_for_update(skip_locked=True, of=AllocationRun)
        .first()
    )
    if request is None:
        return None
    request.status = AllocationRunStatusEnum.RUNNING
    request.started_at = now
    request.error_message = None
    request_id = request.id
    trigger_type = request.trigger_type
    db.commit()
    return request_id, trigger_type


def _process_hotel_request(
    db: Session,
    *,
    hotel_id: int,
    now: datetime | None = None,
    allocation_runner: Callable | None = None,
    origin_key: str | None = None,
) -> dict[str, int]:
    """Process one queued run and auto-apply only its safe, complete moves."""
    now = now or datetime.now(timezone.utc)
    set_tenant_hotel_context(db, hotel_id)
    claimed = _claim_request(db, hotel_id=hotel_id, now=now)
    if claimed is None:
        return {"selected": 0, "succeeded": 0, "failed": 0, "deferred": 0}
    request_id, trigger_type = claimed

    if allocation_runner is None:
        from app.services.allocation_runtime_service import run_persisted_allocation

        allocation_runner = run_persisted_allocation

    try:
        normalized_origin_key = str(UUID(origin_key)) if origin_key else None
    except (AttributeError, TypeError, ValueError):
        normalized_origin_key = None
    if normalized_origin_key:
        db.info["domain_event_origin_key"] = normalized_origin_key

    try:
        result = allocation_runner(
            db,
            hotel_id=hotel_id,
            trigger_type=trigger_type,
            apply=True,
            queued_run_id=request_id,
            origin_key=normalized_origin_key,
        )
        if result.run.status == AllocationRunStatusEnum.SUCCEEDED:
            pending_moves = (
                db.query(AllocationAssignment.id)
                .filter(
                    AllocationAssignment.hotel_id == hotel_id,
                    AllocationAssignment.allocation_run_id == request_id,
                    AllocationAssignment.status == AllocationAssignmentStatusEnum.PROPOSED,
                )
                .count()
            )
            if pending_moves:
                from app.services.allocation_runtime_service import accept_allocation_run

                accept_allocation_run(
                    db,
                    hotel_id=hotel_id,
                    run_id=request_id,
                    user_id=None,
                    automatic=True,
                )
        db.commit()
        succeeded = int(result.run.status == AllocationRunStatusEnum.SUCCEEDED)
        failed = int(not succeeded)
        return {"selected": 1, "succeeded": succeeded, "failed": failed, "deferred": 0}
    except (DistributedLockBusy, DistributedLockUnavailable) as exc:
        # Another recalculation is in progress or its coordination backend is
        # temporarily unavailable. Keep the durable request for the next beat.
        db.rollback()
        set_tenant_hotel_context(db, hotel_id)
        request = (
            db.query(AllocationRun)
            .filter(
                AllocationRun.id == request_id,
                AllocationRun.hotel_id == hotel_id,
                AllocationRun.trigger_type.in_(ALLOCATION_PROPOSAL_TRIGGER_TYPES),
                AllocationRun.status == AllocationRunStatusEnum.RUNNING,
            )
            .one_or_none()
        )
        if request is not None:
            request.status = AllocationRunStatusEnum.PENDING
            request.started_at = None
            request.error_message = None
            db.commit()
        logger.info(
            "allocation_tasks.request_deferred hotel_id=%s run_id=%s error_type=%s",
            hotel_id,
            request_id,
            type(exc).__name__,
        )
        return {"selected": 1, "succeeded": 0, "failed": 0, "deferred": 1}
    except Exception as exc:
        # Solver/worker failures are visible on the run while the reservation's
        # first-fit assignment remains unchanged. Do not log exception text,
        # which could contain database or request details.
        db.rollback()
        set_tenant_hotel_context(db, hotel_id)
        request = (
            db.query(AllocationRun)
            .filter(
                AllocationRun.id == request_id,
                AllocationRun.hotel_id == hotel_id,
                AllocationRun.trigger_type.in_(ALLOCATION_PROPOSAL_TRIGGER_TYPES),
                AllocationRun.status == AllocationRunStatusEnum.RUNNING,
            )
            .one_or_none()
        )
        if request is not None:
            request.status = AllocationRunStatusEnum.FAILED
            request.finished_at = datetime.now(timezone.utc)
            request.error_message = "Automatic room optimization failed; manual recalculation is available."
            db.commit()
        logger.warning(
            "allocation_tasks.request_failed hotel_id=%s run_id=%s error_type=%s",
            hotel_id,
            request_id,
            type(exc).__name__,
        )
        return {"selected": 1, "succeeded": 0, "failed": 1, "deferred": 0}


@celery_app.task(name="allocation.process_recalculation_requests")
def process_recalculation_requests(
    database_url: str | None = None,
    hotel_id: int | None = None,
    origin_key: str | None = None,
) -> dict[str, int]:
    """Process one pending optimizer run per active hotel, without providers."""
    totals = {"selected": 0, "succeeded": 0, "failed": 0, "deferred": 0}
    if hotel_id is not None and (type(hotel_id) is not int or hotel_id <= 0):
        logger.warning("allocation_tasks.invalid_hotel_id")
        return totals
    db = _session(database_url)
    try:
        # The fixed cap bounds a beat run while scanning every tenant so a
        # quiet early hotel cannot starve pending work for later hotels.
        if hotel_id is not None:
            hotel_ids = [hotel_id]
        else:
            from app.tasks.report_tasks import _active_hotel_ids

            hotel_ids = _active_hotel_ids(db)
        for queued_hotel_id in hotel_ids:
            try:
                counts = _process_hotel_request(
                    db,
                    hotel_id=queued_hotel_id,
                    origin_key=origin_key if queued_hotel_id == hotel_id else None,
                )
                for key in totals:
                    totals[key] += counts[key]
                if hotel_id is None and totals["selected"] >= 3:
                    break
            except Exception as exc:
                db.rollback()
                logger.warning(
                    "allocation_tasks.hotel_processing_failed hotel_id=%s error_type=%s",
                    queued_hotel_id,
                    type(exc).__name__,
                )
                totals["failed"] += 1
        return totals
    finally:
        db.close()
