"""
AllocationEngine — Intelligent Room Assignment using Google OR-Tools (CP-SAT Solver).

This is the core optimization module that:
1. Takes reservations and available rooms
2. Maximizes the number of booked nights that can be placed
3. Respects hard constraints (no overlap, category/capacity/accessibility, checked-in guests)
4. Uses room concentration, one-night gaps, assignment stability and guest-room preferences
   only as tie-breakers after the occupied-night objective

The solver uses a Constraint Programming (CP-SAT) model where:
- Decision variables: x[r, h] = 1 if reservation r is assigned to room h
- Hard constraints ensure feasibility
- The primary objective is booked nights, with room continuity as a secondary objective
"""
import time
from bisect import bisect_right
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Mapping, Optional

from sqlalchemy.orm import Session, lazyload, load_only

from app.models.allocation import ReservationAllocationLock
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.room import Room, RoomStatusEnum
from app.services.reservation_service import (
    _active_reservations_without_hotel,
    active_reservations,
)
from app.services.room_service import active_rooms


# CP-SAT stores objective bounds in signed 64-bit integers. Keep a margin so a
# large but valid database amount cannot overflow the solver's internal sum.
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
    is_locked: bool  # Checked-in or explicitly pinned; confirmed bookings may be proposed for moves.
    explicitly_locked: bool = False
    guest_id: Optional[int] = None
    company_id: Optional[int] = None
    channel_code: Optional[str] = None
    source: Optional[str] = None
    num_guests: int = 1
    mobility_restriction: bool = False
    allowed_category_ids: list[int] = field(default_factory=list)
    category_priority_by_id: dict[int, int] = field(default_factory=dict)
    prior_stay_room_id: Optional[int] = None
    avoided_room_ids: list[int] = field(default_factory=list)
    blocked_room_ids: list[int] = field(default_factory=list)

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
    allocation_priority_channel_groups: list[str] = field(default_factory=list)
    allocation_priority_company_ids: list[int] = field(default_factory=list)


def _reservation_indexes_by_horizon_day(
    reservations: list[ReservationSlot],
    horizon_start: date,
    total_days: int,
) -> list[list[int]]:
    """Index reservation coverage once, clipping to the half-open horizon."""
    reservations_by_day: list[list[int]] = [[] for _ in range(total_days)]
    for reservation_index, reservation in enumerate(reservations):
        first_day = max((reservation.check_in - horizon_start).days, 0)
        after_last_day = min((reservation.check_out - horizon_start).days, total_days)
        for day_index in range(first_day, after_last_day):
            reservations_by_day[day_index].append(reservation_index)
    return reservations_by_day


@dataclass
class AllocationResult:
    """Result of the allocation engine run."""
    success: bool
    assignments: dict[int, int] = field(default_factory=dict)  # reservation_id → room_id
    unassigned_reservations: list[int] = field(default_factory=list)
    moved_reservations: list[int] = field(default_factory=list)
    objective_value: float = 0.0
    error: Optional[str] = None
    primary_status: str = "not_run"
    tie_break_status: str = "not_run"


def _check_overlap(slot_a: ReservationSlot, slot_b: ReservationSlot) -> bool:
    """Check if two reservation slots overlap in time."""
    return slot_a.check_in < slot_b.check_out and slot_b.check_in < slot_a.check_out


def _overlapping_reservation_pairs(
    reservations: list[ReservationSlot],
) -> list[tuple[int, int]]:
    """Return each overlapping reservation-index pair once using a sweep line."""
    ordered = sorted(
        enumerate(reservations),
        key=lambda item: (item[1].check_in, item[1].check_out, item[0]),
    )
    active: list[tuple[int, ReservationSlot]] = []
    pairs: list[tuple[int, int]] = []

    for current_index, current in ordered:
        if current.check_out <= current.check_in:
            continue
        active = [
            (reservation_index, reservation)
            for reservation_index, reservation in active
            if reservation.check_out > current.check_in
        ]
        pairs.extend(
            (min(reservation_index, current_index), max(reservation_index, current_index))
            for reservation_index, _reservation in active
        )
        active.append((current_index, current))

    return pairs


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


def _reservation_channel_group(reservation: ReservationSlot) -> str | None:
    """Normalize persisted channel/source fields to an operator-facing group."""
    if reservation.company_id is not None:
        return "company"
    channel = (reservation.channel_code or "").casefold()
    source = (reservation.source or "").casefold()
    if channel in {"booking", "expedia", "despegar", "other_ota"} or source in {
        "booking", "expedia", "other_ota"
    }:
        return "ota"
    if channel == "company":
        return "company"
    if channel in {"website_direct", "whatsapp", "phone", "walk_in", "other_direct"} or source == "direct":
        return "direct"
    return None


def _allocation_source_preference_score(
    reservation: ReservationSlot,
    room: RoomSlot,
) -> int:
    """Score only explicit room preferences; unmatched and unknown are neutral."""
    score = 0
    if reservation.company_id is not None and reservation.company_id in room.allocation_priority_company_ids:
        score += 2
    channel_group = _reservation_channel_group(reservation)
    if channel_group and channel_group in room.allocation_priority_channel_groups:
        score += 1
    return score


def run_allocation(
    reservations: list[ReservationSlot],
    rooms: list[RoomSlot],
    optimization_horizon: Optional[tuple[date, date]] = None,
    policy_constraints: Optional[dict] = None,
    policy_weights: Optional[dict] = None,
    forbidden_room_ids_by_reservation: Optional[Mapping[int, set[int]]] = None,
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
        2. Room category, capacity and accessibility must be compatible
        3. No two reservations assigned to the same room can overlap in time
        4. Checked-in or explicitly pinned reservations stay in their current room
    
    Objective:
        First maximize total occupied reservation nights. Only after that primary
        value is fixed, prefer fewer used rooms, fewer one-night gaps, stable room
        assignments, exact category matches and configured guest-room signals.
        Pricing, FX rates, age and nationality are not allocation objectives.
        Room source preferences and lower-floor preference are separate final
        tie-break phases after room continuity and gap optimization.
    """
    if not reservations:
        return AllocationResult(success=True)

    policy_constraints = policy_constraints or {}
    policy_weights = policy_weights or {}
    combined_forbidden_room_ids: dict[int, set[int]] = {
        reservation_id: set(room_ids)
        for reservation_id, room_ids in (forbidden_room_ids_by_reservation or {}).items()
    }
    for reservation in reservations:
        if reservation.blocked_room_ids:
            combined_forbidden_room_ids.setdefault(reservation.reservation_id, set()).update(
                reservation.blocked_room_ids
            )
    forbidden_room_ids_by_reservation = combined_forbidden_room_ids
    objective_mode = str(policy_constraints.get("optimization_objective", "occupied_nights"))
    if objective_mode != "occupied_nights":
        return AllocationResult(
            success=False,
            error=(
                "Room allocation only supports occupied nights and room continuity; "
                "use rate recommendations for pricing decisions."
            ),
        )

    try:
        from ortools.sat.python import cp_model
    except ImportError:
        return _run_allocation_greedy(
            reservations,
            rooms,
            optimization_horizon,
            policy_constraints=policy_constraints,
            policy_weights=policy_weights,
            forbidden_room_ids_by_reservation=forbidden_room_ids_by_reservation,
        )

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
    def primary_objective_coefficient(reservation: ReservationSlot) -> int:
        return max(0, reservation.nights)

    model = cp_model.CpModel()

    # ── Compatible assignment candidates ──
    # Filter impossible room/reservation pairs before creating solver
    # variables. A typical hotel has several room categories, so a dense
    # reservation_count × room_count matrix creates many variables that are
    # immediately fixed to zero and still cost memory and presolve time.
    compatible_room_indexes_by_reservation: list[set[int]] = []
    candidate_reservations_by_room: list[list[int]] = [[] for _ in rooms]
    for r_idx, res in enumerate(reservations):
        compatible_room_indexes: set[int] = set()
        forbidden_room_ids = forbidden_room_ids_by_reservation.get(res.reservation_id, set())
        for h_idx, room in enumerate(rooms):
            if room.room_id in forbidden_room_ids:
                continue
            if room.category_id not in res.effective_allowed_category_ids:
                continue
            if room.max_occupancy < res.num_guests:
                continue
            if res.mobility_restriction and not room.is_accessible:
                continue
            compatible_room_indexes.add(h_idx)
            candidate_reservations_by_room[h_idx].append(r_idx)
        compatible_room_indexes_by_reservation.append(compatible_room_indexes)

    # x[r_idx, h_idx] = 1 only for candidates that pass hard eligibility.
    # Reuse a zero constant for impossible pairs instead of allocating a bool
    # variable and a forced-zero constraint for every one of them.
    zero = model.NewConstant(0)
    x = {
        (r_idx, h_idx): model.NewBoolVar(f"x_{r_idx}_{h_idx}")
        for r_idx, candidate_indexes in enumerate(compatible_room_indexes_by_reservation)
        for h_idx in sorted(candidate_indexes)
    }

    def assignment_var(r_idx: int, h_idx: int):
        return x.get((r_idx, h_idx), zero)

    # is_assigned[r_idx] = sum(x[r_idx, *])
    is_assigned = {}
    for r_idx in range(len(reservations)):
        is_assigned[r_idx] = model.NewBoolVar(f"assigned_{r_idx}")
        model.Add(
            sum(assignment_var(r_idx, h_idx) for h_idx in range(len(rooms)))
            == is_assigned[r_idx]
        )
        if reservations[r_idx].is_locked:
            model.Add(is_assigned[r_idx] == 1)

    # ── Hard Constraint 3: No temporal overlap on the same compatible room ──
    # Time overlap is independent of room. Compute each reservation pair once
    # instead of repeating the date comparison for every room, then omit rooms
    # that a hard category/capacity/mobility rule already excludes.
    for first_index, second_index in _overlapping_reservation_pairs(reservations):
        shared_room_indexes = (
            compatible_room_indexes_by_reservation[first_index]
            & compatible_room_indexes_by_reservation[second_index]
        )
        for h_idx in sorted(shared_room_indexes):
            model.Add(x[first_index, h_idx] + x[second_index, h_idx] <= 1)

    # ── Hard Constraint 4: Locked reservations stay in their current room ──
    for r_idx, res in enumerate(reservations):
        if res.is_locked and res.current_room_id is not None:
            for h_idx in sorted(compatible_room_indexes_by_reservation[r_idx]):
                room = rooms[h_idx]
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

    # Build occupancy indicators only for room/day combinations with at least
    # one eligible reservation. This avoids a dense horizon-sized model for
    # rooms and nights that no candidate can occupy.
    candidate_reservations_by_room_day: list[list[list[int]]] = [
        [[] for _ in range(total_days)] for _ in rooms
    ]
    for h_idx, reservation_indexes in enumerate(candidate_reservations_by_room):
        for r_idx in reservation_indexes:
            reservation = reservations[r_idx]
            first_day = max((reservation.check_in - horizon_start).days, 0)
            after_last_day = min((reservation.check_out - horizon_start).days, total_days)
            for day_index in range(first_day, after_last_day):
                candidate_reservations_by_room_day[h_idx][day_index].append(r_idx)

    is_occupied = {}
    for h_idx, reservations_by_day_for_room in enumerate(candidate_reservations_by_room_day):
        for d, covering in enumerate(reservations_by_day_for_room):
            if covering:
                is_occupied[h_idx, d] = model.NewBoolVar(f"occ_{h_idx}_{d}")
                model.AddMaxEquality(
                    is_occupied[h_idx, d],
                    [x[r_idx, h_idx] for r_idx in covering]
                )

    # Gap penalty: penalize day d if day d-1 and d+1 are occupied but d is not
    gap_penalties = []

    for h_idx, reservations_by_day_for_room in enumerate(candidate_reservations_by_room_day):
        occupied_candidate_days = {
            day_index
            for day_index, reservation_indexes in enumerate(reservations_by_day_for_room)
            if reservation_indexes
        }
        possible_gap_days = sorted(
            day_index
            for day_index in occupied_candidate_days
            if 0 < day_index < total_days - 1
            and day_index - 1 in occupied_candidate_days
            and day_index + 1 in occupied_candidate_days
        )
        for d in possible_gap_days:
            prev_occ = is_occupied[h_idx, d - 1]
            curr_occ = is_occupied.get((h_idx, d), zero)
            next_occ = is_occupied[h_idx, d + 1]
            if prev_occ is not None and next_occ is not None:
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
    primary_objective_score = []
    stability_bonus = []
    category_match_bonus = []
    fallback_penalties = []
    room_score_bonus = []
    prior_stay_room_bonus_terms = []
    guest_room_avoidance_penalty_terms = []
    allocation_source_preference_terms = []
    lower_floor_preference_terms = []
    rooms_by_id = {room.room_id: room for room in rooms}

    for r_idx, res in enumerate(reservations):
        current_room = rooms_by_id.get(res.current_room_id)
        current_room_is_compatible = bool(
            current_room
            and current_room.category_id in res.effective_allowed_category_ids
            and current_room.max_occupancy >= res.num_guests
            and (not res.mobility_restriction or current_room.is_accessible)
        )
        for h_idx in sorted(compatible_room_indexes_by_reservation[r_idx]):
            room = rooms[h_idx]
            primary_objective_score.append(
                (x[r_idx, h_idx], primary_objective_coefficient(res))
            )

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
            source_preference = _allocation_source_preference_score(res, room)
            if source_preference:
                allocation_source_preference_terms.append((x[r_idx, h_idx], source_preference))

        if res.mobility_restriction and policy_constraints.get("hotel_has_elevator") is False:
            compatible_floors = [
                rooms[h_idx].floor
                for h_idx in compatible_room_indexes_by_reservation[r_idx]
            ]
            highest_candidate_floor = max(compatible_floors, default=0)
            for h_idx in sorted(compatible_room_indexes_by_reservation[r_idx]):
                floor_bonus = highest_candidate_floor - rooms[h_idx].floor
                if floor_bonus > 0:
                    lower_floor_preference_terms.append((x[r_idx, h_idx], floor_bonus))

    # Concentration bonus: penalize spreading across many rooms
    # For each room, add penalty if it has any reservation (encourages packing)
    room_usage = {}
    for h_idx, reservation_indexes in enumerate(candidate_reservations_by_room):
        room_has_any = model.NewBoolVar(f"room_used_{h_idx}")
        assignments_to_room = [x[r_idx, h_idx] for r_idx in reservation_indexes]
        if assignments_to_room:
            model.AddMaxEquality(room_has_any, assignments_to_room)
        else:
            model.Add(room_has_any == 0)
        room_usage[h_idx] = room_has_any

    primary_objective = sum(var * coeff for var, coeff in primary_objective_score)
    assigned_count_objective = sum(is_assigned.values())
    tie_break_terms = [
        *stability_bonus,
        *prior_stay_room_bonus_terms,
        *category_match_bonus,
        *room_score_bonus,
        *((room_usage[h_idx], -room_usage_penalty) for h_idx in range(len(rooms))),
        *((var, -coeff) for var, coeff in fallback_penalties),
        *((var, -coeff) for var, coeff in guest_room_avoidance_penalty_terms),
        *((gap, -one_night_gap_penalty) for gap in gap_penalties),
    ]
    tie_break_objective = sum(var * coeff for var, coeff in tie_break_terms)
    allocation_source_preference_objective = sum(
        var * coeff for var, coeff in allocation_source_preference_terms
    )
    lower_floor_preference_objective = sum(
        var * coeff for var, coeff in lower_floor_preference_terms
    )

    # The hotel's configured goal always wins. Room continuity and gap rules are
    # resolved before source preferences, which are resolved before the optional
    # lower-floor preference for hotels that explicitly report no elevator.
    # Every phase shares one bounded budget.
    solve_started = time.monotonic()
    total_solve_seconds = 30.0

    def solve_with_remaining_budget():
        remaining = total_solve_seconds - (time.monotonic() - solve_started)
        if remaining <= 0.01:
            return None, None
        phase_solver = cp_model.CpSolver()
        phase_solver.parameters.max_time_in_seconds = remaining
        # Keep the solver bounded for small hotel instances and constrained hosts.
        phase_solver.parameters.num_workers = 1
        return phase_solver, phase_solver.Solve(model)

    model.Maximize(primary_objective)
    solver, status = solve_with_remaining_budget()
    if solver is None or status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        primary_status = solver.StatusName(status) if solver is not None else "UNKNOWN"
        return AllocationResult(
            success=False,
            error=f"Solver status: {primary_status}. No feasible assignment found.",
            primary_status=primary_status,
        )

    primary_status = solver.StatusName(status)
    tie_break_status = (
        "not_run_primary_not_proven"
        if status != cp_model.OPTIMAL
        else "not_run_budget"
    )
    selected_solver = solver
    if status == cp_model.OPTIMAL:
        best_primary_value = solver.Value(primary_objective)
        model.Add(primary_objective == best_primary_value)
        model.Maximize(assigned_count_objective)
        count_solver, count_status = solve_with_remaining_budget()
        if count_solver is not None and count_status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            selected_solver = count_solver
            tie_break_status = count_solver.StatusName(count_status)
            if count_status == cp_model.OPTIMAL:
                best_assigned_count = count_solver.Value(assigned_count_objective)
                model.Add(assigned_count_objective == best_assigned_count)
                model.Maximize(tie_break_objective)
                preference_solver, preference_status = solve_with_remaining_budget()
                if preference_solver is not None and preference_status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
                    selected_solver = preference_solver
                    tie_break_status = preference_solver.StatusName(preference_status)
                    if preference_status == cp_model.OPTIMAL:
                        best_tie_break_value = preference_solver.Value(tie_break_objective)
                        model.Add(tie_break_objective == best_tie_break_value)

                        if allocation_source_preference_terms:
                            model.Maximize(allocation_source_preference_objective)
                            source_solver, source_status = solve_with_remaining_budget()
                            if source_solver is not None and source_status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
                                selected_solver = source_solver
                                tie_break_status = source_solver.StatusName(source_status)
                                if source_status == cp_model.OPTIMAL:
                                    best_source_value = source_solver.Value(
                                        allocation_source_preference_objective
                                    )
                                    model.Add(
                                        allocation_source_preference_objective == best_source_value
                                    )

                        if lower_floor_preference_terms and tie_break_status == "OPTIMAL":
                            model.Maximize(lower_floor_preference_objective)
                            floor_solver, floor_status = solve_with_remaining_budget()
                            if floor_solver is not None and floor_status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
                                selected_solver = floor_solver
                                tie_break_status = floor_solver.StatusName(floor_status)

    if selected_solver is not None:
        assignments = {}
        unassigned = []
        moved = []
        for r_idx, res in enumerate(reservations):
            assigned = False
            for h_idx, room in enumerate(rooms):
                if selected_solver.Value(assignment_var(r_idx, h_idx)) == 1:
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
            objective_value=float(selected_solver.Value(primary_objective)),
            primary_status=primary_status,
            tie_break_status=tie_break_status,
        )
    else:
        return AllocationResult(
            success=False,
            error=f"Solver status: {solver.StatusName(status)}. No feasible assignment found.",
            primary_status=primary_status,
        )


def _run_allocation_greedy(
    reservations: list[ReservationSlot],
    rooms: list[RoomSlot],
    optimization_horizon: Optional[tuple[date, date]] = None,
    policy_constraints: Optional[dict] = None,
    policy_weights: Optional[dict] = None,
    forbidden_room_ids_by_reservation: Optional[Mapping[int, set[int]]] = None,
) -> AllocationResult:
    """
    Greedy fallback allocation when OR-Tools is not available.
    Simple first-fit approach respecting all hard constraints.
    """
    assignments: dict[int, int] = {}
    moved: list[int] = []
    policy_constraints = policy_constraints or {}
    policy_weights = policy_weights or {}
    forbidden_room_ids_by_reservation = forbidden_room_ids_by_reservation or {}
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

    def priority(reservation: ReservationSlot) -> int:
        return max(0, reservation.nights)

    # Sort reservations: locked first, then objective priority, then check-in.
    sorted_reservations = sorted(
        reservations,
        key=lambda r: (not r.is_locked, -priority(r), r.check_in, -r.nights),
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
            and room.room_id not in forbidden_room_ids_by_reservation.get(res.reservation_id, set())
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
                    -(r.score or 0),
                    -len(room_occupancy.get(r.room_id, [])),
                    -_allocation_source_preference_score(res, r),
                    r.floor
                    if res.mobility_restriction and policy_constraints.get("hotel_has_elevator") is False
                    else 0,
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
                    -(r.score or 0),
                    -len(room_occupancy.get(r.room_id, [])),
                    -_allocation_source_preference_score(res, r),
                    r.floor
                    if res.mobility_restriction and policy_constraints.get("hotel_has_elevator") is False
                    else 0,
                ),
            )

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
                break

    unassigned = list(set(r.reservation_id for r in reservations) - set(assignments.keys()))
    return AllocationResult(
        success=len(unassigned) == 0,
        assignments=assignments,
        unassigned_reservations=unassigned,
        moved_reservations=moved,
        primary_status="HEURISTIC",
        tie_break_status="HEURISTIC",
    )


def apply_allocation_result(
    db: Session,
    result: AllocationResult,
    hotel_id: Optional[int] = None,
    *,
    trigger_reason: str = "allocation_recalculate",
    trigger_event: Optional[str] = None,
    created_by_user_id: Optional[int] = None,
    reservations_by_id: Optional[Mapping[int, Reservation]] = None,
    one_time_locked_move_approvals: set[int] | None = None,
) -> list[Reservation]:
    """
    Apply the solver's assignments to the database.
    Updates room_id on each reservation.
    """
    if result.error:
        raise AllocationError(result.error)

    from app.models.operations import RoomMoveEvent, RoomMovementGroup, RoomMoveTypeEnum

    updated = []
    pending_moves: list[tuple[Reservation, int, int | None]] = []
    reservation_ids = set(result.assignments)
    if reservations_by_id is None:
        reservation_query = (
            active_reservations(db, hotel_id)
            if hotel_id is not None
            else _active_reservations_without_hotel(db)
        )
        reservations_by_id = (
            {
                reservation.id: reservation
                for reservation in reservation_query.filter(
                    Reservation.id.in_(reservation_ids)
                ).all()
            }
            if reservation_ids
            else {}
        )

    from app.models.allocation import ReservationAllocationLock

    active_lock_query = db.query(ReservationAllocationLock.reservation_id).filter(
        ReservationAllocationLock.is_active.is_(True),
        ReservationAllocationLock.reservation_id.in_(result.assignments),
    )
    if hotel_id is not None:
        active_lock_query = active_lock_query.filter(
            ReservationAllocationLock.hotel_id == hotel_id
        )
    active_lock_ids = {row[0] for row in active_lock_query.all()}
    one_time_locked_move_approvals = one_time_locked_move_approvals or set()
    candidate_moves: list[tuple[Reservation, int, int | None]] = []
    for reservation_id, room_id in result.assignments.items():
        reservation = reservations_by_id.get(reservation_id)
        if (
            reservation is not None
            and getattr(reservation, "deleted_at", None) is None
            and (hotel_id is None or getattr(reservation, "hotel_id", None) == hotel_id)
        ):
            previous_room_id = reservation.room_id
            if previous_room_id != room_id:
                status_value = (
                    reservation.status.value
                    if hasattr(reservation.status, "value")
                    else str(reservation.status)
                )
                if (
                    status_value in {
                        ReservationStatusEnum.PARTIAL_CHECK_IN.value,
                        ReservationStatusEnum.CHECKED_IN.value,
                    }
                    or getattr(reservation, "actual_check_in", None) is not None
                    or (
                        (
                            bool(getattr(reservation, "allocation_locked", False))
                            or reservation.id in active_lock_ids
                        )
                        and reservation.id not in one_time_locked_move_approvals
                    )
                ):
                    raise AllocationError(
                        f"Reservation {reservation.id} is checked in or explicitly protected from reassignment"
                    )
                candidate_moves.append((reservation, room_id, previous_room_id))
            updated.append(reservation)

    # Validate every proposed mutation before changing any ORM entity. The caller
    # can therefore preserve the whole transaction if a single protected stay is
    # included in a forged or stale AllocationResult.
    for reservation, room_id, previous_room_id in candidate_moves:
        reservation.room_id = room_id
        pending_moves.append((reservation, room_id, previous_room_id))

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
    policy_weights: Optional[dict] = None,
    allow_locked_moves_for_review: bool = False,
) -> tuple[list[ReservationSlot], list[RoomSlot]]:
    """
    Load reservations and rooms from the database and convert to solver-friendly slots.
    
    Args:
        start_date: Only include reservations that overlap with this date or later.
        end_date: Only include reservations that overlap with this date or earlier.
    """
    import datetime as dt
    from datetime import date as date_type

    if start_date is None:
        start_date = date_type.today()
    if end_date is None:
        end_date = start_date + dt.timedelta(days=90)
    policy_constraints = policy_constraints or {}
    if hotel_id is not None:
        from app.models.hotel_config import HotelConfiguration

        # Unknown remains unknown: only an explicit false enables the optional
        # lower-floor preference for a guest with a mobility restriction.
        policy_constraints["hotel_has_elevator"] = (
            db.query(HotelConfiguration.has_elevator)
            .filter(HotelConfiguration.id == hotel_id)
            .scalar()
        )
    from app.models.guest_room_avoidance import (
        GuestRoomAvoidance,
        GuestRoomAvoidanceStatusEnum,
    )
    from app.models.room_block import RoomBlock
    has_hotel_context = hotel_id is not None

    # Load active reservations in the window
    reservations_query = (
        active_reservations(db, hotel_id)
        if has_hotel_context
        else _active_reservations_without_hotel(db)
    ).options(
        lazyload("*"),
        load_only(
            Reservation.id,
            Reservation.hotel_id,
            Reservation.status,
            Reservation.company_id,
            Reservation.channel_code,
            Reservation.source,
            Reservation.category_id,
            Reservation.check_in_date,
            Reservation.check_out_date,
            Reservation.room_id,
            Reservation.guest_id,
            Reservation.num_adults,
            Reservation.num_children,
            Reservation.mobility_restriction,
            Reservation.sellable_product_id,
            Reservation.actual_check_in,
            Reservation.pre_check_in_at,
            Reservation.allocation_locked,
        ),
    ).filter(
        Reservation.status.notin_([
            ReservationStatusEnum.CANCELLED,
            ReservationStatusEnum.CHECKED_OUT,
        ]),
        Reservation.check_in_date < end_date,
        Reservation.check_out_date > start_date,
    )

    # Select scalar columns instead of Reservation entities. Entity loading
    # applies mapper-level eager joins/select-in loaders for guest, room,
    # transactions and additional guests, none of which the solver uses.
    reservation_rows = reservations_query.with_entities(
        Reservation.id,
        Reservation.hotel_id,
        Reservation.category_id,
        Reservation.sellable_product_id,
        Reservation.guest_id,
        Reservation.check_in_date,
        Reservation.check_out_date,
        Reservation.room_id,
        Reservation.status,
        Reservation.num_adults,
        Reservation.num_children,
        Reservation.company_id,
        Reservation.channel_code,
        Reservation.source,
        Reservation.actual_check_in,
        Reservation.pre_check_in_at,
        Reservation.allocation_locked,
        Reservation.mobility_restriction,
    ).all()
    reservation_ids = [reservation.id for reservation in reservation_rows]
    active_lock_ids: set[int] = set()
    if reservation_ids:
        active_lock_query = db.query(ReservationAllocationLock.reservation_id).filter(
            ReservationAllocationLock.reservation_id.in_(reservation_ids),
            ReservationAllocationLock.is_active.is_(True),
        )
        if has_hotel_context:
            active_lock_query = active_lock_query.filter(
                ReservationAllocationLock.hotel_id == hotel_id
            )
        active_lock_ids = {row.reservation_id for row in active_lock_query.all()}
    # Discover allowed categories intelligently
    from app.models.commercial import ProductRoomCompatibility, SellableProduct
    from app.models.room import RoomCategory

    compat_query = db.query(ProductRoomCompatibility).options(
        lazyload("*"),
        load_only(
            ProductRoomCompatibility.sellable_product_id,
            ProductRoomCompatibility.room_category_id,
            ProductRoomCompatibility.priority,
            ProductRoomCompatibility.compatibility_kind,
        ),
    ).filter(ProductRoomCompatibility.allows_auto_assignment.is_(True))
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
    product_map: dict[int, int | None] = {}
    if product_ids:
        product_query = db.query(
            SellableProduct.id,
            SellableProduct.primary_room_category_id,
        ).filter(SellableProduct.id.in_(product_ids))
        if has_hotel_context:
            product_query = product_query.filter(SellableProduct.hotel_id == hotel_id)
        product_map = {
            product_id: primary_category_id
            for product_id, primary_category_id in product_query.all()
        }

    # A single UNION ALL query batches both guest-room data sources for every
    # guest represented in the horizon. The slot loop below only reads these
    # in-memory maps, so allocation cannot turn returning guests into an N+1
    # query path.
    guest_ids = {reservation.guest_id for reservation in reservation_rows if reservation.guest_id is not None}
    avoided_room_ids_by_guest: dict[int, set[int]] = {}
    completed_stays_by_guest: dict[int, list[tuple[date, int, int, int]]] = {}
    completed_stay_keys_by_guest: dict[int, list[tuple[date, int]]] = {}
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
            Reservation.check_out_date < end_date,
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
        for guest_id, stays in completed_stays_by_guest.items():
            stays.sort(key=lambda stay: (stay[0], stay[1]))
            completed_stay_keys_by_guest[guest_id] = [
                (stay[0], stay[1]) for stay in stays
            ]

    reservation_slots = []
    for res in reservation_rows:
        allowed = [res.category_id]
        priority_by_category: dict[int, int] = {res.category_id: 0}

        sellable_product_id = getattr(res, "sellable_product_id", None)
        primary_room_category_id = product_map.get(sellable_product_id)
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
        elif primary_room_category_id and primary_room_category_id not in allowed:
            # Keep the fallback model explicit: if no compatibility rows were configured
            # we only trust the product's declared primary category, never code heuristics.
            allowed.append(primary_room_category_id)
            priority_by_category[primary_room_category_id] = 0

        avoided_room_ids = avoided_room_ids_by_guest.get(res.guest_id, set())
        guest_stays = completed_stays_by_guest.get(res.guest_id, [])
        guest_stay_keys = completed_stay_keys_by_guest.get(res.guest_id, [])
        prior_stay_index = bisect_right(
            guest_stay_keys,
            (res.check_in_date, float("inf")),
        ) - 1
        last_stay = guest_stays[prior_stay_index] if prior_stay_index >= 0 else None
        prior_stay_room_id = (
            last_stay[2]
            if last_stay is not None
            and last_stay[3] == res.category_id
            and last_stay[2] not in avoided_room_ids
            else None
        )

        has_physical_checkin = bool(
            res.status in {
                ReservationStatusEnum.PARTIAL_CHECK_IN,
                ReservationStatusEnum.CHECKED_IN,
            }
            or res.actual_check_in is not None
        )
        explicitly_locked = bool(res.allocation_locked or res.id in active_lock_ids)
        slot = ReservationSlot(
            reservation_id=res.id,
            category_id=res.category_id,
            check_in=res.check_in_date,
            check_out=res.check_out_date,
            current_room_id=res.room_id,
            is_locked=has_physical_checkin or (explicitly_locked and not allow_locked_moves_for_review),
            explicitly_locked=explicitly_locked,
            guest_id=res.guest_id,
            company_id=res.company_id,
            channel_code=getattr(res.channel_code, "value", res.channel_code),
            source=getattr(res.source, "value", res.source),
            num_guests=max(1, int((res.num_adults or 0) + (res.num_children or 0))),
            mobility_restriction=bool(getattr(res, "mobility_restriction", False)),
            allowed_category_ids=allowed,
            category_priority_by_id=priority_by_category,
            prior_stay_room_id=prior_stay_room_id,
            avoided_room_ids=sorted(avoided_room_ids),
        )
        reservation_slots.append(slot)

    if has_hotel_context:
        active_block_rows = (
            db.query(RoomBlock.room_id, RoomBlock.starts_at, RoomBlock.ends_at)
            .filter(
                RoomBlock.hotel_id == hotel_id,
                RoomBlock.resolved_at.is_(None),
                RoomBlock.starts_at < end_date,
                (RoomBlock.ends_at.is_(None) | (RoomBlock.ends_at > start_date)),
            )
            .all()
        )
        for slot in reservation_slots:
            slot.blocked_room_ids = sorted(
                {
                    room_id
                    for room_id, block_start, block_end in active_block_rows
                    if block_start < slot.check_out
                    and (block_end is None or block_end > slot.check_in)
                }
            )

    # Keep rooms with blocks in the solver; a block excludes that room only
    # for reservations whose stay overlaps the block's half-open date range.
    rooms_query = active_rooms(db, hotel_id).filter(
        Room.is_active == True,
        Room.status.in_([RoomStatusEnum.AVAILABLE, RoomStatusEnum.OCCUPIED, RoomStatusEnum.CLEANING]),
    )
    rooms = (
        rooms_query.with_entities(
            Room.id,
            Room.room_number,
            Room.category_id,
            Room.floor,
            Room.score,
            Room.is_accessible,
            Room.allocation_priority_channel_groups,
            Room.allocation_priority_company_ids,
            RoomCategory.max_occupancy,
        )
        .outerjoin(
            RoomCategory,
            (RoomCategory.id == Room.category_id)
            & (RoomCategory.hotel_id == Room.hotel_id),
        )
        .all()
    )
    room_slots = [
        RoomSlot(
            room_id=room_id,
            room_number=room_number,
            category_id=category_id,
            max_occupancy=max(1, int(max_occupancy or 1)),
            floor=floor,
            score=score,
            is_accessible=bool(is_accessible),
            allocation_priority_channel_groups=list(priority_channel_groups or []),
            allocation_priority_company_ids=[int(company_id) for company_id in (priority_company_ids or [])],
        )
        for (
            room_id,
            room_number,
            category_id,
            floor,
            score,
            is_accessible,
            priority_channel_groups,
            priority_company_ids,
            max_occupancy,
        ) in rooms
    ]

    return reservation_slots, room_slots
