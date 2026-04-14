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
from app.models.reservation import Reservation, ReservationStatusEnum


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
    allowed_category_ids: list[int] = field(default_factory=list)
    category_priority_by_id: dict[int, int] = field(default_factory=dict)

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
        for h_idx, room in enumerate(rooms):
            if room.category_id not in res.effective_allowed_category_ids:
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
            horizon_start = date.today()
            horizon_end = date.today() + timedelta(days=30)

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

    for r_idx, res in enumerate(reservations):
        for h_idx, room in enumerate(rooms):
            # Occupancy contribution: each night assigned to a room adds to score
            occupancy_score.append((x[r_idx, h_idx], res.nights))

            # Stability: prefer keeping reservation in current room (if one exists)
            if res.current_room_id == room.room_id and not res.is_locked:
                stability_bonus.append((x[r_idx, h_idx], stability_weight))

            # Category match bonus: heavily penalize upgrading if original category is available
            if room.category_id == res.category_id:
                category_match_bonus.append((x[r_idx, h_idx], exact_match_weight))
            else:
                fallback_penalties.append(
                    (x[r_idx, h_idx], res.category_priority(room.category_id) * fallback_priority_penalty)
                )

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
        + sum(var * coeff for var, coeff in category_match_bonus)
        - sum(room_usage[h_idx] * room_usage_penalty for h_idx in range(len(rooms)))
        - sum(var * coeff for var, coeff in fallback_penalties)
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

    # Group rooms by category
    rooms_by_category: dict[int, list[RoomSlot]] = {}
    for room in rooms:
        rooms_by_category.setdefault(room.category_id, []).append(room)

    # Track room occupancy: room_id → list of (check_in, check_out)
    room_occupancy: dict[int, list[tuple[date, date]]] = {r.room_id: [] for r in rooms}

    # Sort reservations: locked first, then by check-in date, then by length (longer first)
    sorted_reservations = sorted(
        reservations,
        key=lambda r: (not r.is_locked, r.check_in, -r.nights),
    )

    for res in sorted_reservations:
        # If locked, assign to current room
        if res.is_locked and res.current_room_id is not None:
            assignments[res.reservation_id] = res.current_room_id
            room_occupancy[res.current_room_id].append((res.check_in, res.check_out))
            continue

        # Find available rooms from all allowed categories
        candidate_rooms = []
        for cat_id in res.effective_allowed_category_ids:
            candidate_rooms.extend(rooms_by_category.get(cat_id, []))

        # Prefer current room for stability, then exact category match, then rooms partially occupied
        if res.current_room_id is not None:
            current_first = sorted(
                candidate_rooms,
                key=lambda r: (
                    0 if r.category_id == res.category_id else 1,
                    _one_night_gap_penalty_for_room(res, room_occupancy.get(r.room_id, [])),
                    -_adjacency_bonus_for_room(res, room_occupancy.get(r.room_id, [])),
                    0 if r.room_id == res.current_room_id else 1,
                    res.category_priority(r.category_id),
                    -len(room_occupancy.get(r.room_id, [])),
                ),
            )
        else:
            # Prefer exact category match
            current_first = sorted(
                candidate_rooms,
                key=lambda r: (
                    0 if r.category_id == res.category_id else 1,
                    _one_night_gap_penalty_for_room(res, room_occupancy.get(r.room_id, [])),
                    -_adjacency_bonus_for_room(res, room_occupancy.get(r.room_id, [])),
                    res.category_priority(r.category_id),
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
) -> list[Reservation]:
    """
    Apply the solver's assignments to the database.
    Updates room_id on each reservation.
    """
    if result.error:
        raise AllocationError(result.error)

    updated = []
    for reservation_id, room_id in result.assignments.items():
        reservation = db.query(Reservation).filter(Reservation.id == reservation_id).first()
        if reservation and (hotel_id is None or getattr(reservation, "hotel_id", None) == hotel_id):
            reservation.room_id = room_id
            updated.append(reservation)
            
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

    # Load active reservations in the window
    reservations_query = db.query(Reservation).filter(
        Reservation.status.notin_([
            ReservationStatusEnum.CANCELLED,
            ReservationStatusEnum.CHECKED_OUT,
        ]),
        Reservation.check_in_date < end_date,
        Reservation.check_out_date > start_date,
    )
    if hotel_id is not None:
        reservations_query = reservations_query.filter(Reservation.hotel_id == hotel_id)

    reservation_rows = reservations_query.all()

    # Discover allowed categories intelligently
    from app.models.room import RoomCategory
    from app.models.commercial import ProductRoomCompatibility, SellableProduct
    all_cat_query = db.query(RoomCategory)
    if hotel_id is not None:
        all_cat_query = all_cat_query.filter(RoomCategory.hotel_id == hotel_id)
    all_cat = all_cat_query.all()
    cat_map = {c.id: c for c in all_cat}
    compat_query = db.query(ProductRoomCompatibility).filter(ProductRoomCompatibility.allows_auto_assignment == True)
    if hotel_id is not None:
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
        if hotel_id is not None:
            product_query = product_query.filter(SellableProduct.hotel_id == hotel_id)
        product_map = {product.id: product for product in product_query.all()}

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

        slot = ReservationSlot(
            reservation_id=res.id,
            category_id=res.category_id,
            check_in=res.check_in_date,
            check_out=res.check_out_date,
            current_room_id=res.room_id,
            is_locked=(res.status == ReservationStatusEnum.CHECKED_IN or getattr(res, "allocation_locked", False)),
            allowed_category_ids=allowed,
            category_priority_by_id=priority_by_category,
        )
        reservation_slots.append(slot)

    # Load all active rooms — EXCLUDE maintenance, blocked, but include CLEANING as it's a temporary state
    rooms_query = db.query(Room).filter(
        Room.is_active == True,
        Room.status.in_([RoomStatusEnum.AVAILABLE, RoomStatusEnum.OCCUPIED, RoomStatusEnum.CLEANING]),
    )
    if hotel_id is not None:
        rooms_query = rooms_query.filter(Room.hotel_id == hotel_id)
    rooms = rooms_query.all()

    room_slots = [
        RoomSlot(
            room_id=room.id,
            room_number=room.room_number,
            category_id=room.category_id,
        )
        for room in rooms
    ]

    return reservation_slots, room_slots
