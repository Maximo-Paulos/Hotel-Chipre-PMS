"""
Persistent allocation runtime service.

Wraps the in-memory solver with database-backed runs, assignments, metrics and
explanations so the PMS can audit and later learn from every recalculation.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

from sqlalchemy.orm import Session, selectinload

from app.models.allocation import (
    AllocationAssignment,
    AllocationAssignmentStatusEnum,
    AllocationExplanation,
    AllocationRun,
    AllocationRunStatusEnum,
    SolverMetric,
)
from app.models.reservation import Reservation
from app.services.allocation_policy_service import get_active_policy_settings
from app.services.allocation_engine import (
    AllocationError,
    AllocationResult,
    apply_allocation_result,
    build_slots_from_db,
    run_allocation,
)


class AllocationRuntimeError(Exception):
    pass


@dataclass(slots=True)
class PersistedAllocationResult:
    run: AllocationRun
    solver_result: AllocationResult


@dataclass(slots=True)
class AllocationRunDetails:
    run: AllocationRun
    explanations: list[AllocationExplanation]
    metrics: list[SolverMetric]
    assignments: list[AllocationAssignment]


def run_persisted_allocation(
    db: Session,
    *,
    hotel_id: int,
    trigger_type: str,
    apply: bool = True,
    horizon_start: Optional[date] = None,
    horizon_end: Optional[date] = None,
) -> PersistedAllocationResult:
    if horizon_start is None:
        horizon_start = date.today()
    if horizon_end is None:
        horizon_end = horizon_start + timedelta(days=90)

    policy_settings = get_active_policy_settings(db, hotel_id)
    policy_version = policy_settings.version
    allocation_run = AllocationRun(
        hotel_id=hotel_id,
        policy_version_id=policy_version.id,
        trigger_type=trigger_type,
        horizon_start=horizon_start,
        horizon_end=horizon_end,
        status=AllocationRunStatusEnum.RUNNING,
    )
    db.add(allocation_run)
    db.flush()

    reservations, rooms = build_slots_from_db(
        db,
        start_date=horizon_start,
        end_date=horizon_end,
        hotel_id=hotel_id,
        policy_constraints=policy_settings.constraints,
    )
    reservation_slot_by_id = {slot.reservation_id: slot for slot in reservations}
    room_slot_by_id = {slot.room_id: slot for slot in rooms}
    fallback_reservation_id = reservations[0].reservation_id if reservations else None
    solver_result = run_allocation(
        reservations,
        rooms,
        optimization_horizon=(horizon_start, horizon_end),
        policy_constraints=policy_settings.constraints,
        policy_weights=policy_settings.weights,
    )

    assignment_status = (
        AllocationAssignmentStatusEnum.APPLIED
        if apply and solver_result.success
        else AllocationAssignmentStatusEnum.PROPOSED
    )
    used_rooms = set()
    for reservation_id, room_id in solver_result.assignments.items():
        reservation = db.get(Reservation, reservation_id)
        if reservation is None:
            continue
        used_rooms.add(room_id)
        db.add(
            AllocationAssignment(
                hotel_id=hotel_id,
                allocation_run_id=allocation_run.id,
                reservation_id=reservation_id,
                room_id=room_id,
                sellable_product_id=reservation.sellable_product_id,
                status=assignment_status,
                objective_delta=None,
                explanation_summary=(
                    "Assignment applied"
                    if assignment_status == AllocationAssignmentStatusEnum.APPLIED
                    else "Assignment proposed"
                ),
            )
        )
        reservation.allocation_status = "assigned" if room_id else "manual_review"
        reservation.requires_manual_review = reservation_id in solver_result.unassigned_reservations
        _create_assignment_explanation(
            db,
            hotel_id=hotel_id,
            allocation_run_id=allocation_run.id,
            reservation=reservation,
            reservation_slot=reservation_slot_by_id.get(reservation_id),
            room_slot=room_slot_by_id.get(room_id),
            room_id=room_id,
            was_moved=reservation_id in solver_result.moved_reservations,
        )

    for reservation_id in solver_result.unassigned_reservations:
        reservation = db.get(Reservation, reservation_id)
        if reservation is None:
            continue
        reservation.allocation_status = "manual_review"
        reservation.requires_manual_review = True
        _create_unassigned_explanation(
            db,
            hotel_id=hotel_id,
            allocation_run_id=allocation_run.id,
            reservation=reservation,
            reservation_slot=reservation_slot_by_id.get(reservation_id),
        )

    if apply and solver_result.success:
        try:
            apply_allocation_result(db, solver_result, hotel_id=hotel_id)
        except AllocationError as exc:
            solver_result.success = False
            solver_result.error = str(exc)

    allocation_run.status = (
        AllocationRunStatusEnum.SUCCEEDED
        if solver_result.success
        else AllocationRunStatusEnum.FAILED
    )
    allocation_run.objective_score = solver_result.objective_value
    allocation_run.solver_summary = (
        f"Assignments={len(solver_result.assignments)}, "
        f"Unassigned={len(solver_result.unassigned_reservations)}, "
        f"Moved={len(solver_result.moved_reservations)}"
    )
    allocation_run.error_message = solver_result.error

    if fallback_reservation_id is not None:
        db.add(
            AllocationExplanation(
                hotel_id=hotel_id,
                allocation_run_id=allocation_run.id,
                reservation_id=next(iter(solver_result.assignments.keys()), fallback_reservation_id),
                explanation_type="summary",
                summary=allocation_run.solver_summary,
                details_json=(
                    f'{{"success": true, "weights": {policy_version.weights_json or "{}"}, "constraints": {policy_version.constraints_json or "{}"}, "moved_reservations": {json.dumps(solver_result.moved_reservations)}, "unassigned_reservations": {json.dumps(solver_result.unassigned_reservations)}}}'
                    if solver_result.success
                    else f'{{"success": false, "requires_manual_review": true, "weights": {policy_version.weights_json or "{}"}, "constraints": {policy_version.constraints_json or "{}"}, "moved_reservations": {json.dumps(solver_result.moved_reservations)}, "unassigned_reservations": {json.dumps(solver_result.unassigned_reservations)}}}'
                ),
            )
        )
    db.add_all(
        [
            SolverMetric(
                hotel_id=hotel_id,
                allocation_run_id=allocation_run.id,
                metric_key="assigned_reservations",
                metric_value=float(len(solver_result.assignments)),
            ),
            SolverMetric(
                hotel_id=hotel_id,
                allocation_run_id=allocation_run.id,
                metric_key="unassigned_reservations",
                metric_value=float(len(solver_result.unassigned_reservations)),
            ),
            SolverMetric(
                hotel_id=hotel_id,
                allocation_run_id=allocation_run.id,
                metric_key="rooms_used",
                metric_value=float(len(used_rooms)),
            ),
        ]
    )
    db.flush()
    return PersistedAllocationResult(run=allocation_run, solver_result=solver_result)


def get_allocation_run_details(db: Session, *, hotel_id: int, run_id: int) -> AllocationRunDetails | None:
    run = (
        db.query(AllocationRun)
        .options(selectinload(AllocationRun.assignments))
        .filter(
            AllocationRun.id == run_id,
            AllocationRun.hotel_id == hotel_id,
        )
        .first()
    )
    if run is None:
        return None
    explanations = (
        db.query(AllocationExplanation)
        .filter(
            AllocationExplanation.allocation_run_id == run_id,
            AllocationExplanation.hotel_id == hotel_id,
        )
        .order_by(AllocationExplanation.id.asc())
        .all()
    )
    metrics = (
        db.query(SolverMetric)
        .filter(
            SolverMetric.allocation_run_id == run_id,
            SolverMetric.hotel_id == hotel_id,
        )
        .order_by(SolverMetric.id.asc())
        .all()
    )
    return AllocationRunDetails(run=run, explanations=explanations, metrics=metrics, assignments=list(run.assignments))


def get_latest_allocation_run_details(db: Session, *, hotel_id: int) -> AllocationRunDetails | None:
    run = (
        db.query(AllocationRun)
        .filter(AllocationRun.hotel_id == hotel_id)
        .order_by(AllocationRun.id.desc())
        .first()
    )
    if run is None:
        return None
    return get_allocation_run_details(db, hotel_id=hotel_id, run_id=run.id)


def _create_assignment_explanation(
    db: Session,
    *,
    hotel_id: int,
    allocation_run_id: int,
    reservation: Reservation,
    reservation_slot,
    room_slot,
    room_id: int,
    was_moved: bool,
) -> None:
    assigned_category_id = room_slot.category_id if room_slot is not None else None
    requested_category_id = reservation.category_id
    priority = reservation_slot.category_priority(assigned_category_id) if reservation_slot and assigned_category_id is not None else None
    is_exact = assigned_category_id == requested_category_id
    summary_parts = []
    if is_exact:
        summary_parts.append("Exact match assignment")
    else:
        summary_parts.append("Compatible fallback assignment")
    if was_moved:
        summary_parts.append("reservation moved")
    summary = ". ".join(summary_parts)
    details = {
        "reservation_id": reservation.id,
        "room_id": room_id,
        "requested_category_id": requested_category_id,
        "assigned_category_id": assigned_category_id,
        "is_exact_match": is_exact,
        "was_moved": was_moved,
        "category_priority": priority,
        "allowed_category_ids": reservation_slot.effective_allowed_category_ids if reservation_slot else [requested_category_id],
    }
    db.add(
        AllocationExplanation(
            hotel_id=hotel_id,
            allocation_run_id=allocation_run_id,
            reservation_id=reservation.id,
            explanation_type="assignment",
            summary=summary,
            details_json=json.dumps(details, ensure_ascii=True, sort_keys=True),
        )
    )


def _create_unassigned_explanation(
    db: Session,
    *,
    hotel_id: int,
    allocation_run_id: int,
    reservation: Reservation,
    reservation_slot,
) -> None:
    details = {
        "reservation_id": reservation.id,
        "requested_category_id": reservation.category_id,
        "allowed_category_ids": reservation_slot.effective_allowed_category_ids if reservation_slot else [reservation.category_id],
        "requires_manual_review": True,
    }
    db.add(
        AllocationExplanation(
            hotel_id=hotel_id,
            allocation_run_id=allocation_run_id,
            reservation_id=reservation.id,
            explanation_type="manual_review",
            summary="No compatible room was available during this allocation run",
            details_json=json.dumps(details, ensure_ascii=True, sort_keys=True),
        )
    )
