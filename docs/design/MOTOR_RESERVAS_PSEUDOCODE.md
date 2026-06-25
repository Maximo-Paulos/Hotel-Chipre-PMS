# Motor de Reservas — Pseudocódigo Detallado y Estructuras Auxiliares

## 1. Estructuras de Datos Clave

### 1.1 ReservationSlot (para CP-SAT)

```python
@dataclass
class ReservationSlot:
    """Lightweight representation of a reservation for the solver."""
    
    # Identidad
    reservation_id: int
    hotel_id: int
    
    # Dimensión temporal
    check_in: date
    check_out: date
    nights: int  # propiedad derivada
    date_range: set[date]  # propiedad derivada
    
    # Asignación actual
    current_room_id: Optional[int]
    category_id: int  # Categoría solicitada
    
    # Restricciones de movimiento
    is_locked: bool  # True si checked_in (no puede moverse)
    allocation_locked: bool  # True si manually locked
    
    # Flexibilidad comercial
    allowed_category_ids: list[int]  # Upgrades permitidos
    category_priority_by_id: dict[int, int]  # Prioridad de cada upgrade
    
    # Metadata
    guest_id: int
    source: ReservationSourceEnum  # "direct" | "booking" | "expedia"
    status: ReservationStatusEnum
    
    def effective_allowed_category_ids(self) -> list[int]:
        """Return upgrade list; fallback to [category_id]."""
        return self.allowed_category_ids if self.allowed_category_ids else [self.category_id]
    
    def category_priority(self, cat_id: int) -> int:
        """Lower = more preferred. 0 for exact match."""
        if cat_id == self.category_id:
            return 0
        return self.category_priority_by_id.get(cat_id, 10_000)
    
    @property
    def nights(self) -> int:
        return (self.check_out - self.check_in).days
    
    @property
    def date_range(self) -> set[date]:
        """Occupancy set: check_in to check_out-1."""
        return {
            self.check_in + timedelta(days=d)
            for d in range(self.nights)
        }
```

### 1.2 RoomSlot (para CP-SAT)

```python
@dataclass
class RoomSlot:
    """Lightweight representation of a room for the solver."""
    
    # Identidad
    room_id: int
    hotel_id: int
    room_number: str  # e.g., "101", "202A"
    
    # Capacidad
    category_id: int
    num_beds: int
    max_occupancy: int
    
    # Estado actual
    status: RoomStatusEnum  # "available" | "occupied" | "maintenance"
    current_occupancy: list[tuple[date, date]]  # Estancias ya asignadas
    
    def overlaps_with(self, check_in: date, check_out: date) -> bool:
        """Check if proposed stay overlaps with current occupancy."""
        for stay_in, stay_out in self.current_occupancy:
            if check_in < stay_out and stay_in < check_out:
                return True
        return False
```

### 1.3 AllocationResult (salida del solver)

```python
@dataclass
class AllocationResult:
    """Result of allocation optimization."""
    
    # Éxito general
    success: bool
    
    # Asignaciones propuestas
    assignments: dict[int, int]  # reservation_id → room_id
    
    # Cambios detectados
    moved_reservations: list[int]  # IDs de reservas que se movieron
    unassigned_reservations: list[int]  # IDs que no pudieron asignarse
    
    # Calidad de la solución
    objective_value: float  # Valor de la función objetivo (minimización)
    optimality_gap: float  # % gap de optimalidad (0 = óptimo)
    
    # Timing
    solver_wall_time_ms: int
    solver_status: str  # "OPTIMAL" | "FEASIBLE" | "INFEASIBLE" | "UNKNOWN"
    
    # Explicaciones por reserva
    reasoning: dict[int, str]  # reservation_id → "por qué asignada/no asignada"
    
    # Metadata
    error: Optional[str]  # Mensaje si success=False
    constraint_violations: list[str]  # Violaciones (para debugging)
```

### 1.4 RoomMoveIntent (solicitud de movimiento)

```python
@dataclass
class RoomMoveIntent:
    """Request to move a reservation to a different room."""
    
    reservation_id: int
    from_room_id: Optional[int]
    to_room_id: int
    
    move_type: RoomMoveTypeEnum  # MANUAL, OPTIMIZATION, UPGRADE, etc.
    reason_code: Optional[str]  # "guest_request", "damage", "upgrade_offer"
    notes: Optional[str]
    
    moved_by_user_id: Optional[int]
    
    # Para auditoría
    proposed_at: datetime = field(default_factory=datetime.now)
    
    def is_valid_move(self, room_before: Room, room_after: Room) -> bool:
        """Perform basic structural validation."""
        if room_before.room_id == room_after.room_id:
            return False  # No move needed
        if room_before.hotel_id != room_after.hotel_id:
            return False  # Cross-hotel move invalid
        return True
```

---

## 2. Algoritmo CP-SAT — Pseudocódigo Completo

### 2.1 Función Principal (run_allocation)

```python
def run_allocation(
    reservations: list[ReservationSlot],
    rooms: list[RoomSlot],
    optimization_horizon: Optional[tuple[date, date]] = None,
    policy_constraints: Optional[dict] = None,
    policy_weights: Optional[dict] = None,
    max_solver_time_seconds: int = 30,
    log_level: str = "INFO"
) → AllocationResult:
    """
    Solve the room-to-reservation assignment problem using CP-SAT.
    
    Parameters:
        reservations: List of ReservationSlot objects to assign
        rooms: List of RoomSlot objects (available rooms)
        optimization_horizon: Date range for gap penalty calculation
        policy_constraints: Hard constraint parameters
        policy_weights: Objective function weights
        max_solver_time_seconds: Timeout for solver
        log_level: Logging verbosity
    
    Returns:
        AllocationResult with assignments and diagnostics
    """
    
    logger = get_logger(__name__, level=log_level)
    
    # ═══════════════════════════════════════════════════════════════
    # EARLY EXITS AND VALIDATION
    # ═══════════════════════════════════════════════════════════════
    
    if not reservations:
        logger.info("No reservations to allocate; returning empty result")
        return AllocationResult(
            success=True,
            assignments={},
            moved_reservations=[],
            unassigned_reservations=[],
            objective_value=0.0,
            solver_status="EMPTY"
        )
    
    if not rooms:
        logger.warning(f"No rooms available; {len(reservations)} unassigned")
        return AllocationResult(
            success=False,
            assignments={},
            unassigned_reservations=[r.reservation_id for r in reservations],
            error="No available rooms"
        )
    
    # ═══════════════════════════════════════════════════════════════
    # LOAD SOLVER LIBRARY
    # ═══════════════════════════════════════════════════════════════
    
    try:
        from ortools.sat.python import cp_model
    except ImportError:
        logger.warning("OR-Tools not installed; falling back to greedy algorithm")
        return _run_allocation_greedy(
            reservations, rooms,
            optimization_horizon=optimization_horizon,
            policy_constraints=policy_constraints,
            policy_weights=policy_weights
        )
    
    # ═══════════════════════════════════════════════════════════════
    # EXTRACT POLICY PARAMETERS WITH DEFAULTS
    # ═══════════════════════════════════════════════════════════════
    
    policy_constraints = policy_constraints or {}
    policy_weights = policy_weights or {}
    
    w_gap = int(policy_weights.get("minimize_one_night_gaps", 100))
    w_stability = int(policy_weights.get("stability", 5))
    w_category = int(policy_weights.get("prefer_exact_match", 500))
    w_unassigned = int(policy_weights.get("unassigned_penalty", 10_000))
    w_room_usage = int(policy_weights.get("room_usage_penalty", 50))
    max_category_upgrades = int(policy_constraints.get("max_category_upgrades", 999))
    
    logger.debug(f"Policy weights: gap={w_gap}, stability={w_stability}, "
                 f"category={w_category}, unassigned={w_unassigned}")
    
    # ═══════════════════════════════════════════════════════════════
    # COMPUTE OPTIMIZATION HORIZON
    # ═══════════════════════════════════════════════════════════════
    
    if optimization_horizon:
        horizon_start, horizon_end = optimization_horizon
    else:
        # Auto-compute from reservations
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
    
    logger.info(f"Optimization horizon: {horizon_start} to {horizon_end} "
                f"({total_days} days)")
    
    # ═══════════════════════════════════════════════════════════════
    # CREATE CP-SAT MODEL
    # ═══════════════════════════════════════════════════════════════
    
    model = cp_model.CpModel()
    
    logger.debug(f"Creating model with {len(reservations)} reservations "
                 f"and {len(rooms)} rooms")
    
    # ═══════════════════════════════════════════════════════════════
    # DECISION VARIABLES: x[r, h] ∈ {0, 1}
    # ═══════════════════════════════════════════════════════════════
    
    x = {}
    for r_idx in range(len(reservations)):
        for h_idx in range(len(rooms)):
            x[r_idx, h_idx] = model.NewBoolVar(f"x_{r_idx}_{h_idx}")
    
    # ═══════════════════════════════════════════════════════════════
    # AUXILIARY VARIABLES: is_assigned[r]
    # ═══════════════════════════════════════════════════════════════
    
    is_assigned = {}
    for r_idx in range(len(reservations)):
        is_assigned[r_idx] = model.NewBoolVar(f"assigned_{r_idx}")
    
    # Link: is_assigned[r] = 1 iff Σ_h x[r, h] ≥ 1
    for r_idx in range(len(reservations)):
        model.Add(
            sum(x[r_idx, h_idx] for h_idx in range(len(rooms))) == is_assigned[r_idx]
        )
    
    # ═══════════════════════════════════════════════════════════════
    # HARD CONSTRAINT 1: Locked reservations stay in current room
    # ═══════════════════════════════════════════════════════════════
    
    for r_idx, res in enumerate(reservations):
        if res.is_locked and res.current_room_id is not None:
            matched = False
            for h_idx, room in enumerate(rooms):
                if room.room_id == res.current_room_id:
                    model.Add(x[r_idx, h_idx] == 1)
                    model.Add(is_assigned[r_idx] == 1)
                    matched = True
                    logger.debug(f"Reservation {res.reservation_id} is locked "
                                 f"in room {room.room_number}")
                else:
                    model.Add(x[r_idx, h_idx] == 0)
            
            if not matched:
                # Current room not in available rooms; mark as infeasible
                logger.warning(f"Locked reservation {res.reservation_id} "
                               f"(room {res.current_room_id}) not in room list")
                model.Add(is_assigned[r_idx] == 0)  # Force unassigned
    
    # ═══════════════════════════════════════════════════════════════
    # HARD CONSTRAINT 2: Category matching
    # ═══════════════════════════════════════════════════════════════
    
    disallowed_pairs = 0
    for r_idx, res in enumerate(reservations):
        allowed_cats = res.effective_allowed_category_ids()
        for h_idx, room in enumerate(rooms):
            if room.category_id not in allowed_cats:
                model.Add(x[r_idx, h_idx] == 0)
                disallowed_pairs += 1
    
    logger.debug(f"Category constraints: {disallowed_pairs} disallowed pairs")
    
    # ═══════════════════════════════════════════════════════════════
    # HARD CONSTRAINT 3: Temporal non-overlap
    # ═══════════════════════════════════════════════════════════════
    
    overlap_constraints = 0
    for h_idx in range(len(rooms)):
        for r1_idx in range(len(reservations)):
            for r2_idx in range(r1_idx + 1, len(reservations)):
                res1 = reservations[r1_idx]
                res2 = reservations[r2_idx]
                
                # Check if time windows overlap
                if res1.check_in < res2.check_out and res2.check_in < res1.check_out:
                    # Overlapping: at most one can be assigned to room h
                    model.Add(x[r1_idx, h_idx] + x[r2_idx, h_idx] <= 1)
                    overlap_constraints += 1
    
    logger.debug(f"Temporal constraints: {overlap_constraints} overlap pairs")
    
    # ═══════════════════════════════════════════════════════════════
    # SOFT CONSTRAINT 1: Occupancy indicators for gap detection
    # ═══════════════════════════════════════════════════════════════
    
    is_occupied = {}
    for h_idx in range(len(rooms)):
        for day_offset in range(total_days):
            current_date = horizon_start + timedelta(days=day_offset)
            
            # Find reservations covering this date
            covering_reservations = [
                r_idx for r_idx, res in enumerate(reservations)
                if current_date in res.date_range
            ]
            
            if covering_reservations:
                occ_var = model.NewBoolVar(f"occ_{h_idx}_{day_offset}")
                # occ_var = 1 iff any covering reservation is assigned to room h
                model.AddMaxEquality(
                    occ_var,
                    [x[r_idx, h_idx] for r_idx in covering_reservations]
                )
                is_occupied[h_idx, day_offset] = occ_var
            else:
                # No reservations cover this date; occupancy is 0
                is_occupied[h_idx, day_offset] = model.NewConstant(0)
    
    logger.debug(f"Occupancy tracking: {len(is_occupied)} occupancy variables")
    
    # ═══════════════════════════════════════════════════════════════
    # SOFT CONSTRAINT 2: Gap penalties (1-night gaps)
    # ═══════════════════════════════════════════════════════════════
    
    gap_vars = []
    for h_idx in range(len(rooms)):
        for day_offset in range(1, total_days - 1):
            prev_occ = is_occupied.get((h_idx, day_offset - 1))
            curr_occ = is_occupied.get((h_idx, day_offset))
            next_occ = is_occupied.get((h_idx, day_offset + 1))
            
            if all(v is not None for v in [prev_occ, curr_occ, next_occ]):
                gap = model.NewBoolVar(f"gap_{h_idx}_{day_offset}")
                
                # gap = 1 iff (prev ∧ next ∧ ¬curr)
                model.Add(gap <= prev_occ)
                model.Add(gap <= next_occ)
                model.Add(gap + curr_occ <= 1)
                model.Add(gap >= prev_occ + next_occ - curr_occ - 1)
                
                gap_vars.append(gap)
    
    logger.debug(f"Gap penalty variables: {len(gap_vars)}")
    
    # ═══════════════════════════════════════════════════════════════
    # BUILD OBJECTIVE FUNCTION
    # ═══════════════════════════════════════════════════════════════
    
    objective_terms = []
    
    # Term 1: Minimize gaps
    for gap in gap_vars:
        objective_terms.append(w_gap * gap)
    
    # Term 2: Penalize unassigned reservations heavily
    for r_idx in range(len(reservations)):
        objective_terms.append(w_unassigned * (1 - is_assigned[r_idx]))
    
    # Term 3: Stability bonus (prefer current assignment)
    for r_idx, res in enumerate(reservations):
        if res.current_room_id and not res.is_locked:
            for h_idx, room in enumerate(rooms):
                if room.room_id == res.current_room_id:
                    objective_terms.append(w_stability * x[r_idx, h_idx])
    
    # Term 4: Category matching preference
    for r_idx, res in enumerate(reservations):
        for h_idx, room in enumerate(rooms):
            if room.category_id == res.category_id:
                # Bonus for exact match
                objective_terms.append(w_category * x[r_idx, h_idx])
            else:
                # Penalty for upgrade
                upgrade_penalty = res.category_priority(room.category_id) * 25
                objective_terms.append(upgrade_penalty * x[r_idx, h_idx])
    
    # Term 5: Room usage fragmentation
    room_used_vars = []
    for h_idx in range(len(rooms)):
        room_used = model.NewBoolVar(f"room_used_{h_idx}")
        model.AddMaxEquality(
            room_used,
            [x[r_idx, h_idx] for r_idx in range(len(reservations))]
        )
        objective_terms.append(w_room_usage * room_used)
        room_used_vars.append(room_used)
    
    logger.debug(f"Objective function: {len(objective_terms)} terms")
    
    # ═══════════════════════════════════════════════════════════════
    # MINIMIZE
    # ═══════════════════════════════════════════════════════════════
    
    model.Minimize(sum(objective_terms))
    
    # ═══════════════════════════════════════════════════════════════
    # SOLVER CONFIGURATION
    # ═══════════════════════════════════════════════════════════════
    
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = max_solver_time_seconds
    solver.parameters.log_search_progress = (log_level == "DEBUG")
    solver.parameters.num_workers = 4  # Parallel solving
    
    logger.info(f"Starting CP-SAT solver (max {max_solver_time_seconds}s, "
                f"{solver.parameters.num_workers} workers)")
    
    # ═══════════════════════════════════════════════════════════════
    # SOLVE
    # ═══════════════════════════════════════════════════════════════
    
    import time
    start_time = time.time()
    status = solver.Solve(model)
    elapsed_ms = int((time.time() - start_time) * 1000)
    
    # ═══════════════════════════════════════════════════════════════
    # PROCESS RESULT
    # ═══════════════════════════════════════════════════════════════
    
    status_names = {
        cp_model.OPTIMAL: "OPTIMAL",
        cp_model.FEASIBLE: "FEASIBLE",
        cp_model.INFEASIBLE: "INFEASIBLE",
        cp_model.MODEL_INVALID: "INVALID"
    }
    status_str = status_names.get(status, "UNKNOWN")
    
    logger.info(f"Solver finished: status={status_str}, time={elapsed_ms}ms, "
                f"objective={solver.ObjectiveValue() if status in {cp_model.OPTIMAL, cp_model.FEASIBLE} else 'N/A'}")
    
    if status not in {cp_model.OPTIMAL, cp_model.FEASIBLE}:
        logger.error(f"Solver failed with status {status_str}")
        return AllocationResult(
            success=False,
            assignments={},
            unassigned_reservations=[r.reservation_id for r in reservations],
            error=f"CP-SAT solver status: {status_str}",
            solver_status=status_str,
            solver_wall_time_ms=elapsed_ms
        )
    
    # ═══════════════════════════════════════════════════════════════
    # EXTRACT ASSIGNMENTS
    # ═══════════════════════════════════════════════════════════════
    
    assignments = {}
    moved_reservations = []
    unassigned_reservations = []
    reasoning = {}
    
    for r_idx, res in enumerate(reservations):
        is_assigned_val = solver.Value(is_assigned[r_idx])
        
        if is_assigned_val == 0:
            unassigned_reservations.append(res.reservation_id)
            reasoning[res.reservation_id] = "Infeasible: no room matches category or availability"
            continue
        
        # Find assigned room
        assigned_room = None
        for h_idx, room in enumerate(rooms):
            if solver.Value(x[r_idx, h_idx]) == 1:
                assigned_room = room
                break
        
        if assigned_room is None:
            # Should not happen if solver is correct
            unassigned_reservations.append(res.reservation_id)
            reasoning[res.reservation_id] = "Internal error: assigned but no room found"
            continue
        
        assignments[res.reservation_id] = assigned_room.room_id
        
        # Check if moved
        if res.current_room_id != assigned_room.room_id and res.current_room_id is not None:
            moved_reservations.append(res.reservation_id)
            if assigned_room.category_id == res.category_id:
                reasoning[res.reservation_id] = f"Moved to {assigned_room.room_number} (same category)"
            else:
                reasoning[res.reservation_id] = f"Upgraded to {assigned_room.room_number} (category {assigned_room.category_id})"
        else:
            reasoning[res.reservation_id] = f"Assigned to {assigned_room.room_number}"
    
    logger.info(f"Allocation complete: {len(assignments)} assigned, "
                f"{len(moved_reservations)} moved, "
                f"{len(unassigned_reservations)} unassigned")
    
    # ═══════════════════════════════════════════════════════════════
    # BUILD RESULT
    # ═══════════════════════════════════════════════════════════════
    
    gap_value = solver.ObjectiveValue() if status in {cp_model.OPTIMAL, cp_model.FEASIBLE} else 0.0
    gap_pct = 0.0 if status == cp_model.OPTIMAL else solver.SufficientlyOptimal()
    
    return AllocationResult(
        success=len(unassigned_reservations) == 0,
        assignments=assignments,
        moved_reservations=moved_reservations,
        unassigned_reservations=unassigned_reservations,
        objective_value=gap_value,
        optimality_gap=gap_pct,
        solver_wall_time_ms=elapsed_ms,
        solver_status=status_str,
        reasoning=reasoning
    )
```

### 2.2 Greedy Fallback Algorithm

```python
def _run_allocation_greedy(
    reservations: list[ReservationSlot],
    rooms: list[RoomSlot],
    optimization_horizon: Optional[tuple[date, date]] = None,
    policy_constraints: Optional[dict] = None,
    policy_weights: Optional[dict] = None
) → AllocationResult:
    """
    Fallback allocation when OR-Tools not available.
    Uses a greedy first-fit approach with heuristics.
    """
    
    logger = get_logger(__name__)
    logger.info("Using greedy allocation fallback")
    
    # Sort reservations: locked first, then by check-in date
    sorted_reservations = sorted(
        enumerate(reservations),
        key=lambda item: (
            not item[1].is_locked,  # Locked first
            item[1].check_in,        # Earlier check-in first
            -(item[1].nights)        # Longer stays first
        )
    )
    
    assignments = {}
    moved = []
    unassigned = []
    occupied_per_room = {room.room_id: [] for room in rooms}
    
    for r_idx, res in sorted_reservations:
        
        # If locked, must stay in current room
        if res.is_locked:
            if res.current_room_id not in occupied_per_room:
                unassigned.append(res.reservation_id)
                logger.warning(f"Locked reservation {res.reservation_id} "
                               f"(room {res.current_room_id}) not in room list")
                continue
            
            # Check compatibility
            can_fit = not any(
                (stay_in < res.check_out and res.check_in < stay_out)
                for stay_in, stay_out in occupied_per_room[res.current_room_id]
            )
            
            if can_fit:
                assignments[res.reservation_id] = res.current_room_id
                occupied_per_room[res.current_room_id].append((res.check_in, res.check_out))
            else:
                unassigned.append(res.reservation_id)
            continue
        
        # Find best room
        best_room = None
        best_score = -float('inf')
        
        for room in rooms:
            # Category check
            if room.category_id not in res.effective_allowed_category_ids():
                continue
            
            # Availability check
            can_fit = not any(
                (stay_in < res.check_out and res.check_in < stay_out)
                for stay_in, stay_out in occupied_per_room[room.room_id]
            )
            
            if not can_fit:
                continue
            
            # Score calculation
            score = 0
            
            # Exact category match: big bonus
            if room.category_id == res.category_id:
                score += 1000
            else:
                score -= res.category_priority(room.category_id) * 10
            
            # Adjacency bonus (continuity)
            adjacent = sum(1
                for stay_in, stay_out in occupied_per_room[room.room_id]
                if stay_out == res.check_in or stay_in == res.check_out
            )
            score += adjacent * 50
            
            # Gap penalty (avoid creating 1-night gaps)
            existing_stays = sorted(occupied_per_room[room.room_id], key=lambda x: x[0])
            all_stays = sorted(existing_stays + [(res.check_in, res.check_out)], key=lambda x: x[0])
            gaps = sum(1
                for i in range(len(all_stays) - 1)
                if (all_stays[i + 1][0] - all_stays[i][1]).days == 1
            )
            score -= gaps * 25
            
            # Stability (prefer current room if unlocked)
            if res.current_room_id == room.room_id:
                score += 100
            
            if score > best_score:
                best_score = score
                best_room = room
        
        if best_room:
            assignments[res.reservation_id] = best_room.room_id
            occupied_per_room[best_room.room_id].append((res.check_in, res.check_out))
            
            if res.current_room_id != best_room.room_id and res.current_room_id is not None:
                moved.append(res.reservation_id)
        else:
            unassigned.append(res.reservation_id)
    
    return AllocationResult(
        success=len(unassigned) == 0,
        assignments=assignments,
        moved_reservations=moved,
        unassigned_reservations=unassigned,
        objective_value=0.0,
        solver_status="GREEDY_FALLBACK",
        solver_wall_time_ms=0
    )
```

---

## 3. Room Move Execution

### 3.1 Validación Pre-Move

```python
def validate_room_move_intent(
    db: Session,
    intent: RoomMoveIntent,
    reservation: Reservation,
    hotel_id: int
) → tuple[bool, Optional[str]]:
    """
    Validate a room move intent before execution.
    Returns (is_valid, error_message).
    """
    
    # 1. Check reservation exists and belongs to hotel
    if reservation.hotel_id != hotel_id:
        return False, "Reservation not in active hotel"
    
    # 2. Check if locked (checked-in)
    if reservation.status == ReservationStatusEnum.CHECKED_IN:
        return False, "Cannot move checked-in reservation"
    
    # 3. Check if terminal state
    if reservation.status in {
        ReservationStatusEnum.CHECKED_OUT,
        ReservationStatusEnum.CANCELLED,
        ReservationStatusEnum.NO_SHOW
    }:
        return False, f"Cannot move {reservation.status} reservation"
    
    # 4. Fetch destination room
    to_room = db.query(Room).filter(
        Room.id == intent.to_room_id,
        Room.hotel_id == hotel_id
    ).first()
    
    if not to_room:
        return False, "Destination room not found"
    
    # 5. Check category compatibility
    allowed_cats = [reservation.category_id]  # TODO: fetch from policy
    if to_room.category_id not in allowed_cats:
        # Could allow upgrade with warning
        pass
    
    # 6. Check availability (pessimistic lock)
    to_room_lock = db.query(Room).with_for_update().filter(
        Room.id == intent.to_room_id
    ).first()
    
    conflicts = db.query(Reservation).filter(
        Reservation.room_id == intent.to_room_id,
        Reservation.id != reservation.id,
        Reservation.check_in_date < reservation.check_out_date,
        Reservation.check_out_date > reservation.check_in_date,
        Reservation.status.in_([
            ReservationStatusEnum.CHECKED_IN,
            ReservationStatusEnum.FULLY_PAID
        ])
    ).all()
    
    if conflicts:
        return False, f"Room occupied during stay ({len(conflicts)} conflicts)"
    
    return True, None
```

### 3.2 Ejecución Atomic del Move

```python
def execute_room_move(
    db: Session,
    intent: RoomMoveIntent,
    reservation: Reservation,
    hotel_id: int
) → RoomMoveEvent:
    """
    Execute the room move atomically with full audit trail.
    Raises exception on failure.
    """
    
    logger = get_logger(__name__)
    
    try:
        # Validate
        is_valid, error_msg = validate_room_move_intent(
            db, intent, reservation, hotel_id
        )
        if not is_valid:
            raise ReservationOperationsError(error_msg)
        
        # Fetch rooms with lock
        from_room = db.query(Room).with_for_update().filter(
            Room.id == reservation.room_id
        ).first() if reservation.room_id else None
        
        to_room = db.query(Room).with_for_update().filter(
            Room.id == intent.to_room_id
        ).first()
        
        # ─────────────────────────────────────────────────────────
        # PERFORM THE MOVE
        # ─────────────────────────────────────────────────────────
        
        old_room_id = reservation.room_id
        reservation.room_id = to_room.id
        reservation.category_id = to_room.category_id
        reservation.updated_at = datetime.now(timezone.utc)
        
        # ─────────────────────────────────────────────────────────
        # CREATE AUDIT EVENT
        # ─────────────────────────────────────────────────────────
        
        event = RoomMoveEvent(
            hotel_id=hotel_id,
            reservation_id=reservation.id,
            from_room_id=old_room_id,
            to_room_id=to_room.id,
            move_type=intent.move_type,
            reason_code=intent.reason_code,
            notes=intent.notes,
            created_by_user_id=intent.moved_by_user_id,
            created_at=datetime.now(timezone.utc)
        )
        db.add(event)
        db.flush()
        
        # ─────────────────────────────────────────────────────────
        # RECORD FEEDBACK (for allocation policy learning)
        # ─────────────────────────────────────────────────────────
        
        feedback = AllocationManualOverrideFeedback(
            hotel_id=hotel_id,
            reservation_id=reservation.id,
            override_type="room_move",
            override_category_id=None,
            override_room_id=to_room.id,
            reason_code=intent.reason_code,
            notes=intent.notes or f"Move to {to_room.room_number}",
            created_by_user_id=intent.moved_by_user_id,
            created_at=datetime.now(timezone.utc)
        )
        db.add(feedback)
        
        # ─────────────────────────────────────────────────────────
        # COMMIT
        # ─────────────────────────────────────────────────────────
        
        db.commit()
        
        logger.info(f"Room move executed: reservation {reservation.id} "
                    f"{old_room_id or 'unassigned'} → {to_room.id} "
                    f"(reason: {intent.reason_code})")
        
        return event
        
    except Exception as e:
        db.rollback()
        logger.error(f"Room move failed: {str(e)}")
        raise ReservationOperationsError(f"Failed to move room: {str(e)}")
```

---

## 4. State Machine Transitions

### 4.1 Validator

```python
def validate_transition(
    current_status: ReservationStatusEnum,
    new_status: ReservationStatusEnum,
    current_datetime: datetime
) → tuple[bool, Optional[str]]:
    """
    Validate if transition is allowed per state machine rules.
    """
    
    VALID_TRANSITIONS = {
        ReservationStatusEnum.PENDING: {
            ReservationStatusEnum.DEPOSIT_PAID,
            ReservationStatusEnum.FULLY_PAID,
            ReservationStatusEnum.CANCELLED,
        },
        ReservationStatusEnum.DEPOSIT_PAID: {
            ReservationStatusEnum.FULLY_PAID,
            ReservationStatusEnum.CANCELLED,
        },
        ReservationStatusEnum.FULLY_PAID: {
            ReservationStatusEnum.CHECKED_IN,
            ReservationStatusEnum.CANCELLED,
            ReservationStatusEnum.NO_SHOW,
        },
        ReservationStatusEnum.CHECKED_IN: {
            ReservationStatusEnum.CHECKED_OUT,
        },
        ReservationStatusEnum.CHECKED_OUT: set(),     # terminal
        ReservationStatusEnum.CANCELLED: set(),        # terminal
        ReservationStatusEnum.NO_SHOW: set(),          # terminal
    }
    
    # Check if transition allowed
    if new_status not in VALID_TRANSITIONS.get(current_status, set()):
        return False, f"Cannot transition {current_status} → {new_status}"
    
    # Guard: never allow NO_SHOW/CANCELLED after check-in
    if current_status in {ReservationStatusEnum.CHECKED_IN, ReservationStatusEnum.CHECKED_OUT}:
        if new_status in {ReservationStatusEnum.CANCELLED, ReservationStatusEnum.NO_SHOW}:
            return False, "Cannot cancel/no-show after check-in/out"
    
    return True, None
```

### 4.2 Transición Atomic

```python
def transition_reservation_status(
    db: Session,
    reservation: Reservation,
    new_status: ReservationStatusEnum,
    transition_reason: str,
    transitioned_by_user_id: Optional[int] = None,
    metadata: Optional[dict] = None
) → bool:
    """
    Atomically transition reservation status with full audit trail.
    Returns success boolean.
    """
    
    logger = get_logger(__name__)
    
    try:
        # Validate transition
        is_valid, error = validate_transition(
            reservation.status,
            new_status,
            datetime.now(timezone.utc)
        )
        
        if not is_valid:
            logger.warning(f"Invalid transition: {error}")
            raise ReservationError(error)
        
        old_status = reservation.status
        
        # ─────────────────────────────────────────────────────────
        // PERFORM TRANSITION
        // ─────────────────────────────────────────────────────────
        
        reservation.status = new_status
        reservation.updated_at = datetime.now(timezone.utc)
        
        // Terminal state handling
        if new_status == ReservationStatusEnum.CANCELLED:
            reservation.cancelled_at = datetime.now(timezone.utc)
            reservation.cancelled_by_user_id = transitioned_by_user_id
            reservation.cancellation_reason_note = transition_reason
        
        elif new_status == ReservationStatusEnum.NO_SHOW:
            reservation.no_show_confirmed_at = datetime.now(timezone.utc)
        
        // ─────────────────────────────────────────────────────────
        // CREATE HISTORY ENTRY
        // ─────────────────────────────────────────────────────────
        
        history = ReservationStatusHistory(
            hotel_id=reservation.hotel_id,
            reservation_id=reservation.id,
            from_status=old_status,
            to_status=new_status,
            changed_at=datetime.now(timezone.utc),
            changed_by_user_id=transitioned_by_user_id,
            reason=transition_reason,
            metadata_json=json.dumps(metadata or {})
        )
        db.add(history)
        
        // ─────────────────────────────────────────────────────────
        // SIDE EFFECTS (based on new status)
        // ─────────────────────────────────────────────────────────
        
        if new_status == ReservationStatusEnum.CHECKED_IN:
            // Lock room assignment
            reservation.allocation_locked = True
            
            // Record actual check-in time
            reservation.actual_check_in = datetime.now(timezone.utc)
            
            // Trigger housekeeping workflow (async)
            # emit_event("reservation.checked_in", reservation)
        
        elif new_status == ReservationStatusEnum.CHECKED_OUT:
            // Record actual check-out time
            reservation.actual_check_out = datetime.now(timezone.utc)
            reservation.allocation_locked = False
            
            // Mark room as needing cleaning
            # emit_event("room.needs_cleaning", reservation.room)
        
        elif new_status == ReservationStatusEnum.CANCELLED:
            // Free up room
            reservation.allocation_locked = False
            
            // Process refund (async)
            # emit_event("reservation.cancelled", reservation)
        
        // ─────────────────────────────────────────────────────────
        // COMMIT
        // ─────────────────────────────────────────────────────────
        
        db.commit()
        
        logger.info(f"Transition: reservation {reservation.id} "
                    f"{old_status} → {new_status}")
        
        return True
        
    except Exception as e:
        db.rollback()
        logger.error(f"Transition failed: {str(e)}")
        return False
```

---

## 5. Testing Strategies (Pseudocódigo)

### 5.1 Unit Test: CP-SAT Exactness

```python
def test_cp_sat_exact_match():
    """5 reservations, 5 rooms: all should be assigned 1:1."""
    
    # Setup
    rooms = [
        RoomSlot(room_id=i, category_id=1, room_number=f"{i+1}01")
        for i in range(5)
    ]
    
    reservations = [
        ReservationSlot(
            reservation_id=i,
            category_id=1,
            check_in=date(2026, 7, i+1),
            check_out=date(2026, 7, i+2),
            current_room_id=None,
            is_locked=False,
            allowed_category_ids=[]
        )
        for i in range(5)
    ]
    
    # Execute
    result = run_allocation(reservations, rooms)
    
    # Assert
    assert result.success
    assert len(result.assignments) == 5
    assert len(result.unassigned_reservations) == 0
    assert len(result.moved_reservations) == 0
    assert all(
        result.assignments[res.reservation_id] in [r.room_id for r in rooms]
        for res in reservations
    )
```

### 5.2 Integration Test: State Machine

```python
def test_state_machine_full_flow(db: Session):
    """Complete booking lifecycle: PENDING → CHECKED_OUT."""
    
    // Setup fixture
    hotel = create_hotel(db)
    guest = create_guest(db)
    category = create_room_category(db, hotel_id=hotel.id)
    room = create_room(db, category_id=category.id)
    
    // Create reservation (PENDING)
    res = create_reservation(
        db,
        guest_id=guest.id,
        room_id=room.id,
        category_id=category.id,
        check_in=date(2026, 7, 1),
        check_out=date(2026, 7, 5),
        hotel_id=hotel.id
    )
    assert res.status == ReservationStatusEnum.PENDING
    
    // Transition: PENDING → DEPOSIT_PAID
    success = transition_reservation_status(
        db, res, ReservationStatusEnum.DEPOSIT_PAID,
        "Deposit payment received",
        transitioned_by_user_id=1
    )
    assert success
    assert res.status == ReservationStatusEnum.DEPOSIT_PAID
    
    // Transition: DEPOSIT_PAID → FULLY_PAID
    success = transition_reservation_status(
        db, res, ReservationStatusEnum.FULLY_PAID,
        "Final payment received",
        transitioned_by_user_id=1
    )
    assert success
    
    // Transition: FULLY_PAID → CHECKED_IN
    success = transition_reservation_status(
        db, res, ReservationStatusEnum.CHECKED_IN,
        "Guest arrived",
        transitioned_by_user_id=1
    )
    assert success
    assert res.allocation_locked  // Room locked
    
    // Transition: CHECKED_IN → CHECKED_OUT
    success = transition_reservation_status(
        db, res, ReservationStatusEnum.CHECKED_OUT,
        "Guest departed",
        transitioned_by_user_id=1
    )
    assert success
    assert res.actual_check_out is not None
    
    // Verify history
    history = db.query(ReservationStatusHistory).filter(
        ReservationStatusHistory.reservation_id == res.id
    ).all()
    assert len(history) == 4
```

---

## Conclusión

Este pseudocódigo proporciona:

1. **Claridad**: Cada función tiene propósito explícito
2. **Completitud**: Manejo de edge cases y errores
3. **Auditabilidad**: Logging detallado en cada etapa
4. **Robustez**: Validaciones antes de cambios
5. **Testing**: Estrategias claras para cobertura

El sistema está listo para implementación en Python/FastAPI.

```
