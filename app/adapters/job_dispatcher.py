"""Portable job-dispatch port with Celery as the first implementation."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.job_runtime import JobDispatchRecord


@dataclass(frozen=True)
class JobSpec:
    queue: str = "critical"
    hard_time_limit: int = 60
    soft_time_limit: int = 30
    max_retries: int = 8


TASK_SPECS: dict[str, JobSpec] = {
    "domain_events.publish_outbox": JobSpec("critical", 60, 30, 8),
    "notifications.process_outbox": JobSpec("critical", 60, 30, 8),
    "analytics.project_all_derived_facts_incremental": JobSpec("heavy", 1200, 900, 3),
    "analytics.reconcile_all_derived_facts_nightly": JobSpec("heavy", 1200, 900, 3),
    "reports.send_morning_reports": JobSpec("heavy", 600, 300, 5),
    "reports.send_nightly_reports": JobSpec("heavy", 600, 300, 5),
}


class JobDispatcher:
    def dispatch(self, task_name: str, *, args: tuple = (), kwargs: dict | None = None, spec: JobSpec | None = None, headers: dict | None = None) -> str:
        raise NotImplementedError


class CeleryJobDispatcher(JobDispatcher):
    def __init__(self, celery_app):
        self._celery_app = celery_app

    def dispatch(self, task_name: str, *, args: tuple = (), kwargs: dict | None = None, spec: JobSpec | None = None, headers: dict | None = None) -> str:
        selected = spec or TASK_SPECS.get(task_name, JobSpec())
        result = self._celery_app.send_task(
            task_name,
            args=args,
            kwargs=kwargs or {},
            queue=selected.queue,
            headers=headers or {},
            time_limit=selected.hard_time_limit,
            soft_time_limit=selected.soft_time_limit,
        )
        return str(result.id)


def dispatch_once(
    db: Session,
    dispatcher: JobDispatcher,
    *,
    hotel_id: int,
    task_name: str,
    deduplication_key: str,
    args: tuple = (),
    kwargs: dict | None = None,
    correlation_id: str | None = None,
) -> tuple[JobDispatchRecord, bool]:
    """Create one durable intent per tenant/task/key before dispatching.

    A duplicate is a no-op. The caller commits the record with the business
    transaction; dispatch remains at-least-once and task handlers must remain
    idempotent.
    """
    existing = (
        db.query(JobDispatchRecord)
        .filter(
            JobDispatchRecord.hotel_id == hotel_id,
            JobDispatchRecord.task_name == task_name,
            JobDispatchRecord.deduplication_key == deduplication_key,
        )
        .one_or_none()
    )
    if existing is not None:
        return existing, False
    record = JobDispatchRecord(
        hotel_id=hotel_id,
        task_name=task_name,
        deduplication_key=deduplication_key,
        correlation_id=correlation_id or str(uuid.uuid4()),
        status="queued",
    )
    db.add(record)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        existing = (
            db.query(JobDispatchRecord)
            .filter(
                JobDispatchRecord.hotel_id == hotel_id,
                JobDispatchRecord.task_name == task_name,
                JobDispatchRecord.deduplication_key == deduplication_key,
            )
            .one()
        )
        return existing, False
    try:
        dispatcher.dispatch(
            task_name,
            args=args,
            kwargs=kwargs,
            spec=TASK_SPECS.get(task_name),
            headers={"hotel_id": hotel_id, "correlation_id": record.correlation_id, "deduplication_key": deduplication_key},
        )
    except Exception as exc:
        record.status = "failed"
        record.last_error = type(exc).__name__
        record.completed_at = datetime.now(timezone.utc)
        db.flush()
        raise
    return record, True
