"""
AllocationEngine — Intelligent Room Assignment using Google OR-Tools (CP-SAT Solver).

This is the core optimization module that:
1. Takes a set of reservations and available rooms
2. Assigns rooms to reservations optimally
3. Respects hard constraints (no overlap, category match, checked-in guests locked)
4. Optimizes for continuous block occupancy and minimizes fragmentation

The solver uses a Constraint Programming (CP-SAT) model where:
- Decision variables: x[r, h] = 1 if reservation r is assigned to room h
- Hard constraints ensure feasibility
- Objective function penalizes fragmentation gaps
"""
from datetime import date, timedelta
from typing import Optional
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.models.room import Room, RoomStatusEnum
from app.services.room_service import active_rooms
from app.models.reservation import Reservation, ReservationStatusEnum
from app.services.reservation_service import _active_reservations_without_hotel, active_reservations


class AllocationError(Exception):
    """Custom exception for allocation engine errors."""
    pass


@dataclass
class ReservationSlot:
    """Lightweight representation of a reservation for the solver."""
    reservation_id: int
    category_id: int
    check_in: date
    check_out: date
    current_room_id: Optional[int]
    is_locked: bool  # True if checked_in (cannot be moved)
    guest_id: Optional[int] = None
    num_guests: int = 1
    mobility_restriction: bool = False
    allowed_category_ids: list[int] = field(default_factory=list)
    category_priority_by_id: dict[int, int] = field(default_factory=dict)
    prior_stay_room_id: Optional[int] = None
    avoided_room_ids: list[int] = field(default_factory=list)

    @property
    def effective_allowed_category_ids(self) -> list[int]:
        """Return allowed categories, falling back to [category_id] if empty."""
        return self.allowed_category_ids if self.allowed_category_ids else [self.category_id]

    def category_priority(self, category_id: int) -> int:
        if category_id == self.category_id:
            return 0
        return self.category_priority_by_id.get(category_id, 10_000)

    @property
    def nights(self) -> int:
        return (self.check_out - self.check_in).days

    @property
    def date_range(self) -> set[date]:
        """Set of dates occupied (check_in to check_out - 1)."""
        return {self.check_in + timedelta(days=d) for d in range(self.nights)}


@dataclass
class RoomSlot:
    """Lightweight representation of a room for the solver."""
    room_id: int
    room_number: str
    category_id: int
    max_occupancy: int = 2
    floor: int = 0
    score: Optional[int] = None
    is_accessible: bool = False


@dataclass
class AllocationResult:
    """Result of the allocation engine run."""
    success: bool
    assignments: dict[int, int] = field(default_factory=dict)  # reservation_id → room_id
    unassigned_reservations: list[int] = field(default_factory=list)
    moved_reservations: list[int] = field(default_factory=list)
    objective_value: float = 0.0
    error: Optional[str] = None


def _check_overlap(slot_a: ReservationSlot, slot_b: ReservationSlot) -> bool:
    """Check if two reservation slots overlap in time."""
    return slot_a.check_in < slot_b.check_out and slot_b.check_in < slot_a.check_out


def _one_night_gap_penalty_for_room(
    reservation: ReservationSlot,
    occupancy: list[tuple[date, date]],
) -> int:
    """
    Estimate how many single-night gaps remain if the reservation is placed on this room.
    Lower is better.
    """
    stays = sorted([*occupancy, (reservation.check_in, reservation.check_out)], key=lambda item: item[0])
    gaps = 0
    for idx in range(len(stays) - 1):
        left_out = stays[idx][1]
        right_in = stays[idx + 1][0]
        if (right_in - left_out).days == 1:
            gaps += 1
    return gaps


def _adjacency_bonus_for_room(
    reservation: ReservationSlot,
    occupancy: list[tuple[date, date]],
) -> int:
    """
    Count how many existing stays touch the candidate reservation without overlap.
    Higher is better because it builds longer continuous occupancy blocks.
    """
    bonus = 0
    for occ_in, occ_out in occupancy:
        if occ_out == reservation.check_in:
            bonus += 1
        if occ_in == reservation.check_out:
            bonus += 1
    return bonus


def _guest_room_signal_score(
    reservation: ReservationSlot,
    room: RoomSlot,
    *,
    prior_stay_room_bonus: int,
    avoided_room_penalty: int,
) -> int:
    """Return the soft, derived guest-room signal for one candidate room.

    ``avoid`` intentionally remains a score, not an eligibility constraint:
    assigning a disliked room is preferable to leaving a guest unassigned when
    it is the only compatible room.
    """
    score = 0
    if room.room_id == reservation.prior_stay_room_id:
        score += prior_stay_room_bonus
    if room.room_id in reservation.avoided_room_ids:
        score -= avoided_room_penalty
    return score


def run_allocation(
    reservations: list[ReservationSlot],
    rooms: list[RoomSlot],
    optimization_horizon: Optional[tuple[date, date]] = None,
    policy_constraints: Optional[dict] = None,
    policy_weights: Optional[dict] = None,
) -> AllocationResult:
    """
    Run the CP-SAT solver to optimally assign rooms to reservations.
    
    Args:
        reservations: List of reservation slots to assign.
        rooms: List of available room slots.
        optimization_horizon: Optional (start, end) date range for gap penalty.
    
    Returns:
        AllocationResult with assignments mapping.
    
    Hard Constraints:
        1. Each reservation is assigned to exactly one room
        2. Room category must match reservation category
        3. No two reservations assigned to the same room can overlap in time
        4. Locked reservations (checked_in) stay in their current room
    
    Objective:
        Minimize fragmentation: penalize single-day gaps between reservations
        on the same room (encourages continuous blocks).
    """
    try:
        from ortools.sat.python import cp_model
    except ImportError:
        return _run_allocation_greedy(
            reservations,
            rooms,
            optimization_horizon,
            policy_constraints=policy_constraints,
            policy_weights=policy_weights,
        )

    if not reservations:
        return AllocationResult(success=True)

    policy_constraints = policy_constraints or {}
    policy_weights = policy_weights or {}
    stability_weight = int(policy_weights.get("stability", 5))
    exact_match_weight = int(policy_weights.get("prefer_exact_match", 500))
    room_usage_penalty = int(policy_weights.get("room_usage_penalty", 50))
    unassigned_penalty = int(policy_weights.get("unassigned_penalty", 10000))
    fallback_priority_penalty = int(policy_weights.get("fallback_priority_penalty", 25))
    one_night_gap_penalty = int(policy_weights.get("minimize_one_night_gaps", room_usage_penalty * 2))
    room_score_tiebreaker = int(policy_weights.get("room_score_tiebreaker", 1))
    # Signals are intentionally smaller than the category objective and never
    # apply when an already-assigned reservation can remain in its room. They
    # steer fresh allocation without introducing preference-driven churn.
    prior_stay_room_bonus = max(
        0,
        min(int(policy_weights.get("prior_stay_room_bonus", 100)), max(exact_match_weight - 1, 0)),
    )
    guest_room_avoidance_penalty = max(
        0,
        min(
            int(policy_weights.get("guest_room_avoidance_penalty", 1000)),
            max(unassigned_penalty - 1, 0),
        ),
    )

    model = cp_model.CpModel()

    # ── Decision Variables ──
    # x[r_idx, h_idx] = 1 if reservation r is assigned to room h
    x = {}
    for r_idx, res in enumerate(reservations):
        for h_idx, room in enumerate(rooms):
            x[r_idx, h_idx] = model.NewBoolVar(f"x_{r_idx}_{h_idx}")

    # is_assigned[r_idx] = sum(x[r_idx, *])
    is_assigned = {}
    for r_idx in range(len(reservations)):
        is_assigned[r_idx] = model.NewBoolVar(f"assigned_{r_idx}")
        model.Add(
            sum(x[r_idx, h_idx] for h_idx in range(len(rooms))) == is_assigned[r_idx]
        )
        if reservations[r_idx].is_locked:
            model.Add(is_assigned[r_idx] == 1)

    # ── Hard Constraint 2: Category match (including upgrades with same bath type) ──
    for r_idx, res in enumerate(reservations):
        mobility_floor = _lowest_available_compatible_floor(res, rooms, reservations)
        for h_idx, room in enumerate(rooms):
            if room.category_id not in res.effective_allowed_category_ids:
                model.Add(x[r_idx, h_idx] == 0)
            if room.max_occupancy < res.num_guests:
                model.Add(x[r_idx, h_idx] == 0)
            if res.mobility_restriction:
                if not room.is_accessible:
                    model.Add(x[r_idx, h_idx] == 0)
                elif mobility_floor is not None and room.floor != mobility_floor:
                    model.Add(x[r_idx, h_idx] == 0)

    # ── Hard Constraint 3: No temporal overlap on the same room ──
    for h_idx in range(len(rooms)):
        for r1_idx in range(len(reservations)):
            for r2_idx in range(r1_idx + 1, len(reservations)):
                if _check_overlap(reservations[r1_idx], reservations[r2_idx]):
                    # These two cannot both be assigned to room h
                    model.Add(x[r1_idx, h_idx] + x[r2_idx, h_idx] <= 1)

    # ── Hard Constraint 4: Locked reservations stay in their current room ──
    for r_idx, res in enumerate(reservations):
        if res.is_locked and res.current_room_id is not None:
            for h_idx, room in enumerate(rooms):
                if room.room_id == res.current_room_id:
                    model.Add(x[r_idx, h_idx] == 1)
                else:
                    model.Add(x[r_idx, h_idx] == 0)

    # ── Objective: Minimize fragmentation ──
    # For each room, penalize small gaps between consecutive reservations.
    # We want reservations on the same room to form continuous blocks.
    
    # Determine horizon
    if optimization_horizon:
        horizon_start, horizon_end = optimization_horizon
    else:
        all_dates = set()
        for res in reservations:
            all_dates.update(res.date_range)
        if all_dates:
            horizon_start = min(all_dates)
            horizon_end = max(all_dates) + timedelta(days=1)
        else:
            # Pure solver: no db/hotel here, and this branch only runs when
            # there are no reservations at all, so the horizon is unused. Real
            # callers pass optimization_horizon (see
            # allocation_runtime_service, which resolves it hotel-locally).
            horizon_start = date.today()
            horizon_end = horizon_start + timedelta(days=30)

    total_days = (horizon_end - horizon_start).days
    if total_days <= 0:
        total_days = 30

    # Build occupancy indicators for gap detection
    # For each room h and day d, is_occupied[h,d] = 1 if any assigned reservation covers day d
    is_occupied = {}
    for h_idx in range(len(rooms)):
        for d in range(total_days):
            current_date = horizon_start + timedelta(days=d)
            # Find reservations that cover this date
            covering = []
            for r_idx, res in enumerate(reservations):
                if current_date in res.date_range:
                    covering.append(r_idx)

            if covering:
                is_occupied[h_idx, d] = model.NewBoolVar(f"occ_{h_idx}_{d}")
                model.AddMaxEquality(
                    is_occupied[h_idx, d],
                    [x[r_idx, h_idx] for r_idx in covering]
                )
            else:
                is_occupied[h_idx, d] = model.NewConstant(0)

    # Gap penalty: penalize day d if day d-1 and d+1 are occupied but d is not
    gap_penalties = []

    for h_idx in range(len(rooms)):
        for d in range(1, total_days - 1):
            prev_occ = is_occupied.get((h_idx, d - 1))
            curr_occ = is_occupied.get((h_idx, d))
            next_occ = is_occupied.get((h_idx, d + 1))

            if prev_occ is not None and curr_occ is not None and next_occ is not None:
                gap = model.NewBoolVar(f"gap_{h_idx}_{d}")
                model.Add(gap <= prev_occ)
                model.Add(gap <= next_occ)
                model.Add(gap + curr_occ <= 1)
                model.Add(gap >= prev_occ + next_occ - curr_occ - 1)
                gap_penalties.append(gap)

    # Simplified but effective objective: maximize continuous usage per room
    # Score = sum of occupied days per room (encourages packing)
    # + bonus for keeping current assignments (stability)
    # + bonus for exact category match (avoids unnecessary upgrades)
    occupancy_score = []
    stability_bonus = []
    category_match_bonus = []
    fallback_penalties = []
    room_score_bonus = []
    prior_stay_room_bonus_terms = []
    guest_room_avoidance_penalty_terms = []
    rooms_by_id = {room.room_id: room for room in rooms}

    for r_idx, res in enumerate(reservations):
        current_room = rooms_by_id.get(res.current_room_id)
        current_room_is_compatible = bool(
            current_room
            and current_room.category_id in res.effective_allowed_category_ids
            and current_room.max_occupancy >= res.num_guests
            and (not res.mobility_restriction or current_room.is_accessible)
        )
        for h_idx, room in enumerate(rooms):
            # Occupancy contribution: each night assigned to a room adds to score
            occupancy_score.append((x[r_idx, h_idx], res.nights))

            # Stability: prefer keeping reservation in current room (if one exists)
            if res.current_room_id == room.room_id and not res.is_locked:
                stability_bonus.append((x[r_idx, h_idx], stability_weight))

            if not current_room_is_compatible and room.room_id == res.prior_stay_room_id:
                prior_stay_room_bonus_terms.append(
                    (x[r_idx, h_idx], prior_stay_room_bonus)
                )
            if not current_room_is_compatible and room.room_id in res.avoided_room_ids:
                guest_room_avoidance_penalty_terms.append(
                    (x[r_idx, h_idx], guest_room_avoidance_penalty)
                )

            # Category match bonus: heavily penalize upgrading if original category is available
            if room.category_id == res.category_id:
                category_match_bonus.append((x[r_idx, h_idx], exact_match_weight))
            else:
                fallback_penalties.append(
                    (x[r_idx, h_idx], res.category_priority(room.category_id) * fallback_priority_penalty)
                )
            if room.score is not None:
                room_score_bonus.append((x[r_idx, h_idx], max(0, min(int(room.score), 10)) * room_score_tiebreaker))

    # Concentration bonus: penalize spreading across many rooms
    # For each room, add penalty if it has any reservation (encourages packing)
    room_usage = {}
    for h_idx in range(len(rooms)):
        room_has_any = model.NewBoolVar(f"room_used_{h_idx}")
        assignments_to_room = [x[r_idx, h_idx] for r_idx in range(len(reservations))]
        if assignments_to_room:
            model.AddMaxEquality(room_has_any, assignments_to_room)
        else:
            model.Add(room_has_any == 0)
        room_usage[h_idx] = room_has_any

    # Objective: maximize occupancy score + stability + category match, minimize rooms used
    # Category match bonus (500) prevents unnecessary upgrades.
    # Unassigned penalty (10000/res) must dominate everything else to try to fit everyone.
    model.Maximize(
        sum(var * coeff for var, coeff in occupancy_score)
        + sum(var * coeff for var, coeff in stability_bonus)
        + sum(var * coeff for var, coeff in prior_stay_room_bonus_terms)
        + sum(var * coeff for var, coeff in category_match_bonus)
        + sum(var * coeff for var, coeff in room_score_bonus)
        - sum(room_usage[h_idx] * room_usage_penalty for h_idx in range(len(rooms)))
        - sum(var * coeff for var, coeff in fallback_penalties)
        - sum(var * coeff for var, coeff in guest_room_avoidance_penalty_terms)
        - sum(gap * one_night_gap_penalty for gap in gap_penalties)
        - sum((1 - is_assigned[r_idx]) * unassigned_penalty for r_idx in range(len(reservations)))
    )

    # ── Solve ──
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 30.0
    solver.parameters.num_workers = 4

    status = solver.Solve(model)

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        assignments = {}
        unassigned = []
        moved = []
        for r_idx, res in enumerate(reservations):
            assigned = False
            for h_idx, room in enumerate(rooms):
                if solver.Value(x[r_idx, h_idx]) == 1:
                    assigned = True
                    assignments[res.reservation_id] = room.room_id
                    if (
                        res.current_room_id is not None
                        and res.current_room_id != room.room_id
                        and not res.is_locked
                    ):
                        moved.append(res.reservation_id)
                    break
            if not assigned:
                unassigned.append(res.reservation_id)

        return AllocationResult(
            success=len(unassigned) == 0,
            assignments=assignments,
            unassigned_reservations=unassigned,
            moved_reservations=moved,
            objective_value=solver.ObjectiveValue(),
        )
    else:
        return AllocationResult(
            success=False,
            error=f"Solver status: {solver.StatusName(status)}. No feasible assignment found.",
        )


def _run_allocation_greedy(
    reservations: list[ReservationSlot],
    rooms: list[RoomSlot],
    optimization_horizon: Optional[tuple[date, date]] = None,
    policy_constraints: Optional[dict] = None,
    policy_weights: Optional[dict] = None,
) -> AllocationResult:
    """
    Greedy fallback allocation when OR-Tools is not available.
    Simple first-fit approach respecting all hard constraints.
    """
    assignments: dict[int, int] = {}
    moved: list[int] = []
    policy_weights = policy_weights or {}
    unassigned_penalty = int(policy_weights.get("unassigned_penalty", 10000))
    prior_stay_room_bonus = max(0, int(policy_weights.get("prior_stay_room_bonus", 100)))
    guest_room_avoidance_penalty = max(
        0,
        min(
            int(policy_weights.get("guest_room_avoidance_penalty", 1000)),
            max(unassigned_penalty - 1, 0),
        ),
    )

    # Group rooms by category
    rooms_by_category: dict[int, list[RoomSlot]] = {}
    for room in rooms:
        rooms_by_category.setdefault(room.category_id, []).append(room)

    # Track room occupancy: room_id → list of (check_in, check_out)
    room_occupancy: dict[int, list[tuple[date, date]]] = {r.room_id: [] for r in rooms}
    rooms_by_id = {room.room_id: room for room in rooms}

    # Sort reservations: locked first, then by check-in date, then by length (longer first)
    sorted_reservations = sorted(
        reservations,
        key=lambda r: (not r.is_locked, r.check_in, -r.nights),
    )

    for res in sorted_reservations:
        # If locked, assign to current room
        if res.is_locked and res.current_room_id is not None:
            current_room = rooms_by_id.get(res.current_room_id)
            if current_room is not None and current_room.max_occupancy >= res.num_guests:
                assignments[res.reservation_id] = res.current_room_id
                room_occupancy[res.current_room_id].append((res.check_in, res.check_out))
            continue

        # Find available rooms from all allowed categories
        candidate_rooms = []
        for cat_id in res.effective_allowed_category_ids:
            candidate_rooms.extend(rooms_by_category.get(cat_id, []))
        candidate_rooms = [
            room for room in candidate_rooms
            if room.max_occupancy >= res.num_guests
        ]
        if res.mobility_restriction:
            candidate_rooms = [room for room in candidate_rooms if room.is_accessible]

        # Preserve an already compatible current assignment before applying
        # either soft signal. Avoided rooms still remain candidates, so the
        # only feasible room is always assigned.
        has_guest_room_signal = res.prior_stay_room_id is not None or bool(res.avoided_room_ids)
        if res.current_room_id is not None:
            current_first = sorted(
                candidate_rooms,
                key=lambda r: (
                    0 if has_guest_room_signal and r.room_id == res.current_room_id else 1,
                    -_guest_room_signal_score(
                        res,
                        r,
                        prior_stay_room_bonus=prior_stay_room_bonus,
                        avoided_room_penalty=guest_room_avoidance_penalty,
                    ),
                    0 if r.category_id == res.category_id else 1,
                    _one_night_gap_penalty_for_room(res, room_occupancy.get(r.room_id, [])),
                    -_adjacency_bonus_for_room(res, room_occupancy.get(r.room_id, [])),
                    0 if r.room_id == res.current_room_id else 1,
                    res.category_priority(r.category_id),
                    r.floor if res.mobility_restriction else 0,
                    -(r.score or 0),
                    -len(room_occupancy.get(r.room_id, [])),
                ),
            )
        else:
            # Prefer exact category match
            current_first = sorted(
                candidate_rooms,
                key=lambda r: (
                    -_guest_room_signal_score(
                        res,
                        r,
                        prior_stay_room_bonus=prior_stay_room_bonus,
                        avoided_room_penalty=guest_room_avoidance_penalty,
                    ),
                    0 if r.category_id == res.category_id else 1,
                    _one_night_gap_penalty_for_room(res, room_occupancy.get(r.room_id, [])),
                    -_adjacency_bonus_for_room(res, room_occupancy.get(r.room_id, [])),
                    res.category_priority(r.category_id),
                    r.floor if res.mobility_restriction else 0,
                    -(r.score or 0),
                    -len(room_occupancy.get(r.room_id, [])),
                ),
            )

        assigned = False
        for room in current_first:
            # Check no overlap with existing assignments on this room
            conflicts = False
            for occ_in, occ_out in room_occupancy.get(room.room_id, []):
                if res.check_in < occ_out and occ_in < res.check_out:
                    conflicts = True
                    break

            if not conflicts:
                assignments[res.reservation_id] = room.room_id
                room_occupancy[room.room_id].append((res.check_in, res.check_out))
                if (
                    res.current_room_id is not None
                    and res.current_room_id != room.room_id
                ):
                    moved.append(res.reservation_id)
                assigned = True
                break

    unassigned = list(set(r.reservation_id for r in reservations) - set(assignments.keys()))
    return AllocationResult(
        success=len(unassigned) == 0,
        assignments=assignments,
        unassigned_reservations=unassigned,
        moved_reservations=moved,
    )


def apply_allocation_result(
    db: Session,
    result: AllocationResult,
    hotel_id: Optional[int] = None,
    *,
    trigger_reason: str = "allocation_recalculate",
    trigger_event: Optional[str] = None,
    created_by_user_id: Optional[int] = None,
) -> list[Reservation]:
    """
    Apply the solver's assignments to the database.
    Updates room_id on each reservation.
    """
    if result.error:
        raise AllocationError(result.error)

    from app.models.operations import RoomMovementGroup, RoomMoveEvent, RoomMoveTypeEnum

    updated = []
    pending_moves: list[tuple[Reservation, int, int | None]] = []
    for reservation_id, room_id in result.assignments.items():
        reservation_query = (
            active_reservations(db, hotel_id)
            if hotel_id is not None
            else _active_reservations_without_hotel(db)
        ).filter(Reservation.id == reservation_id)
        reservation = reservation_query.first()
        if reservation and (hotel_id is None or getattr(reservation, "hotel_id", None) == hotel_id):
            previous_room_id = reservation.room_id
            if previous_room_id != room_id:
                pending_moves.append((reservation, room_id, previous_room_id))
            reservation.room_id = room_id
            updated.append(reservation)

    if pending_moves:
        group_hotel_id = hotel_id if hotel_id is not None else pending_moves[0][0].hotel_id
        movement_group = RoomMovementGroup(
            hotel_id=group_hotel_id,
            trigger_reason=trigger_reason,
            notes=f"Allocation run moved {len(pending_moves)} reservation(s)",
            created_by_user_id=created_by_user_id,
        )
        db.add(movement_group)
        db.flush()
        for reservation, room_id, previous_room_id in pending_moves:
            status_value = reservation.status.value if hasattr(reservation.status, "value") else str(reservation.status)
            db.add(
                RoomMoveEvent(
                    hotel_id=reservation.hotel_id,
                    reservation_id=reservation.id,
                    movement_group_id=movement_group.id,
                    from_room_id=previous_room_id,
                    to_room_id=room_id,
                    move_type=RoomMoveTypeEnum.AUTO_ASSIGNMENT,
                    reason_code=trigger_reason,
                    trigger_event=trigger_event,
                    state_before=f"status={status_value};room_id={previous_room_id}",
                    state_after=f"status={status_value};room_id={room_id}",
                    created_by_user_id=created_by_user_id,
                )
            )
            
    if result.unassigned_reservations:
        # No borres asignaciones existentes; informá al caller para que actúe.
        raise AllocationError(
            f"Sin habitaciones disponibles para las reservas: {', '.join(map(str, result.unassigned_reservations))}"
        )

    db.flush()
    return updated


def build_slots_from_db(
    db: Session,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    hotel_id: Optional[int] = None,
    policy_constraints: Optional[dict] = None,
) -> tuple[list[ReservationSlot], list[RoomSlot]]:
    """
    Load reservations and rooms from the database and convert to solver-friendly slots.
    
    Args:
        start_date: Only include reservations that overlap with this date or later.
        end_date: Only include reservations that overlap with this date or earlier.
    """
    from datetime import date as date_type
    import datetime as dt

    if start_date is None:
        start_date = date_type.today()
    if end_date is None:
        end_date = start_date + dt.timedelta(days=90)
    policy_constraints = policy_constraints or {}
    from app.models.allocation import ReservationAllocationLock
    from app.models.company import Company
    from app.models.guest_room_avoidance import GuestRoomAvoidance, GuestRoomAvoidanceStatusEnum
    from app.services.room_block_service import blocked_room_ids_for_range
    has_hotel_context = hotel_id is not None

    # Load active reservations in the window
    reservations_query = (
        active_reservations(db, hotel_id)
        if has_hotel_context
        else _active_reservations_without_hotel(db)
    ).filter(
        Reservation.status.notin_([
            ReservationStatusEnum.CANCELLED,
            ReservationStatusEnum.CHECKED_OUT,
        ]),
        Reservation.check_in_date < end_date,
        Reservation.check_out_date > start_date,
    )

    reservation_rows = reservations_query.all()
    reservation_ids = [reservation.id for reservation in reservation_rows]
    active_lock_ids: set[int] = set()
    if reservation_ids:
        active_lock_ids = {
            row.reservation_id
            for row in db.query(ReservationAllocationLock.reservation_id)
            .filter(
                ReservationAllocationLock.reservation_id.in_(reservation_ids),
                ReservationAllocationLock.is_active == True,
            )
            .all()
        }
    company_ids = {
        company_id
        for company_id in {getattr(reservation, "company_id", None) for reservation in reservation_rows}
        if company_id is not None
    }
    protected_company_ids: set[int] = set()
    if company_ids:
        company_query = db.query(Company).filter(Company.id.in_(company_ids))
        if has_hotel_context:
            company_query = company_query.filter(Company.hotel_id == hotel_id)
        protected_company_ids = {
            company.id
            for company in company_query.all()
            if bool(company.requires_signature or company.payment_deferred)
        }

    # Discover allowed categories intelligently
    from app.models.room import RoomCategory
    from app.models.commercial import ProductRoomCompatibility, SellableProduct
    all_cat_query = db.query(RoomCategory)
    if has_hotel_context:
        all_cat_query = all_cat_query.filter(RoomCategory.hotel_id == hotel_id)
    all_cat = all_cat_query.all()
    cat_map = {c.id: c for c in all_cat}
    compat_query = db.query(ProductRoomCompatibility).filter(ProductRoomCompatibility.allows_auto_assignment == True)
    if has_hotel_context:
        compat_query = compat_query.filter(ProductRoomCompatibility.hotel_id == hotel_id)
    compatibility_rows = compat_query.order_by(ProductRoomCompatibility.priority.asc()).all()
    allow_category_fallback = bool(policy_constraints.get("allow_category_fallback", True))
    compatibility_by_product: dict[int, list[ProductRoomCompatibility]] = {}
    for row in compatibility_rows:
        compatibility_by_product.setdefault(row.sellable_product_id, []).append(row)
    product_ids = {
        product_id
        for product_id in {
            getattr(reservation, "sellable_product_id", None)
            for reservation in reservation_rows
        }
        if product_id is not None
    }
    product_map: dict[int, SellableProduct] = {}
    if product_ids:
        product_query = db.query(SellableProduct).filter(SellableProduct.id.in_(product_ids))
        if has_hotel_context:
            product_query = product_query.filter(SellableProduct.hotel_id == hotel_id)
        product_map = {product.id: product for product in product_query.all()}

    # A single UNION ALL query batches both guest-room data sources for every
    # guest represented in the horizon. The slot loop below only reads these
    # in-memory maps, so allocation cannot turn returning guests into an N+1
    # query path.
    guest_ids = {reservation.guest_id for reservation in reservation_rows if reservation.guest_id is not None}
    avoided_room_ids_by_guest: dict[int, set[int]] = {}
    completed_stays_by_guest: dict[int, list[tuple[date, int, int, int]]] = {}
    if guest_ids:
        from sqlalchemy import Date, Integer, and_, literal

        avoidance_signal_query = db.query(
            GuestRoomAvoidance.guest_id,
            GuestRoomAvoidance.room_id,
            literal(None, type_=Date()).label("check_out_date"),
            literal(None, type_=Integer()).label("completed_reservation_id"),
            literal(None, type_=Integer()).label("room_category_id"),
            literal("avoidance").label("source"),
        ).filter(
            GuestRoomAvoidance.guest_id.in_(guest_ids),
            GuestRoomAvoidance.status == GuestRoomAvoidanceStatusEnum.ACTIVE,
        )
        if has_hotel_context:
            avoidance_signal_query = avoidance_signal_query.filter(GuestRoomAvoidance.hotel_id == hotel_id)

        historical_stay_signal_query = db.query(
            Reservation.guest_id,
            Reservation.room_id,
            Reservation.check_out_date,
            Reservation.id.label("completed_reservation_id"),
            Room.category_id.label("room_category_id"),
            literal("historical_stay").label("source"),
        ).join(
            Room,
            and_(Room.id == Reservation.room_id, Room.hotel_id == Reservation.hotel_id),
        ).filter(
            Reservation.guest_id.in_(guest_ids),
            Reservation.room_id.isnot(None),
            Reservation.status == ReservationStatusEnum.CHECKED_OUT,
        )
        if has_hotel_context:
            historical_stay_signal_query = historical_stay_signal_query.filter(Reservation.hotel_id == hotel_id)

        for guest_id, room_id, check_out_date, completed_reservation_id, room_category_id, source in (
            avoidance_signal_query.union_all(historical_stay_signal_query).all()
        ):
            if source == "avoidance":
                avoided_room_ids_by_guest.setdefault(guest_id, set()).add(room_id)
            elif check_out_date is not None:
                completed_stays_by_guest.setdefault(guest_id, []).append(
                    (check_out_date, completed_reservation_id, room_id, room_category_id)
                )

    reservation_slots = []
    for res in reservation_rows:
        req_cat = cat_map.get(res.category_id)
        allowed = [res.category_id]
        priority_by_category: dict[int, int] = {res.category_id: 0}

        sellable_product_id = getattr(res, "sellable_product_id", None)
        product = product_map.get(sellable_product_id)
        compat_rows = compatibility_by_product.get(sellable_product_id, [])
        if compat_rows:
            for row in compat_rows:
                if not allow_category_fallback and row.compatibility_kind != "exact":
                    continue
                if row.room_category_id not in allowed:
                    allowed.append(row.room_category_id)
                priority_by_category[row.room_category_id] = min(
                    priority_by_category.get(row.room_category_id, row.priority),
                    row.priority,
                )
        elif product and product.primary_room_category_id and product.primary_room_category_id not in allowed:
            # Keep the fallback model explicit: if no compatibility rows were configured
            # we only trust the product's declared primary category, never code heuristics.
            allowed.append(product.primary_room_category_id)
            priority_by_category[product.primary_room_category_id] = 0

        avoided_room_ids = avoided_room_ids_by_guest.get(res.guest_id, set())
        prior_stays = [
            stay
            for stay in completed_stays_by_guest.get(res.guest_id, [])
            if stay[0] <= res.check_in_date
        ]
        last_stay = max(prior_stays, default=None, key=lambda stay: (stay[0], stay[1]))
        prior_stay_room_id = (
            last_stay[2]
            if last_stay is not None
            and last_stay[3] == res.category_id
            and last_stay[2] not in avoided_room_ids
            else None
        )

        slot = ReservationSlot(
            reservation_id=res.id,
            category_id=res.category_id,
            check_in=res.check_in_date,
            check_out=res.check_out_date,
            current_room_id=res.room_id,
            is_locked=_is_protected_reservation(
                res,
                active_lock_ids=active_lock_ids,
                protected_company_ids=protected_company_ids,
            ),
            guest_id=res.guest_id,
            num_guests=max(1, int((res.num_adults or 0) + (res.num_children or 0))),
            mobility_restriction=bool(getattr(res, "mobility_restriction", False)),
            allowed_category_ids=allowed,
            category_priority_by_id=priority_by_category,
            prior_stay_room_id=prior_stay_room_id,
            avoided_room_ids=sorted(avoided_room_ids),
        )
        reservation_slots.append(slot)

    # Load all active rooms — EXCLUDE maintenance, blocked, but include CLEANING as it's a temporary state
    rooms_query = active_rooms(db, hotel_id).filter(
        Room.is_active == True,
        Room.status.in_([RoomStatusEnum.AVAILABLE, RoomStatusEnum.OCCUPIED, RoomStatusEnum.CLEANING]),
    )
    rooms = rooms_query.all()
    blocked_room_ids = (
        blocked_room_ids_for_range(db, hotel_id=hotel_id, start_date=start_date, end_date=end_date)
        if has_hotel_context
        else set()
    )

    room_slots = [
        RoomSlot(
            room_id=room.id,
            room_number=room.room_number,
            category_id=room.category_id,
            max_occupancy=max(1, int(getattr(room.category, "max_occupancy", 1) or 1)),
            floor=room.floor,
            score=room.score,
            is_accessible=bool(room.is_accessible),
        )
        for room in rooms
        if room.id not in blocked_room_ids
    ]

    return reservation_slots, room_slots


def _lowest_compatible_floor(reservation: ReservationSlot, rooms: list[RoomSlot]) -> int | None:
    floors = [
        room.floor
        for room in rooms
        if room.is_accessible and room.category_id in reservation.effective_allowed_category_ids
    ]
    return min(floors) if floors else None


def _lowest_available_compatible_floor(
    reservation: ReservationSlot,
    rooms: list[RoomSlot],
    reservations: list[ReservationSlot],
) -> int | None:
    locked_occupancy = [
        other
        for other in reservations
        if other.reservation_id != reservation.reservation_id
        and other.is_locked
        and other.current_room_id is not None
        and _check_overlap(reservation, other)
    ]
    available_rooms = []
    for room in rooms:
        if not room.is_accessible or room.category_id not in reservation.effective_allowed_category_ids:
            continue
        if any(other.current_room_id == room.room_id for other in locked_occupancy):
            continue
        available_rooms.append(room)
    return _lowest_compatible_floor(reservation, available_rooms)


def _is_protected_reservation(
    reservation: Reservation,
    *,
    active_lock_ids: set[int],
    protected_company_ids: set[int],
) -> bool:
    return bool(
        reservation.status in {ReservationStatusEnum.CHECKED_IN, ReservationStatusEnum.PRE_CHECK_IN}
        or getattr(reservation, "actual_check_in", None) is not None
        or getattr(reservation, "pre_check_in_at", None) is not None
        or getattr(reservation, "allocation_locked", False)
        or reservation.id in active_lock_ids
        or (
            getattr(reservation, "company_id", None) is not None
            and reservation.company_id in protected_company_ids
        )
    )
