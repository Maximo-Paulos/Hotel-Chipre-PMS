"""
Persistent allocation runtime service.

Wraps the in-memory solver with database-backed runs, assignments, metrics and
explanations so the PMS can audit and later learn from every recalculation.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from functools import wraps
from typing import Optional

from sqlalchemy.orm import Session, selectinload

from app.models.allocation import (
    AllocationAssignment,
    AllocationAssignmentStatusEnum,
    AllocationExplanation,
    AllocationPolicyProfile,
    AllocationPolicyVersion,
    AllocationRun,
    AllocationRunStatusEnum,
    ReservationAllocationLock,
    SolverMetric,
)
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.room import Room, RoomCategory, RoomStatusEnum
from app.models.security_audit_log import SecurityAuditLog
from app.services.allocation_engine import (
    AllocationError,
    AllocationResult,
    apply_allocation_result,
    build_slots_from_db,
    run_allocation,
)
from app.services.allocation_policy_service import get_active_policy_settings
from app.services.allocation_trigger_service import (
    ALLOCATION_PROPOSAL_TRIGGER_TYPES,
    DEFAULT_ALLOCATION_HORIZON_DAYS,
)
from app.services.distributed_lock import with_distributed_lock
from app.services.domain_events import coalesce_model_change_family
from app.services.reservation_service import active_reservations
from app.services.room_block_service import room_has_active_block
from app.services.row_locks import lock_query
from app.services.timezones import hotel_today


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


_ALLOCATION_EVENT_TABLES = (
    "reservations",
    "room_move_events",
    "room_movement_groups",
    "allocation_assignments",
    "allocation_explanations",
    "allocation_runs",
    "solver_metrics",
)

def reservation_overlaps_default_horizon(
    db: Session,
    *,
    hotel_id: int,
    check_in_date: date,
    check_out_date: date,
) -> bool:
    """Whether a reservation can affect the default hotel-local allocation run."""
    horizon_start = hotel_today(db, hotel_id)
    horizon_end = horizon_start + timedelta(days=DEFAULT_ALLOCATION_HORIZON_DAYS)
    return check_in_date < horizon_end and check_out_date > horizon_start


def _coalesce_allocation_events(function):
    @wraps(function)
    def wrapped(db: Session, *args, **kwargs):
        with coalesce_model_change_family(
            db,
            family="allocation",
            table_names=_ALLOCATION_EVENT_TABLES,
        ):
            return function(db, *args, **kwargs)

    return wrapped


@with_distributed_lock("allocation", "hotel_id", ttl_seconds=30)
@_coalesce_allocation_events
def run_persisted_allocation(
    db: Session,
    *,
    hotel_id: int,
    trigger_type: str,
    apply: bool = True,
    horizon_start: Optional[date] = None,
    horizon_end: Optional[date] = None,
    forbidden_room_ids_by_reservation: Optional[dict[int, set[int]]] = None,
    proposal_context: Optional[dict] = None,
    queued_run_id: int | None = None,
    origin_key: str | None = None,
) -> PersistedAllocationResult:
    if origin_key:
        db.info["domain_event_origin_key"] = origin_key
    if horizon_start is None:
        horizon_start = hotel_today(db, hotel_id)
    if horizon_end is None:
        horizon_end = horizon_start + timedelta(days=DEFAULT_ALLOCATION_HORIZON_DAYS)

    policy_settings = get_active_policy_settings(db, hotel_id)
    policy_version = policy_settings.version
    if queued_run_id is None:
        allocation_run = AllocationRun(
            hotel_id=hotel_id,
            policy_version_id=policy_version.id,
            trigger_type=trigger_type,
            horizon_start=horizon_start,
            horizon_end=horizon_end,
            status=AllocationRunStatusEnum.RUNNING,
            started_at=datetime.now(timezone.utc),
        )
        db.add(allocation_run)
        db.flush()
    else:
        allocation_run = lock_query(
            db.query(AllocationRun).filter(
                AllocationRun.id == queued_run_id,
                AllocationRun.hotel_id == hotel_id,
                AllocationRun.trigger_type == trigger_type,
                AllocationRun.trigger_type.in_(ALLOCATION_PROPOSAL_TRIGGER_TYPES),
            ),
            AllocationRun,
        ).one_or_none()
        if allocation_run is None or allocation_run.status != AllocationRunStatusEnum.RUNNING:
            raise AllocationRuntimeError("Queued allocation request is no longer available")
        allocation_run.policy_version_id = policy_version.id
        allocation_run.horizon_start = horizon_start
        allocation_run.horizon_end = horizon_end
        allocation_run.started_at = allocation_run.started_at or datetime.now(timezone.utc)

    reservations, rooms = build_slots_from_db(
        db,
        start_date=horizon_start,
        end_date=horizon_end,
        hotel_id=hotel_id,
        policy_constraints=policy_settings.constraints,
        policy_weights=policy_settings.weights,
        # Let the solver find a better target for an explicitly locked
        # reservation, but persist it only as a one-time approval request.
        # Physical check-in remains a hard lock in build_slots_from_db.
        allow_locked_moves_for_review=proposal_context is None,
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
        forbidden_room_ids_by_reservation=forbidden_room_ids_by_reservation,
    )

    relevant_reservation_ids = set(solver_result.assignments) | set(
        solver_result.unassigned_reservations
    )
    reservations_by_id = (
        {
            reservation.id: reservation
            for reservation in active_reservations(db, hotel_id)
            .filter(Reservation.id.in_(relevant_reservation_ids))
            .all()
        }
        if relevant_reservation_ids
        else {}
    )
    used_rooms = set()
    immediately_applied_assignments: dict[int, int] = {}
    proposal_count = 0
    assignment_records: list[AllocationAssignment] = []
    assignment_explanations: list[AllocationExplanation] = []
    initial_assignment_failures: list[AllocationExplanation] = []
    review_reservations: list[Reservation] = []
    for reservation_id, room_id in solver_result.assignments.items():
        reservation = reservations_by_id.get(reservation_id)
        if reservation is None:
            continue
        used_rooms.add(room_id)
        is_changed = reservation.room_id != room_id
        # Persist proposed changes first. Automatic callers pass them through
        # the same fresh-state acceptance workflow; preview callers leave them
        # pending for an operator. That workflow rechecks check-in, locks,
        # room capacity, accessibility and overlapping stays before movement.
        is_proposal = is_changed and (reservation.room_id is not None or not apply)
        assignment_status = (
            AllocationAssignmentStatusEnum.PROPOSED
            if is_proposal
            else AllocationAssignmentStatusEnum.APPLIED
        )
        if is_proposal:
            proposal_count += 1
        elif is_changed and solver_result.success:
            immediately_applied_assignments[reservation_id] = room_id
        assignment = AllocationAssignment(
            hotel_id=hotel_id,
            allocation_run_id=allocation_run.id,
            reservation_id=reservation_id,
            room_id=room_id,
            sellable_product_id=reservation.sellable_product_id,
            status=assignment_status,
            objective_delta=None,
            explanation_summary=(
                "Room optimization proposed; reception confirmation required"
                if is_proposal
                else "Initial room assignment applied"
                if is_changed
                else "Existing assignment retained"
            ),
        )
        if assignment_status == AllocationAssignmentStatusEnum.APPLIED:
            assignment.applied_at = datetime.now(timezone.utc)
        if not solver_result.success and is_changed and not is_proposal:
            # A partial solver result is not permission to apply only the easy
            # assignments. Keep each skipped first assignment visible for
            # review and make persisted status match what was actually saved.
            assignment.status = AllocationAssignmentStatusEnum.MANUAL_REVIEW
            assignment.applied_at = None
            assignment.explanation_summary = (
                "Initial assignment was not applied because the solver "
                "could not produce a complete plan"
            )
            reservation.allocation_status = "manual_review"
            reservation.requires_manual_review = True
            if reservation not in review_reservations:
                review_reservations.append(reservation)
            initial_assignment_failures.append(
                AllocationExplanation(
                    hotel_id=hotel_id,
                    allocation_run_id=allocation_run.id,
                    reservation_id=reservation_id,
                    explanation_type="initial_assignment_failed",
                    summary="Initial assignment was not applied because the solver could not produce a complete plan",
                    details_json=json.dumps(
                        {
                            "requires_manual_review": True,
                            "reason": solver_result.error or "The solver returned a partial assignment.",
                        },
                        ensure_ascii=True,
                        sort_keys=True,
                    ),
                )
            )
        assignment_records.append(assignment)
        assignment_explanations.append(
            _create_assignment_explanation(
                hotel_id=hotel_id,
                allocation_run_id=allocation_run.id,
                reservation=reservation,
                reservation_slot=reservation_slot_by_id.get(reservation_id),
                room_slot=room_slot_by_id.get(room_id),
                room_id=room_id,
                was_moved=is_changed,
            )
        )
        if not is_proposal and not is_changed:
            reservation.allocation_status = "assigned" if room_id else "manual_review"
            reservation.requires_manual_review = reservation_id in solver_result.unassigned_reservations

    for reservation_id in solver_result.unassigned_reservations:
        reservation = reservations_by_id.get(reservation_id)
        if reservation is None:
            continue
        reservation.allocation_status = "manual_review"
        reservation.requires_manual_review = True
        review_reservations.append(reservation)
        _create_unassigned_explanation(
            db,
            hotel_id=hotel_id,
            allocation_run_id=allocation_run.id,
            reservation=reservation,
            reservation_slot=reservation_slot_by_id.get(reservation_id),
        )

    if immediately_applied_assignments and solver_result.success:
        try:
            # Keep first-time assignments atomic and serialize against
            # create_reservation(), which also locks candidate Room rows.
            with db.begin_nested():
                fresh_reservations = _lock_and_validate_initial_assignments(
                    db,
                    hotel_id=hotel_id,
                    assignments=immediately_applied_assignments,
                    reservation_slots=reservation_slot_by_id,
                    room_slots=room_slot_by_id,
                )
                apply_allocation_result(
                    db,
                    AllocationResult(success=True, assignments=immediately_applied_assignments),
                    hotel_id=hotel_id,
                    reservations_by_id=fresh_reservations,
                    trigger_reason=trigger_type,
                    trigger_event=trigger_type,
                )
                for reservation_id in immediately_applied_assignments:
                    reservation = fresh_reservations[reservation_id]
                    reservation.allocation_status = "assigned"
                    reservation.requires_manual_review = False
        except AllocationError as exc:
            solver_result.success = False
            solver_result.error = str(exc)
            review_reservations_by_id = {
                reservation.id: reservation
                for reservation in active_reservations(db, hotel_id)
                .filter(Reservation.id.in_(sorted(immediately_applied_assignments)))
                .populate_existing()
                .all()
            }
            for assignment in assignment_records:
                if assignment.reservation_id not in immediately_applied_assignments:
                    continue
                assignment.status = AllocationAssignmentStatusEnum.MANUAL_REVIEW
                assignment.applied_at = None
                assignment.explanation_summary = "Initial assignment was stale or conflicted; manual review required"
                reservation = review_reservations_by_id.get(assignment.reservation_id)
                if reservation is not None:
                    reservation.allocation_status = "manual_review"
                    reservation.requires_manual_review = True
                    if reservation not in review_reservations:
                        review_reservations.append(reservation)
                if assignment.reservation_id not in solver_result.unassigned_reservations:
                    solver_result.unassigned_reservations.append(assignment.reservation_id)
                db.add(
                    AllocationExplanation(
                        hotel_id=hotel_id,
                        allocation_run_id=allocation_run.id,
                        reservation_id=assignment.reservation_id,
                        explanation_type="initial_assignment_failed",
                        summary="Initial room assignment was not applied because the room or reservation changed",
                        details_json=json.dumps(
                            {"requires_manual_review": True, "reason": str(exc)},
                            ensure_ascii=True,
                            sort_keys=True,
                        ),
                    )
                )

    # Do not insert candidate-room foreign keys until the availability check
    # and initial assignment have finished. On PostgreSQL the FK check takes a
    # key-share lock on Room; flushing it before revalidation can make a
    # concurrent booking wait on the allocation transaction that is waiting
    # for that same booking to commit.
    db.add_all(assignment_records)
    db.add_all(assignment_explanations)
    db.add_all(initial_assignment_failures)

    context_reservation_id = (
        fallback_reservation_id
        or next(iter(solver_result.assignments), None)
        or next(iter(solver_result.unassigned_reservations), None)
    )
    if proposal_context and context_reservation_id is not None:
        db.add(
            AllocationExplanation(
                hotel_id=hotel_id,
                allocation_run_id=allocation_run.id,
                reservation_id=context_reservation_id,
                explanation_type="proposal_context",
                summary="Additional constraints for a human-reviewed allocation proposal",
                details_json=json.dumps(proposal_context, ensure_ascii=True, sort_keys=True),
            )
        )

    allocation_run.status = (
        AllocationRunStatusEnum.SUCCEEDED
        if solver_result.success
        else AllocationRunStatusEnum.FAILED
    )
    allocation_run.objective_score = solver_result.objective_value
    allocation_run.solver_summary = (
        f"Assignments={len(solver_result.assignments)}, "
        f"Unassigned={len(solver_result.unassigned_reservations)}, "
        f"Moved={len(solver_result.moved_reservations)}, "
        f"Proposed={proposal_count}, "
        f"PrimaryObjectiveStatus={_primary_objective_label(solver_result.primary_status)}, "
        f"TieBreak={solver_result.tie_break_status}"
    )
    allocation_run.error_message = solver_result.error
    allocation_run.finished_at = datetime.now(timezone.utc)

    if fallback_reservation_id is not None:
        db.add(
            AllocationExplanation(
                hotel_id=hotel_id,
                allocation_run_id=allocation_run.id,
                reservation_id=next(iter(solver_result.assignments.keys()), fallback_reservation_id),
                explanation_type="summary",
                summary=allocation_run.solver_summary,
                details_json=json.dumps(
                    {
                        "success": solver_result.success,
                        "requires_manual_review": not solver_result.success,
                        "weights": policy_settings.weights,
                        "constraints": policy_settings.constraints,
                        "moved_reservations": solver_result.moved_reservations,
                        "unassigned_reservations": solver_result.unassigned_reservations,
                        "primary_objective_status": solver_result.primary_status,
                        "primary_objective_status_label": _primary_objective_label(
                            solver_result.primary_status
                        ),
                        "tie_break_status": solver_result.tie_break_status,
                    },
                    ensure_ascii=True,
                    sort_keys=True,
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
            SolverMetric(
                hotel_id=hotel_id,
                allocation_run_id=allocation_run.id,
                metric_key="primary_objective_optimal",
                metric_value=float(solver_result.primary_status == "OPTIMAL"),
            ),
            SolverMetric(
                hotel_id=hotel_id,
                allocation_run_id=allocation_run.id,
                metric_key="primary_objective_status_optimal",
                metric_value=float(solver_result.primary_status == "OPTIMAL"),
            ),
            SolverMetric(
                hotel_id=hotel_id,
                allocation_run_id=allocation_run.id,
                metric_key="primary_objective_status_feasible",
                metric_value=float(solver_result.primary_status == "FEASIBLE"),
            ),
            SolverMetric(
                hotel_id=hotel_id,
                allocation_run_id=allocation_run.id,
                metric_key="primary_objective_status_heuristic",
                metric_value=float(solver_result.primary_status == "HEURISTIC"),
            ),
            SolverMetric(
                hotel_id=hotel_id,
                allocation_run_id=allocation_run.id,
                metric_key="tie_break_complete",
                metric_value=float(solver_result.tie_break_status == "OPTIMAL"),
            ),
        ]
    )
    db.flush()

    # §13.3 review routing: reviews that affect a reservation active today get an
    # immediate alert; future reviews wait for the morning report. Best-effort —
    # any failure here must never abort the allocation run.
    if review_reservations:
        try:
            from app.services.operational_report_service import route_manual_review

            for reservation in review_reservations:
                route_manual_review(db, reservation)
        except Exception:  # pragma: no cover - defensive guard
            pass

    return PersistedAllocationResult(run=allocation_run, solver_result=solver_result)


def _primary_objective_label(status: str | None) -> str:
    """Describe solver evidence without implying an unproven optimum."""
    normalized = str(status or "NOT_RUN").upper()
    if normalized == "OPTIMAL":
        return "OPTIMAL (optimality proven)"
    if normalized == "FEASIBLE":
        return "FEASIBLE (optimality not proven)"
    if normalized == "HEURISTIC":
        return "HEURISTIC (optimality not proven)"
    return f"{normalized} (optimality not proven)"


def _lock_and_validate_initial_assignments(
    db: Session,
    *,
    hotel_id: int,
    assignments: dict[int, int],
    reservation_slots: dict,
    room_slots: dict,
) -> dict[int, Reservation]:
    """Lock and recheck every immediate autoassignment before writing rooms.

    Room rows are acquired in primary-key order, matching the locking strategy
    used by ``create_reservation``. The reservation and category rows are then
    refreshed and checked under lock so stale solver inputs fail closed.
    """
    if not assignments:
        return {}

    target_room_ids = sorted(set(assignments.values()))
    room_query = (
        db.query(Room)
        .filter(
            Room.hotel_id == hotel_id,
            Room.id.in_(target_room_ids),
            Room.deleted_at.is_(None),
        )
        .order_by(Room.id.asc())
        .enable_eagerloads(False)
        .populate_existing()
    )
    rooms = lock_query(room_query, Room).all()
    rooms_by_id = {room.id: room for room in rooms}
    if set(rooms_by_id) != set(target_room_ids):
        raise AllocationError("A selected room no longer exists for this hotel")

    reservation_ids = sorted(assignments)
    reservation_query = (
        active_reservations(db, hotel_id)
        .filter(Reservation.id.in_(reservation_ids))
        .order_by(Reservation.id.asc())
        .populate_existing()
    )
    fresh_reservations = lock_query(reservation_query, Reservation).all()
    reservations_by_id = {reservation.id: reservation for reservation in fresh_reservations}
    if set(reservations_by_id) != set(reservation_ids):
        raise AllocationError("A selected reservation is no longer active")

    category_ids = sorted({room.category_id for room in rooms if room.category_id is not None})
    category_query = (
        db.query(RoomCategory)
        .filter(
            RoomCategory.hotel_id == hotel_id,
            RoomCategory.id.in_(category_ids),
        )
        .order_by(RoomCategory.id.asc())
        .populate_existing()
    ) if category_ids else db.query(RoomCategory).filter(RoomCategory.id == -1)
    categories = lock_query(category_query, RoomCategory).all()
    categories_by_id = {category.id: category for category in categories}
    if set(categories_by_id) != set(category_ids):
        raise AllocationError("A selected room category changed or is no longer available")

    from app.services.reservation_service import (
        ReservationError,
        check_room_availability,
    )

    active_lock_ids = {
        row[0]
        for row in db.query(ReservationAllocationLock.reservation_id)
        .filter(
            ReservationAllocationLock.hotel_id == hotel_id,
            ReservationAllocationLock.reservation_id.in_(reservation_ids),
            ReservationAllocationLock.is_active.is_(True),
        )
        .all()
    }
    planned_windows: dict[int, list[tuple[date, date]]] = {}
    for reservation_id in reservation_ids:
        reservation = reservations_by_id[reservation_id]
        slot = reservation_slots.get(reservation_id)
        room_id = assignments[reservation_id]
        room = rooms_by_id[room_id]
        room_slot = room_slots.get(room_id)
        category = categories_by_id.get(room.category_id)
        if slot is None or room_slot is None or category is None:
            raise AllocationError("The allocation plan is missing a current room or reservation snapshot")
        if (
            reservation.room_id != slot.current_room_id
            or reservation.check_in_date != slot.check_in
            or reservation.check_out_date != slot.check_out
            or reservation.category_id != slot.category_id
            or (reservation.num_adults or 0) + (reservation.num_children or 0) != slot.num_guests
            or bool(reservation.mobility_restriction) != bool(slot.mobility_restriction)
        ):
            raise AllocationError("A reservation changed while allocation was running; recalculate allocation")
        if reservation.room_id is not None:
            raise AllocationError("A reservation already has a room; review the new allocation")
        if (
            reservation.status in {
                ReservationStatusEnum.PARTIAL_CHECK_IN,
                ReservationStatusEnum.CHECKED_IN,
            }
            or reservation.actual_check_in is not None
            or reservation.allocation_locked
            or reservation.id in active_lock_ids
        ):
            raise AllocationError("A reservation is checked in or protected from reassignment")
        if room_slot.category_id != room.category_id or room.category_id not in slot.effective_allowed_category_ids:
            raise AllocationError("A selected room is no longer category-compatible")
        if category.max_occupancy < (reservation.num_adults or 0) + (reservation.num_children or 0):
            raise AllocationError("A selected room no longer has enough capacity")
        if bool(reservation.mobility_restriction) and not bool(room.is_accessible):
            raise AllocationError("A selected room no longer meets the accessibility requirement")
        try:
            available = check_room_availability(
                db,
                room_id,
                reservation.check_in_date,
                reservation.check_out_date,
                hotel_id=hotel_id,
                exclude_reservation_id=reservation.id,
                known_room=room,
            )
        except ReservationError as exc:
            raise AllocationError("Room availability could not be verified; review the allocation") from exc
        if not available:
            raise AllocationError("A selected room is no longer available for this stay")

        windows = planned_windows.setdefault(room_id, [])
        if any(
            reservation.check_in_date < existing_checkout
            and existing_checkin < reservation.check_out_date
            for existing_checkin, existing_checkout in windows
        ):
            raise AllocationError("Selected reservations now conflict in the same room")
        windows.append((reservation.check_in_date, reservation.check_out_date))

    return reservations_by_id


def _active_policy_version_id_for_acceptance(db: Session, hotel_id: int) -> int:
    """Read and lock the active policy rows before proposal acceptance."""
    profile_query = (
        db.query(AllocationPolicyProfile)
        .filter(
            AllocationPolicyProfile.hotel_id == hotel_id,
            AllocationPolicyProfile.is_active.is_(True),
        )
        .order_by(AllocationPolicyProfile.id.asc())
        .populate_existing()
    )
    profile = lock_query(profile_query, AllocationPolicyProfile).first()
    if profile is None:
        # Preserve the policy service's default creation contract for hotels
        # whose seed records are missing, then re-read those records from SQL.
        settings = get_active_policy_settings(db, hotel_id)
        profile_query = (
            db.query(AllocationPolicyProfile)
            .filter(
                AllocationPolicyProfile.id == settings.profile.id,
                AllocationPolicyProfile.hotel_id == hotel_id,
                AllocationPolicyProfile.is_active.is_(True),
            )
            .populate_existing()
        )
        profile = lock_query(profile_query, AllocationPolicyProfile).one_or_none()
    if profile is None:
        raise AllocationRuntimeError("No active allocation policy is available; recalculate allocation")

    version_query = (
        db.query(AllocationPolicyVersion)
        .filter(
            AllocationPolicyVersion.hotel_id == hotel_id,
            AllocationPolicyVersion.profile_id == profile.id,
            AllocationPolicyVersion.is_published.is_(True),
        )
        .order_by(AllocationPolicyVersion.version_number.desc(), AllocationPolicyVersion.id.desc())
        .populate_existing()
    )
    version = lock_query(version_query, AllocationPolicyVersion).first()
    if version is None:
        settings = get_active_policy_settings(db, hotel_id)
        version_query = (
            db.query(AllocationPolicyVersion)
            .filter(
                AllocationPolicyVersion.id == settings.version.id,
                AllocationPolicyVersion.hotel_id == hotel_id,
                AllocationPolicyVersion.is_published.is_(True),
            )
            .populate_existing()
        )
        version = lock_query(version_query, AllocationPolicyVersion).one_or_none()
    if version is None:
        raise AllocationRuntimeError("No published allocation policy is available; recalculate allocation")
    return version.id


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


def accept_allocation_run(
    db: Session,
    *,
    hotel_id: int,
    run_id: int,
    user_id: int | None,
    allow_room_block_plan: bool = False,
    automatic: bool = False,
    explicitly_approved_locked_reservation_ids: set[int] | None = None,
) -> AllocationRunDetails:
    """Accept the proposed room moves from a fresh, tenant-scoped solver run.

    The run, reservations and target rooms are locked in a stable order. Every
    source state and the complete target occupancy is checked again before the
    first reservation changes, so a stale plan cannot partially move guests.
    Room-block plans may only be accepted by the atomic block workflow.
    """
    run_query = db.query(AllocationRun).filter(
        AllocationRun.id == run_id,
        AllocationRun.hotel_id == hotel_id,
    ).populate_existing()
    run = lock_query(run_query, AllocationRun).one_or_none()
    if run is None:
        raise AllocationRuntimeError("Allocation run not found for this hotel")
    if run.status != AllocationRunStatusEnum.SUCCEEDED:
        raise AllocationRuntimeError("Only successful allocation runs can be accepted")

    context_row = (
        db.query(AllocationExplanation)
        .filter(
            AllocationExplanation.hotel_id == hotel_id,
            AllocationExplanation.allocation_run_id == run_id,
            AllocationExplanation.explanation_type == "proposal_context",
        )
        .order_by(AllocationExplanation.id.asc())
        .first()
    )
    proposal_context = _load_json_dict(context_row.details_json) if context_row else {}
    is_room_block_plan = proposal_context.get("kind") in {
        "room_block",
        "room_block_extension",
    }
    if is_room_block_plan and not allow_room_block_plan:
        raise AllocationRuntimeError("Room-block proposals must be accepted with the block mutation")
    if allow_room_block_plan and not is_room_block_plan:
        raise AllocationRuntimeError("Allocation run is not a room-block proposal")

    assignment_query = (
        db.query(AllocationAssignment)
        .filter(
            AllocationAssignment.hotel_id == hotel_id,
            AllocationAssignment.allocation_run_id == run_id,
        )
        .order_by(AllocationAssignment.reservation_id.asc())
        .populate_existing()
    )
    assignments = lock_query(assignment_query, AllocationAssignment).all()
    proposed = [
        item for item in assignments
        if item.status == AllocationAssignmentStatusEnum.PROPOSED
    ]
    if not proposed:
        if assignments and all(item.status == AllocationAssignmentStatusEnum.APPLIED for item in assignments):
            details = get_allocation_run_details(db, hotel_id=hotel_id, run_id=run_id)
            assert details is not None
            return details
        raise AllocationRuntimeError("Allocation run has no pending proposals")

    active_policy_version_id = _active_policy_version_id_for_acceptance(db, hotel_id)
    if active_policy_version_id != run.policy_version_id:
        raise AllocationRuntimeError("The active allocation policy changed after this proposal; recalculate allocation")

    proposal_ids = {item.reservation_id for item in proposed}
    plan_ids = {item.reservation_id for item in assignments if item.room_id is not None}
    reservation_query = (
        active_reservations(db, hotel_id)
        .filter(Reservation.id.in_(plan_ids))
        .order_by(Reservation.id.asc())
        .populate_existing()
    )
    reservations = lock_query(reservation_query, Reservation).all()
    reservations_by_id = {item.id: item for item in reservations}
    if set(reservations_by_id) != plan_ids:
        raise AllocationRuntimeError("A reservation in this allocation plan is no longer active")

    explanation_rows = (
        db.query(AllocationExplanation)
        .filter(
            AllocationExplanation.hotel_id == hotel_id,
            AllocationExplanation.allocation_run_id == run_id,
            AllocationExplanation.explanation_type == "assignment",
            AllocationExplanation.reservation_id.in_(proposal_ids),
        )
        .order_by(AllocationExplanation.id.asc())
        .all()
    )
    explanation_by_reservation: dict[int, dict] = {}
    for item in explanation_rows:
        explanation_by_reservation[item.reservation_id] = _load_json_dict(item.details_json)
    required_locked_move_approvals = {
        assignment.reservation_id
        for assignment in proposed
        if (
            isinstance(
                explanation_by_reservation.get(assignment.reservation_id, {}).get(
                    "room_assignment_signal"
                ),
                dict,
            )
            and explanation_by_reservation[assignment.reservation_id][
                "room_assignment_signal"
            ].get("requires_explicit_approval") is True
        )
    }
    approved_locked_move_ids = set(explicitly_approved_locked_reservation_ids or set())
    if not approved_locked_move_ids.issubset(required_locked_move_approvals):
        raise AllocationRuntimeError(
            "The one-time locked-move approval does not match this proposal"
        )
    if approved_locked_move_ids and (automatic or user_id is None):
        raise AllocationRuntimeError(
            "Locked reservation moves require explicit approval from an authenticated user"
        )
    locked_moves_left_unchanged = required_locked_move_approvals - approved_locked_move_ids

    all_assignment_explanations = (
        db.query(AllocationExplanation)
        .filter(
            AllocationExplanation.hotel_id == hotel_id,
            AllocationExplanation.allocation_run_id == run_id,
            AllocationExplanation.explanation_type == "assignment",
            AllocationExplanation.reservation_id.in_(plan_ids),
        )
        .order_by(AllocationExplanation.id.asc())
        .all()
    )
    plan_explanation_by_reservation = {
        item.reservation_id: _load_json_dict(item.details_json)
        for item in all_assignment_explanations
    }
    already_applied_rows = (
        db.query(AllocationExplanation)
        .filter(
            AllocationExplanation.hotel_id == hotel_id,
            AllocationExplanation.allocation_run_id == run_id,
            AllocationExplanation.explanation_type.in_(
                ["proposal_auto_applied", "proposal_accepted"]
            ),
            AllocationExplanation.reservation_id.in_(plan_ids),
        )
        .order_by(AllocationExplanation.id.asc())
        .all()
    )
    already_applied_by_reservation = {
        item.reservation_id: _load_json_dict(item.details_json)
        for item in already_applied_rows
    }
    assignment_by_reservation = {item.reservation_id: item for item in assignments}
    for reservation_id, reservation in reservations_by_id.items():
        plan_explanation = plan_explanation_by_reservation.get(reservation_id)
        if not plan_explanation or not plan_explanation.get("source_state_fingerprint"):
            raise AllocationRuntimeError("The allocation plan is missing a source-state snapshot")
        assignment = assignment_by_reservation[reservation_id]
        # First-time assignments may already have been applied by a direct/OTA
        # intake trigger. Their recorded source was intentionally unassigned;
        # their current state is valid only while it still matches the run's
        # chosen destination and dates/category remain in the fingerprint.
        applied_explanation = already_applied_by_reservation.get(reservation_id)
        applied_target_matches = bool(
            applied_explanation
            and applied_explanation.get("target_room_id") == assignment.room_id
        )
        was_initially_assigned = plan_explanation.get("source_room_id") is None
        was_moved_by_this_run = applied_target_matches and not was_initially_assigned
        if (
            assignment.status == AllocationAssignmentStatusEnum.APPLIED
            and reservation.room_id == assignment.room_id
            and (was_initially_assigned or was_moved_by_this_run)
        ):
            expected_state = plan_explanation.get("source_state")
            current_state = _reservation_state_payload(reservation)
            if not isinstance(expected_state, dict):
                raise AllocationRuntimeError("The allocation plan is missing its source-state snapshot")
            expected_state = dict(expected_state)
            expected_state.pop("room_id", None)
            current_state.pop("room_id", None)
            if expected_state != current_state:
                raise AllocationRuntimeError("A reservation changed after this proposal; recalculate allocation")
            continue
        if plan_explanation["source_state_fingerprint"] != _reservation_state_fingerprint(reservation):
            raise AllocationRuntimeError("A reservation changed after this proposal; recalculate allocation")

    active_lock_ids = {
        row[0]
        for row in db.query(ReservationAllocationLock.reservation_id)
        .filter(
            ReservationAllocationLock.hotel_id == hotel_id,
            ReservationAllocationLock.reservation_id.in_(proposal_ids),
            ReservationAllocationLock.is_active.is_(True),
        )
        .all()
    }
    target_room_ids = {
        item.room_id
        for item in proposed
        if item.room_id is not None
        and item.reservation_id not in locked_moves_left_unchanged
    }
    target_room_query = (
        db.query(Room)
        .filter(
            Room.hotel_id == hotel_id,
            Room.id.in_(target_room_ids),
            Room.deleted_at.is_(None),
        )
        .order_by(Room.id.asc())
        .populate_existing()
    ) if target_room_ids else db.query(Room).filter(Room.hotel_id == hotel_id, Room.id == -1)
    target_rooms = lock_query(target_room_query, Room).all()
    rooms_by_id = {item.id: item for item in target_rooms}
    if set(rooms_by_id) != target_room_ids:
        raise AllocationRuntimeError("A proposed target room is no longer available")

    moves: dict[int, int] = {}
    proposed_target_windows: list[tuple[int, date, date, int]] = []
    for assignment in proposed:
        reservation = reservations_by_id[assignment.reservation_id]
        explanation = explanation_by_reservation.get(reservation.id)
        if not explanation or not explanation.get("source_state_fingerprint"):
            raise AllocationRuntimeError("The proposal is missing its source-state snapshot")
        if explanation["source_state_fingerprint"] != _reservation_state_fingerprint(reservation):
            raise AllocationRuntimeError("Reservation changed after this proposal; recalculate allocation")
        room_assignment_signal = explanation.get("room_assignment_signal")
        expected_explicit_lock = bool(
            isinstance(room_assignment_signal, dict)
            and room_assignment_signal.get("explicitly_locked") is True
        )
        current_explicit_lock = bool(
            reservation.allocation_locked or reservation.id in active_lock_ids
        )
        if current_explicit_lock != expected_explicit_lock:
            raise AllocationRuntimeError(
                "A reservation lock changed after this proposal; recalculate allocation"
            )
        if (
            reservation.status in {
                ReservationStatusEnum.PARTIAL_CHECK_IN,
                ReservationStatusEnum.CHECKED_IN,
            }
            or reservation.actual_check_in is not None
        ):
            raise AllocationRuntimeError("A proposed reservation has already checked in")
        if current_explicit_lock and reservation.id not in approved_locked_move_ids:
            if reservation.id not in locked_moves_left_unchanged:
                raise AllocationRuntimeError(
                    "Explicit one-time approval is required for this locked reservation move"
                )
            continue
        if assignment.room_id is None:
            raise AllocationRuntimeError("A proposed reassignment has no destination room")
        room = rooms_by_id[assignment.room_id]
        allowed_categories = explanation.get("allowed_category_ids") or [reservation.category_id]
        if room.category_id not in allowed_categories:
            raise AllocationRuntimeError("A proposed destination is no longer category-compatible")
        if room.status not in {RoomStatusEnum.AVAILABLE, RoomStatusEnum.OCCUPIED, RoomStatusEnum.CLEANING}:
            raise AllocationRuntimeError("A proposed destination room is not reservable")
        if room.category is not None and room.category.max_occupancy < (
            (reservation.num_adults or 0) + (reservation.num_children or 0)
        ):
            raise AllocationRuntimeError("A proposed destination room no longer has enough capacity")
        if bool(reservation.mobility_restriction) and not bool(room.is_accessible):
            raise AllocationRuntimeError("A proposed destination room is not accessible")
        moves[reservation.id] = assignment.room_id
        proposed_target_windows.append(
            (assignment.room_id, reservation.check_in_date, reservation.check_out_date, reservation.id)
        )

    # Confirm the plan still fits alongside reservations outside the solver run.
    # Existing stays included in the plan are compared as a complete final state;
    # all other active stays and blocks are checked against every proposed window.
    active_other_reservations = (
        active_reservations(db, hotel_id)
        .filter(
            Reservation.id.notin_(plan_ids),
            Reservation.status.notin_([ReservationStatusEnum.CANCELLED, ReservationStatusEnum.CHECKED_OUT]),
        )
        .all()
    )
    all_plan_assignments: dict[int, int] = {}
    for item in assignments:
        if item.room_id is None:
            continue
        if item.reservation_id in locked_moves_left_unchanged:
            source_room_id = plan_explanation_by_reservation[item.reservation_id].get(
                "source_room_id"
            )
            if source_room_id is None:
                continue
            all_plan_assignments[item.reservation_id] = source_room_id
        else:
            all_plan_assignments[item.reservation_id] = item.room_id
    plan_reservations_by_id = reservations_by_id
    for room_id, check_in, check_out, reservation_id in proposed_target_windows:
        for other_id, other_room_id in all_plan_assignments.items():
            if other_id == reservation_id or other_room_id != room_id:
                continue
            other = plan_reservations_by_id.get(other_id)
            if other and check_in < other.check_out_date and other.check_in_date < check_out:
                raise AllocationRuntimeError("Proposed assignments conflict with each other; recalculate allocation")
        for other in active_other_reservations:
            if (
                other.room_id == room_id
                and check_in < other.check_out_date
                and other.check_in_date < check_out
            ):
                raise AllocationRuntimeError("A proposed destination is occupied by another reservation")
        if room_has_active_block(
            db,
            hotel_id=hotel_id,
            room_id=room_id,
            start_date=check_in,
            end_date=check_out,
        ):
            raise AllocationRuntimeError("A proposed destination is now blocked")

    try:
        with db.begin_nested():
            apply_allocation_result(
                db,
                AllocationResult(success=True, assignments=moves),
                hotel_id=hotel_id,
                reservations_by_id=reservations_by_id,
                trigger_reason=run.trigger_type,
                trigger_event=(
                    "allocation_auto_applied"
                    if automatic
                    else "allocation_locked_move_approved"
                    if approved_locked_move_ids
                    else "allocation_proposal_accepted"
                ),
                created_by_user_id=user_id,
                one_time_locked_move_approvals=approved_locked_move_ids,
            )
            approved_lock_rows = (
                db.query(ReservationAllocationLock)
                .filter(
                    ReservationAllocationLock.hotel_id == hotel_id,
                    ReservationAllocationLock.reservation_id.in_(approved_locked_move_ids),
                    ReservationAllocationLock.is_active.is_(True),
                )
                .order_by(ReservationAllocationLock.reservation_id.asc())
                .all()
                if approved_locked_move_ids
                else []
            )
            for lock in approved_lock_rows:
                # A one-time approval moves the pin to the newly accepted room;
                # it never releases the lock or permits a later automatic move.
                lock.locked_room_id = moves[lock.reservation_id]
            for assignment in proposed:
                explanation = explanation_by_reservation[assignment.reservation_id]
                if assignment.reservation_id in locked_moves_left_unchanged:
                    if not automatic:
                        assignment.status = AllocationAssignmentStatusEnum.MANUAL_REVIEW
                    db.add(
                        AllocationExplanation(
                            hotel_id=hotel_id,
                            allocation_run_id=run_id,
                            reservation_id=assignment.reservation_id,
                            explanation_type=(
                                "proposal_lock_pending_approval"
                                if automatic
                                else "proposal_lock_preserved"
                            ),
                            summary=(
                                "Automatic allocation kept the reservation in its current room; one-time approval is required to apply this proposed move"
                                if automatic
                                else "No one-time approval was given; the reservation stayed in its current room and remains locked"
                            ),
                            details_json=json.dumps(
                                {
                                    "source_room_id": explanation.get("source_room_id"),
                                    "suggested_room_id": assignment.room_id,
                                    "one_time_lock_override": False,
                                    "lock_preserved": True,
                                },
                                ensure_ascii=True,
                                sort_keys=True,
                            ),
                        )
                    )
                    continue
                assignment.status = AllocationAssignmentStatusEnum.APPLIED
                assignment.applied_at = datetime.now(timezone.utc)
                db.add(
                    AllocationExplanation(
                        hotel_id=hotel_id,
                        allocation_run_id=run_id,
                        reservation_id=assignment.reservation_id,
                        explanation_type=(
                            "proposal_auto_applied" if automatic else "proposal_accepted"
                        ),
                        summary=(
                            "Allocation engine automatically applied the eligible room reassignment"
                            if automatic
                            else "Reception approved a one-time move; the reassignment lock remains active"
                            if assignment.reservation_id in approved_locked_move_ids
                            else "Reception accepted the proposed room reassignment"
                        ),
                        details_json=json.dumps(
                            {
                                "source_room_id": explanation.get("source_room_id"),
                                "target_room_id": assignment.room_id,
                                "applied_by": "allocation_engine" if automatic else "user",
                                "accepted_by_user_id": None if automatic else user_id,
                                "one_time_lock_override": assignment.reservation_id in approved_locked_move_ids,
                                "lock_preserved": assignment.reservation_id in approved_locked_move_ids,
                                "applied_at": datetime.now(timezone.utc).isoformat(),
                            },
                            ensure_ascii=True,
                            sort_keys=True,
                        ),
                    )
                )
            db.add(
                SecurityAuditLog(
                    hotel_id=hotel_id,
                    user_id=user_id,
                    action=(
                        "allocation.proposal.auto_applied"
                        if automatic
                        else "allocation.proposal.accepted"
                    ),
                    resource_type="allocation_run",
                    resource_id=str(run_id),
                    details=json.dumps(
                        {
                            "reservation_ids": sorted(moves),
                            "room_block_plan": allow_room_block_plan,
                            "applied_by": "allocation_engine" if automatic else "user",
                            "one_time_locked_move_approval_ids": sorted(approved_locked_move_ids),
                            "one_time_lock_target_rooms": {
                                str(reservation_id): moves[reservation_id]
                                for reservation_id in sorted(approved_locked_move_ids)
                            },
                            "locked_moves_left_unchanged": sorted(locked_moves_left_unchanged),
                        },
                        sort_keys=True,
                    ),
                )
            )
    except AllocationError as exc:
        raise AllocationRuntimeError(str(exc)) from exc

    db.flush()
    details = get_allocation_run_details(db, hotel_id=hotel_id, run_id=run_id)
    assert details is not None
    return details


def auto_apply_safe_allocation_run(
    db: Session,
    *,
    hotel_id: int,
    run_id: int,
) -> AllocationRunDetails | None:
    """Apply a complete successful run through the locked acceptance workflow.

    Room-block plans keep their dedicated atomic acceptance path. Explicit
    reservation locks and check-in state are revalidated by
    ``accept_allocation_run`` and cannot be bypassed here.
    """
    run = (
        db.query(AllocationRun)
        .filter(AllocationRun.id == run_id, AllocationRun.hotel_id == hotel_id)
        .one_or_none()
    )
    if run is None:
        raise AllocationRuntimeError("Allocation run not found for this hotel")

    details = get_allocation_run_details(db, hotel_id=hotel_id, run_id=run_id)
    if details is None or run.status != AllocationRunStatusEnum.SUCCEEDED:
        return details

    context_row = (
        db.query(AllocationExplanation)
        .filter(
            AllocationExplanation.hotel_id == hotel_id,
            AllocationExplanation.allocation_run_id == run_id,
            AllocationExplanation.explanation_type == "proposal_context",
        )
        .order_by(AllocationExplanation.id.asc())
        .first()
    )
    proposal_context = _load_json_dict(context_row.details_json) if context_row else {}
    if proposal_context.get("kind") in {"room_block", "room_block_extension"}:
        return details

    pending_moves = (
        db.query(AllocationAssignment.id)
        .filter(
            AllocationAssignment.hotel_id == hotel_id,
            AllocationAssignment.allocation_run_id == run_id,
            AllocationAssignment.status == AllocationAssignmentStatusEnum.PROPOSED,
        )
        .count()
    )
    if not pending_moves:
        return details

    assignment_explanations = {
        item.reservation_id: _load_json_dict(item.details_json)
        for item in details.explanations
        if item.explanation_type == "assignment"
    }
    safe_moves = []
    for assignment in details.assignments:
        if assignment.status != AllocationAssignmentStatusEnum.PROPOSED:
            continue
        room_signal = assignment_explanations.get(
            assignment.reservation_id, {}
        ).get("room_assignment_signal")
        if not isinstance(room_signal, dict) or room_signal.get(
            "requires_explicit_approval"
        ) is not True:
            safe_moves.append(assignment)
    if not safe_moves:
        # Keep locked moves visible in the successful run so an authenticated
        # operator can approve each exception once from the review screen.
        return details

    # No room changes escape this savepoint unless the full acceptance
    # validation passes. A stale plan is returned to the caller for retry.
    with db.begin_nested():
        return accept_allocation_run(
            db,
            hotel_id=hotel_id,
            run_id=run_id,
            user_id=None,
            automatic=True,
        )


def reject_allocation_run(
    db: Session,
    *,
    hotel_id: int,
    run_id: int,
    user_id: int | None,
) -> AllocationRunDetails:
    """Reject outstanding solver proposals without changing room assignments."""
    run_query = db.query(AllocationRun).filter(
        AllocationRun.id == run_id,
        AllocationRun.hotel_id == hotel_id,
    ).populate_existing()
    run = lock_query(run_query, AllocationRun).one_or_none()
    if run is None:
        raise AllocationRuntimeError("Allocation run not found for this hotel")
    assignment_query = (
        db.query(AllocationAssignment)
        .filter(
            AllocationAssignment.hotel_id == hotel_id,
            AllocationAssignment.allocation_run_id == run_id,
        )
        .order_by(AllocationAssignment.reservation_id.asc())
        .populate_existing()
    )
    assignments = lock_query(assignment_query, AllocationAssignment).all()
    proposed = [item for item in assignments if item.status == AllocationAssignmentStatusEnum.PROPOSED]
    if not proposed and assignments and all(item.status == AllocationAssignmentStatusEnum.REJECTED for item in assignments):
        details = get_allocation_run_details(db, hotel_id=hotel_id, run_id=run_id)
        assert details is not None
        return details
    if not proposed:
        raise AllocationRuntimeError("Allocation run has no pending proposals")
    now = datetime.now(timezone.utc)
    for assignment in proposed:
        assignment.status = AllocationAssignmentStatusEnum.REJECTED
        db.add(
            AllocationExplanation(
                hotel_id=hotel_id,
                allocation_run_id=run_id,
                reservation_id=assignment.reservation_id,
                explanation_type="proposal_rejected",
                summary="Reception rejected the proposed room reassignment",
                details_json=json.dumps({"rejected_by_user_id": user_id, "rejected_at": now.isoformat()}, sort_keys=True),
            )
        )
    db.add(
        SecurityAuditLog(
            hotel_id=hotel_id,
            user_id=user_id,
            action="allocation.proposal.rejected",
            resource_type="allocation_run",
            resource_id=str(run_id),
            details=json.dumps({"reservation_ids": sorted(item.reservation_id for item in proposed)}, sort_keys=True),
        )
    )
    db.flush()
    details = get_allocation_run_details(db, hotel_id=hotel_id, run_id=run_id)
    assert details is not None
    return details


def set_reservation_reassignment_lock(
    db: Session,
    *,
    hotel_id: int,
    reservation_id: int,
    locked: bool,
    reason: str | None,
    user_id: int | None,
) -> Reservation:
    """Set the owner's explicit No permitir reasignar flag and audit it."""
    reservation_query = active_reservations(db, hotel_id).filter(Reservation.id == reservation_id).populate_existing()
    reservation = lock_query(reservation_query, Reservation).one_or_none()
    if reservation is None:
        raise AllocationRuntimeError("Reservation not found for this hotel")
    if locked and reservation.room_id is None:
        raise AllocationRuntimeError("Assign a room before preventing reassignment")

    lock_query_obj = (
        db.query(ReservationAllocationLock)
        .filter(
            ReservationAllocationLock.hotel_id == hotel_id,
            ReservationAllocationLock.reservation_id == reservation.id,
        )
        .order_by(ReservationAllocationLock.id.asc())
        .populate_existing()
    )
    lock_rows = lock_query(lock_query_obj, ReservationAllocationLock).all()
    active_lock = next((row for row in lock_rows if row.is_active), None)
    prior_value = bool(reservation.allocation_locked or active_lock)
    reservation.allocation_locked = locked
    now = datetime.now(timezone.utc)
    if locked:
        if active_lock is None:
            active_lock = next(iter(lock_rows), None)
            if active_lock is None:
                active_lock = ReservationAllocationLock(
                    hotel_id=hotel_id,
                    reservation_id=reservation.id,
                    locked_room_id=reservation.room_id,
                    lock_reason_code="manual_pin",
                    notes=reason,
                    created_by_user_id=user_id,
                    is_active=True,
                )
                db.add(active_lock)
            else:
                active_lock.locked_room_id = reservation.room_id
                active_lock.lock_reason_code = "manual_pin"
                active_lock.notes = reason
                active_lock.created_by_user_id = user_id
                active_lock.created_at = now
                active_lock.released_at = None
                active_lock.is_active = True
        else:
            active_lock.locked_room_id = reservation.room_id
            active_lock.lock_reason_code = "manual_pin"
            active_lock.notes = reason
    elif active_lock is not None:
        active_lock.is_active = False
        active_lock.released_at = now

    db.add(
        SecurityAuditLog(
            hotel_id=hotel_id,
            user_id=user_id,
            action="reservation.reassignment_lock.updated",
            resource_type="reservation",
            resource_id=str(reservation.id),
            details=json.dumps(
                {"previous_locked": prior_value, "locked": locked, "reason": reason},
                ensure_ascii=True,
                sort_keys=True,
            ),
        )
    )
    db.flush()
    return reservation


def _create_assignment_explanation(
    *,
    hotel_id: int,
    allocation_run_id: int,
    reservation: Reservation,
    reservation_slot,
    room_slot,
    room_id: int,
    was_moved: bool,
) -> AllocationExplanation:
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
    prior_stay_room_id = reservation_slot.prior_stay_room_id if reservation_slot else None
    avoided_room_ids = set(reservation_slot.avoided_room_ids) if reservation_slot else set()
    if room_id == prior_stay_room_id:
        summary_parts.append("returning guest, previous completed room honored")
    elif room_id in avoided_room_ids:
        summary_parts.append("rejected room assigned as a soft signal")
    elif avoided_room_ids:
        summary_parts.append("active room rejection respected")
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
        "prior_stay_room_id": prior_stay_room_id,
        "avoided_room_ids": sorted(avoided_room_ids),
        "source_room_id": reservation.room_id,
        "source_state": _reservation_state_payload(reservation),
        "source_state_fingerprint": _reservation_state_fingerprint(reservation),
    }
    if reservation_slot is not None:
        details["room_assignment_signal"] = {
            "mobility_restriction": reservation_slot.mobility_restriction,
            "prior_stay_room_id": reservation_slot.prior_stay_room_id,
            "avoided_room_ids": sorted(reservation_slot.avoided_room_ids),
            "explicitly_locked": reservation_slot.explicitly_locked,
            "requires_explicit_approval": bool(
                reservation_slot.explicitly_locked
                and reservation_slot.current_room_id != room_id
            ),
        }
    return AllocationExplanation(
        hotel_id=hotel_id,
        allocation_run_id=allocation_run_id,
        reservation_id=reservation.id,
        explanation_type="assignment",
        summary=summary,
        details_json=json.dumps(details, ensure_ascii=True, sort_keys=True),
    )


def _reservation_state_fingerprint(reservation: Reservation) -> str:
    """Hash only assignment-relevant fields so stale proposals fail closed."""
    state = _reservation_state_payload(reservation)
    serialized = json.dumps(state, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _reservation_state_payload(reservation: Reservation) -> dict:
    status = reservation.status.value if hasattr(reservation.status, "value") else str(reservation.status)

    return {
        "hotel_id": reservation.hotel_id,
        "reservation_id": reservation.id,
        "room_id": reservation.room_id,
        "status": status,
        "check_in_date": reservation.check_in_date.isoformat() if reservation.check_in_date else None,
        "check_out_date": reservation.check_out_date.isoformat() if reservation.check_out_date else None,
        "category_id": reservation.category_id,
        "sellable_product_id": reservation.sellable_product_id,
        "num_adults": reservation.num_adults,
        "num_children": reservation.num_children,
        "mobility_restriction": bool(getattr(reservation, "mobility_restriction", False)),
        "allocation_locked": bool(getattr(reservation, "allocation_locked", False)),
        "actual_check_in": (
            reservation.actual_check_in.isoformat()
            if getattr(reservation, "actual_check_in", None)
            else None
        ),
    }


def _load_json_dict(raw_value: str | None) -> dict:
    if not raw_value:
        return {}
    try:
        loaded = json.loads(raw_value)
    except (TypeError, json.JSONDecodeError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


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
