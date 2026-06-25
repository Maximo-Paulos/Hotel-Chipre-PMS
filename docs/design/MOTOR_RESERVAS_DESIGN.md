# Módulo Motor de Reservas — Diseño de Algoritmo de Optimización

## 1. Visión General

El **Motor de Reservas** es el componente central que:
1. Gestiona el ciclo de vida completo de las reservas
2. Optimiza la asignación de habitaciones usando programación por restricciones (CP-SAT)
3. Ejecuta movimientos de reservas con auditoría y cumplimiento de constraints
4. Maneja cambios de estado con máquina de estados estricta
5. Calcula precios dinámicamente según políticas comerciales

### Arquitectura en 3 capas

```
┌─────────────────────────────────────────────────────────────┐
│           API de Reservas (REST/GraphQL)                    │
│  POST /reservations, PATCH /{id}, DELETE /{id}              │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│    Servicio de Reservas (Orquestación de Negocio)          │
│  - Validación de dominio                                    │
│  - Máquina de estados                                       │
│  - Cálculo de precios                                       │
│  - Transacciones ACID                                       │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│    Motor de Optimización + Operaciones                      │
│  - AllocationEngine (CP-SAT)                                │
│  - Movimientos de habitaciones                              │
│  - Auditoría de cambios                                     │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│              Persistencia (SQLAlchemy + PostgreSQL)         │
│  - Transacciones pessimistas                                │
│  - Índices para queries críticas                            │
│  - Audit trails completos                                   │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Modelo de Datos (Entidades Principales)

### 2.1 Reservation (Núcleo)

```
Reservation {
  id: int (PK)
  hotel_id: int (FK) — multi-tenancy
  confirmation_code: str (UNIQUE, INDEXED)
  
  // Entidades relacionadas
  guest_id: int (FK)
  room_id: int (FK, NULLABLE) — asignado durante optimización
  category_id: int (FK) — categoría original
  
  // Fecha/hora
  check_in_date: date
  check_out_date: date
  actual_check_in: datetime (nullable)
  actual_check_out: datetime (nullable)
  
  // Máquina de estados
  status: ReservationStatusEnum {
    PENDING → DEPOSIT_PAID → FULLY_PAID → CHECKED_IN → CHECKED_OUT
    ↓ (desde cualquiera hasta CHECKED_IN)
    CANCELLED
    NO_SHOW
  }
  
  // Asignación
  allocation_status: str {
    "unassigned" | "assigned" | "moved" | "locked"
  }
  allocation_locked: bool — true si checked_in
  
  // Finanzas
  total_amount: float
  amount_paid: float
  deposit_amount: float
  subtotal_amount, tax_amount, fee_amount, commission_amount: float
  net_amount: float
  currency_code: str (ARS por defecto)
  
  // Auditoría
  created_at: datetime
  updated_at: datetime
  cancelled_at: datetime (nullable)
  cancelled_by_user_id: int (FK, nullable)
}
```

### 2.2 Tablas de Operaciones (Auditoría)

```
RoomMoveEvent {
  id: int (PK)
  hotel_id: int (FK)
  reservation_id: int (FK)
  from_room_id: int (FK, nullable) — NULL si es primera asignación
  to_room_id: int (FK)
  move_type: RoomMoveTypeEnum {
    "initial_allocation" | "manual_move" | "optimization_move" | "upgrade"
  }
  reason_code: str (nullable)
  notes: str (nullable)
  created_by_user_id: int (FK, nullable)
  created_at: datetime
}

ReservationAdjustment {
  id: int (PK)
  hotel_id: int (FK)
  reservation_id: int (FK)
  kind: ReservationAdjustmentKindEnum {
    "category_upgrade" | "room_move" | "date_change" | "guest_change" | "ota_rebook"
  }
  status: ReservationAdjustmentStatusEnum {
    "draft" | "approved" | "applied" | "reversed"
  }
  original_pricing_snapshot: json
  adjusted_pricing_snapshot: json
  delta_amount: float
  approved_at: datetime (nullable)
  applied_at: datetime (nullable)
  created_by_user_id: int (FK)
  created_at: datetime
}

BillingAdjustment {
  id: int (PK)
  reservation_id: int (FK)
  type: BillingAdjustmentTypeEnum {
    "surcharge" | "discount" | "refund" | "cancellation_fee"
  }
  amount: float
  currency_code: str
  reason: str
  created_at: datetime
}
```

---

## 3. Algoritmo de Optimización (CP-SAT)

### 3.1 Formulación Matemática

```
MINIMIZE:
  w_fragmentation × Σ gap_penalties[h, d]
  + w_stability × Σ (1 - x[r, current_room])
  + w_unassigned × Σ (1 - is_assigned[r])
  + w_category × Σ category_mismatch[r, h]
  + w_room_usage × Σ room_fragmentation[h]

SUBJECT TO:

Hard Constraints:
  C1. Exactitud: Σ_h x[r, h] = is_assigned[r]  ∀r
  C2. Categoría: x[r, h] = 0 si category[h] ∉ allowed_categories[r]  ∀r,h
  C3. Sin solapamiento: x[r1, h] + x[r2, h] ≤ 1 si overlap(r1,r2)  ∀r1<r2,h
  C4. Bloqueo: x[r, h] = 1 si r.is_locked ∧ current_room[r] = h  ∀r,h
  C5. Dominio: x[r, h] ∈ {0, 1}  ∀r,h

Soft Constraints (penalizadas en objetivo):
  S1. Fragmentación: penalizar gaps de 1 noche entre estancias
  S2. Estabilidad: preferir mantener asignación actual
  S3. Exactitud: preferir categoría exacta (evitar upgrades innecesarios)
  S4. Ocupación: maximizar utilización por habitación
```

### 3.2 Estructura de Entrada (ReservationSlot)

```pseudocode
class ReservationSlot:
    reservation_id: int                      # ID único en BD
    category_id: int                         # Categoría solicitada
    check_in: date                           # Fecha entrada
    check_out: date                          # Fecha salida
    current_room_id: Optional[int]           # Room actual (puede moverse)
    is_locked: bool                          # True si checked_in
    allowed_category_ids: List[int]          # Upgrades permitidos
    category_priority_by_id: Dict[int, int]  # Prioridad de upgrade
```

### 3.3 Estructura de Entrada (RoomSlot)

```pseudocode
class RoomSlot:
    room_id: int                             # ID único
    room_number: str                         # Número visible (101, 201A, etc.)
    category_id: int                         # Categoría de la habitación
    occupancy_schedule: List[Tuple[date, date]]  # Estancias ya asignadas
```

### 3.4 Estructura de Salida

```pseudocode
class AllocationResult:
    success: bool
    assignments: Dict[int, int]              # reservation_id → room_id
    unassigned_reservations: List[int]       # Reservas sin asignar (infeasible)
    moved_reservations: List[int]            # Reservas movidas (vs. asignación previa)
    objective_value: float                   # Valor de la función objetivo
    error: Optional[str]                     # Mensaje de error si success=False
    solver_stats: Dict                       # Tiempo ejecución, gap de optimalidad, etc.
    reasoning: Dict[int, str]                # Por qué cada reserva fue asignada/no asignada
```

### 3.5 Pseudocódigo Principal

```pseudocode
FUNCTION run_allocation(
    reservations: List[ReservationSlot],
    rooms: List[RoomSlot],
    optimization_horizon: Optional[Tuple[date, date]],
    policy_constraints: Dict,
    policy_weights: Dict
) → AllocationResult:

    IF NOT reservations:
        RETURN AllocationResult(success=True, assignments={})
    
    // Intentar CP-SAT si disponible
    IF NOT ortools.installed():
        RETURN _run_allocation_greedy(reservations, rooms, ...)
    
    model ← NEW CpModel()
    
    // ══════════════════════════════════════════════════════════
    // VARIABLES DE DECISIÓN
    // ══════════════════════════════════════════════════════════
    x[r_idx, h_idx] ← NewBoolVar(f"assign_{r_idx}_{h_idx}")
        ∀ r_idx ∈ reservations, h_idx ∈ rooms
    
    is_assigned[r_idx] ← NewBoolVar(f"assigned_{r_idx}")
        ∀ r_idx ∈ reservations
    
    FOR r_idx IN range(len(reservations)):
        model.Add(
            SUM(x[r_idx, h_idx] FOR h_idx IN rooms) == is_assigned[r_idx]
        )
    
    // ══════════════════════════════════════════════════════════
    // CONSTRAINTS DURAS
    // ══════════════════════════════════════════════════════════
    
    // C1: Reservas locked permanecen en su habitación
    FOR r_idx, res IN enumerate(reservations):
        IF res.is_locked ∧ res.current_room_id IS NOT NULL:
            FOR h_idx, room IN enumerate(rooms):
                IF room.room_id == res.current_room_id:
                    model.Add(x[r_idx, h_idx] == 1)
                ELSE:
                    model.Add(x[r_idx, h_idx] == 0)
    
    // C2: Categoría debe coincidir o estar en upgrades permitidos
    FOR r_idx, res IN enumerate(reservations):
        FOR h_idx, room IN enumerate(rooms):
            IF room.category_id NOT IN res.effective_allowed_category_ids():
                model.Add(x[r_idx, h_idx] == 0)
    
    // C3: No solapamiento temporal en misma habitación
    FOR h_idx IN range(len(rooms)):
        FOR r1_idx, r2_idx IN combinations(reservations, 2):
            IF overlap(reservations[r1_idx], reservations[r2_idx]):
                model.Add(x[r1_idx, h_idx] + x[r2_idx, h_idx] <= 1)
    
    // C4: Todas las reservas locked deben estar asignadas
    FOR r_idx, res IN enumerate(reservations):
        IF res.is_locked:
            model.Add(is_assigned[r_idx] == 1)
    
    // ══════════════════════════════════════════════════════════
    // CONSTRUIR VARIABLES DE OCUPACIÓN (para penalidad de gaps)
    // ══════════════════════════════════════════════════════════
    
    horizon_start ← optimization_horizon[0] OR min(check_in de todas las reservas)
    horizon_end ← optimization_horizon[1] OR max(check_out de todas las reservas)
    total_days ← (horizon_end - horizon_start).days
    
    FOR h_idx IN range(len(rooms)):
        FOR d IN range(total_days):
            current_date ← horizon_start + timedelta(days=d)
            covering_reservations ← [r_idx | current_date ∈ reservations[r_idx].date_range]
            
            IF covering_reservations:
                is_occupied[h_idx, d] ← NewBoolVar(f"occ_{h_idx}_{d}")
                model.AddMaxEquality(
                    is_occupied[h_idx, d],
                    [x[r_idx, h_idx] FOR r_idx IN covering_reservations]
                )
            ELSE:
                is_occupied[h_idx, d] ← 0 (constante)
    
    // ══════════════════════════════════════════════════════════
    // CONSTRUIR PENALIDADES DE GAPS
    // ══════════════════════════════════════════════════════════
    
    gap_penalties ← []
    FOR h_idx IN range(len(rooms)):
        FOR d IN range(1, total_days - 1):
            prev_occupied ← is_occupied[h_idx, d-1]
            curr_occupied ← is_occupied[h_idx, d]
            next_occupied ← is_occupied[h_idx, d+1]
            
            IF all NOT NULL:
                gap ← NewBoolVar(f"gap_{h_idx}_{d}")
                // Gap es 1 ssi (prev ∧ next ∧ ¬curr)
                model.Add(gap <= prev_occupied)
                model.Add(gap <= next_occupied)
                model.Add(gap + curr_occupied <= 1)
                model.Add(gap >= prev_occupied + next_occupied - curr_occupied - 1)
                gap_penalties.append(gap)
    
    // ══════════════════════════════════════════════════════════
    // FUNCIÓN OBJETIVO (SOFT CONSTRAINTS)
    // ══════════════════════════════════════════════════════════
    
    objective_terms ← []
    
    // 1. Penalidad por gaps de 1 noche
    w_gap ← policy_weights.get("minimize_one_night_gaps", 100)
    FOR gap IN gap_penalties:
        objective_terms.append(w_gap × gap)
    
    // 2. Penalidad por no asignar
    w_unassigned ← policy_weights.get("unassigned_penalty", 10000)
    FOR r_idx IN range(len(reservations)):
        objective_terms.append(w_unassigned × (1 - is_assigned[r_idx]))
    
    // 3. Bonificación de estabilidad (mantener asignación actual)
    w_stability ← policy_weights.get("stability", 5)
    FOR r_idx, res IN enumerate(reservations):
        IF res.current_room_id:
            FOR h_idx, room IN enumerate(rooms):
                IF room.room_id == res.current_room_id ∧ NOT res.is_locked:
                    objective_terms.append(w_stability × x[r_idx, h_idx])
    
    // 4. Penalidad por cambios de categoría
    w_category ← policy_weights.get("prefer_exact_match", 500)
    FOR r_idx, res IN enumerate(reservations):
        FOR h_idx, room IN enumerate(rooms):
            IF room.category_id == res.category_id:
                objective_terms.append(w_category × x[r_idx, h_idx])
            ELSE:
                priority_penalty ← res.category_priority(room.category_id) × 25
                objective_terms.append(priority_penalty × x[r_idx, h_idx])
    
    // 5. Penalidad por fragmentación de salas (usar más de K salas)
    w_room_usage ← policy_weights.get("room_usage_penalty", 50)
    FOR h_idx IN range(len(rooms)):
        room_used ← NewBoolVar(f"room_used_{h_idx}")
        model.AddMaxEquality(room_used, [x[r_idx, h_idx] FOR r_idx IN reservations])
        objective_terms.append(w_room_usage × room_used)
    
    model.Minimize(SUM(objective_terms))
    
    // ══════════════════════════════════════════════════════════
    // RESOLVER
    // ══════════════════════════════════════════════════════════
    
    solver ← CpSolver()
    solver.parameters.max_time_in_seconds = 30
    solver.parameters.log_search_progress = False
    
    status ← solver.Solve(model)
    
    // ══════════════════════════════════════════════════════════
    // PROCESAR RESULTADO
    // ══════════════════════════════════════════════════════════
    
    IF status IN {OPTIMAL, FEASIBLE}:
        assignments ← {}
        moved_reservations ← []
        unassigned_reservations ← []
        
        FOR r_idx, res IN enumerate(reservations):
            IF NOT solver.Value(is_assigned[r_idx]):
                unassigned_reservations.append(res.reservation_id)
            ELSE:
                FOR h_idx, room IN enumerate(rooms):
                    IF solver.Value(x[r_idx, h_idx]):
                        assignments[res.reservation_id] = room.room_id
                        
                        IF res.current_room_id ≠ room.room_id:
                            moved_reservations.append(res.reservation_id)
                        
                        BREAK
        
        RETURN AllocationResult(
            success=True,
            assignments=assignments,
            moved_reservations=moved_reservations,
            unassigned_reservations=unassigned_reservations,
            objective_value=solver.ObjectiveValue(),
            solver_stats={
                "wall_time": solver.WallTime(),
                "gap": solver.SufficientlyOptimal() ? 0 : solver.Gap()
            }
        )
    ELSE:
        RETURN AllocationResult(
            success=False,
            error=f"CP-SAT status: {status}"
        )
```

### 3.6 Fallback Greedy (Sin OR-Tools)

```pseudocode
FUNCTION _run_allocation_greedy(
    reservations: List[ReservationSlot],
    rooms: List[RoomSlot]
) → AllocationResult:
    
    // Ordenar reservas: locked primero, luego por fecha de entrada
    sorted_reservations ← SORT(
        reservations,
        BY (NOT is_locked, check_in, -nights)
    )
    
    assignments ← {}
    unassigned ← []
    moved ← []
    
    occupancy_per_room ← { room.room_id: [] FOR room IN rooms }
    
    FOR res IN sorted_reservations:
        
        // 1. Si es locked, asignarla a su room actual
        IF res.is_locked:
            assignments[res.reservation_id] = res.current_room_id
            occupancy_per_room[res.current_room_id].append((res.check_in, res.check_out))
            CONTINUE
        
        // 2. Buscar mejor room según criterios
        best_room ← NULL
        best_score ← -∞
        
        FOR room IN rooms:
            IF room.category_id NOT IN res.effective_allowed_category_ids():
                CONTINUE
            
            // Verificar no-overlap
            can_fit ← TRUE
            FOR (check_in_existing, check_out_existing) IN occupancy_per_room[room.room_id]:
                IF overlap(res.check_in, res.check_out, check_in_existing, check_out_existing):
                    can_fit ← FALSE
                    BREAK
            
            IF NOT can_fit:
                CONTINUE
            
            // Calcular score
            score ← 0
            
            // Bonus por categoría exacta
            IF room.category_id == res.category_id:
                score += 1000
            ELSE:
                score -= res.category_priority(room.category_id) × 10
            
            // Bonus por continuidad (adjacent stays)
            adjacent_bonus ← _adjacency_bonus_for_room(res, occupancy_per_room[room.room_id])
            score += adjacent_bonus × 50
            
            // Penalidad por gaps
            gap_penalty ← _one_night_gap_penalty_for_room(res, occupancy_per_room[room.room_id])
            score -= gap_penalty × 25
            
            // Bonus por estabilidad
            IF res.current_room_id == room.room_id:
                score += 100
            
            IF score > best_score:
                best_score ← score
                best_room ← room
        
        IF best_room:
            assignments[res.reservation_id] = best_room.room_id
            occupancy_per_room[best_room.room_id].append((res.check_in, res.check_out))
            IF res.current_room_id ≠ best_room.room_id:
                moved.append(res.reservation_id)
        ELSE:
            unassigned.append(res.reservation_id)
    
    RETURN AllocationResult(
        success=len(unassigned) == 0,
        assignments=assignments,
        moved_reservations=moved,
        unassigned_reservations=unassigned,
        objective_value=ESTIMATE_OBJECTIVE(assignments, rooms, reservations)
    )
```

---

## 4. Movimiento de Reservas (Room Move)

### 4.1 Operación: Move Reservation Room

```pseudocode
FUNCTION move_reservation_room(
    db: Session,
    reservation: Reservation,
    to_room_id: int,
    hotel_id: int,
    moved_by_user_id: Optional[int] = None,
    reason_code: Optional[str] = None,
    notes: Optional[str] = None,
    move_type: RoomMoveTypeEnum = MANUAL_MOVE
) → RoomMoveEvent:
    
    // 1. Validar room destino
    to_room ← db.query(Room)
        .filter(Room.id == to_room_id, Room.hotel_id == hotel_id)
        .first()
    
    IF NOT to_room:
        RAISE ReservationOperationsError("Room destino no existe")
    
    // 2. Validar disponibilidad (sin overlaps)
    available ← check_room_availability(
        db,
        to_room_id,
        reservation.check_in_date,
        reservation.check_out_date,
        exclude_reservation_id=reservation.id
    )
    
    IF NOT available:
        RAISE ReservationOperationsError("Room destino no disponible para esas fechas")
    
    // 3. Realizar el movimiento
    from_room_id ← reservation.room_id
    reservation.room_id ← to_room.id
    reservation.category_id ← to_room.category_id
    
    // 4. Registrar evento de auditoría
    move_event ← NEW RoomMoveEvent(
        hotel_id=hotel_id,
        reservation_id=reservation.id,
        from_room_id=from_room_id,
        to_room_id=to_room.id,
        move_type=move_type,
        reason_code=reason_code,
        notes=notes,
        created_by_user_id=moved_by_user_id,
        created_at=NOW()
    )
    db.add(move_event)
    
    // 5. Registrar feedback para allocation policy
    record_manual_override_feedback(
        db,
        hotel_id=hotel_id,
        reservation_id=reservation.id,
        override_type="room_move",
        reason_code=reason_code,
        notes=notes OR f"Room move to {to_room.room_number}",
        created_by_user_id=moved_by_user_id
    )
    
    // 6. Flush cambios
    db.flush()
    
    RETURN move_event
```

### 4.2 Constraints de Movimiento

**Hard Constraints:**
- Room destino debe existir en el hotel
- Room destino no puede tener overlaps con la reserva en sus fechas
- Si `allocation_locked == TRUE` (checked_in), no permitir movimiento

**Soft Constraints:**
- Preferir room de la misma categoría
- Penalizar cambios de room frecuentes en corto plazo
- Bonificar upgrades si hay disponibilidad y el cliente lo solicita

### 4.3 Auditoría Completa

```
RoomMoveEvent registra:
  - Cuál room se movió
  - De qué room a cuál
  - Por qué (reason_code)
  - Quién lo ejecutó (user_id)
  - Cuándo
  
Posibles reason_codes:
  "guest_request" — cliente solicitó movimiento
  "damage" — habitación con daño descubierto
  "maintenance" — mantenimiento urgente
  "overbooking" — ajuste por error de asignación
  "optimization" — optimización automática
  "upgrade_offer" — oferta de upgrade gratuito
```

---

## 5. Máquina de Estados (State Machine)

### 5.1 Transiciones Válidas

```
PENDING
  ↓ (pago de depósito)
  ├→ DEPOSIT_PAID
  │   ↓ (pago final)
  │   └→ FULLY_PAID
  │       ├→ CHECKED_IN (si check_in date ≤ today)
  │       │   └→ CHECKED_OUT
  │       ├→ CANCELLED
  │       └→ NO_SHOW
  │
  ├→ FULLY_PAID (skip deposit)
  │   └→ (igual que arriba)
  │
  └→ CANCELLED (customer cancels before payment)

Terminal States:
  CHECKED_OUT — terminal absoluto
  CANCELLED — terminal (no hay vuelta atrás)
  NO_SHOW — terminal
```

### 5.2 Validación de Transiciones

```pseudocode
FUNCTION can_transition_to(
    current_status: ReservationStatusEnum,
    new_status: ReservationStatusEnum
) → bool:
    
    VALID_TRANSITIONS ← {
        PENDING: {DEPOSIT_PAID, FULLY_PAID, CANCELLED},
        DEPOSIT_PAID: {FULLY_PAID, CANCELLED},
        FULLY_PAID: {CHECKED_IN, CANCELLED, NO_SHOW},
        CHECKED_IN: {CHECKED_OUT},
        CHECKED_OUT: {},  // terminal
        CANCELLED: {},     // terminal
        NO_SHOW: {}        // terminal
    }
    
    // Guard: nunca pasar a NO_SHOW/CANCELLED después de check_in/out
    IF current_status IN {CHECKED_IN, CHECKED_OUT}:
        IF new_status IN {CANCELLED, NO_SHOW}:
            RETURN FALSE
    
    RETURN new_status IN VALID_TRANSITIONS[current_status]
```

---

## 6. Cálculo de Precios (Pricing)

### 6.1 Pipeline de Cálculo

```pseudocode
FUNCTION calculate_reservation_pricing(
    db: Session,
    category_id: int,
    check_in: date,
    check_out: date,
    hotel_id: Optional[int],
    sellable_product_id: Optional[int],
    rate_plan_id: Optional[int],
    tax_policy_id: Optional[int],
    pricing_channel_code: Optional[str],
    guest_scope: str = "all",
    target_currency: Optional[str],
    occupancy: Optional[int]
) → ReservationPricingResult:
    
    // 1. Validar category
    category ← db.query(RoomCategory).filter(RoomCategory.id == category_id).first()
    IF NOT category:
        RAISE ReservationError(f"Category {category_id} not found")
    
    hotel_id ← resolve_hotel_id(hotel_id, category)
    
    // 2. Calcular noches
    nights ← (check_out - check_in).days
    IF nights <= 0:
        RAISE ReservationError("Check-out debe ser después de check-in")
    
    // 3. Resolver contexto comercial
    (sellable_product, rate_plan, tax_policy) ← _resolve_reservation_commercial_context(
        db, hotel_id, category, sellable_product_id, rate_plan_id, tax_policy_id
    )
    
    // 4. Obtener quote (tasa nightly + totales)
    IF rate_plan:
        quote ← quote_rate_plan_stay(
            db,
            rate_plan,
            category,
            check_in,
            check_out,
            pricing_channel_code,
            guest_scope,
            target_currency,
            occupancy
        )
        nightly_rate ← quote.nightly_rate
        subtotal ← quote.subtotal
    ELSE:
        // Fallback a pricing por categoría
        nightly_rate ← category.base_nightly_rate
        subtotal ← nightly_rate × nights
    
    // 5. Aplicar políticas de impuestos
    IF tax_policy:
        tax_amount ← apply_tax_policy(tax_policy, subtotal)
    ELSE:
        tax_amount ← 0
    
    // 6. Calcular depósito
    deposit_amount ← compute_deposit_requirement(
        hotel_id, subtotal, tax_amount, nights, category
    )
    
    // 7. Calcular fee/commission (si aplica)
    fee_amount, commission_amount ← compute_fees_and_commissions(
        hotel_id, subtotal, source="direct" OR "ota"
    )
    
    // 8. Total
    total_amount ← subtotal + tax_amount + fee_amount
    net_amount ← subtotal + commission_amount
    
    RETURN ReservationPricingResult(
        nights=nights,
        nightly_rate=nightly_rate,
        total_amount=total_amount,
        deposit_amount=deposit_amount,
        subtotal_amount=subtotal,
        tax_amount=tax_amount,
        fee_amount=fee_amount,
        commission_amount=commission_amount,
        net_amount=net_amount,
        currency_code=target_currency OR hotel.default_currency,
        fx_rate_snapshot=get_current_fx_rate(...),
        pricing_source="rate_plan" OR "category_default",
        sellable_product_id=sellable_product?.id,
        rate_plan_id=rate_plan?.id,
        tax_policy_id=tax_policy?.id,
        pricing_snapshot=json.dumps({...})
    )
```

### 6.2 Políticas Comerciales

```
Deposit Policy:
  - Percentage of subtotal (e.g., 30%)
  - Fixed amount per night (e.g., ARS 5000/night)
  - Full prepayment for certain channels (OTA)

Tax Policy:
  - VAT (IVA) por jurisdicción (AR: 21%)
  - Municipal tax
  - Tourism tax
  
Fee Structure:
  - OTA comisión (Booking: 15%, Expedia: 20%)
  - Payment gateway fee (MercadoPago: 2.99% + ARS 3)
  - Admin fee (si aplica)

Currency Conversion:
  - FX snapshot al momento de crear reserva
  - Used para conversión backwards si guest paga en otra moneda
```

---

## 7. Manejo de Transacciones (ACID)

### 7.1 Pessimistic Locking

```pseudocode
FUNCTION create_reservation_atomic(
    db: Session,
    hotel_id: int,
    guest_data: GuestCreate,
    reservation_data: ReservationCreate,
    ...
) → Reservation:
    
    TRY:
        // 1. Bloquear room (si es especificado)
        IF reservation_data.preferred_room_id:
            room ← db.query(Room)
                .with_for_update()  // Pessimistic lock
                .filter(Room.id == reservation_data.preferred_room_id)
                .first()
            
            // Validar disponibilidad bajo lock
            IF NOT check_room_availability(...):
                RAISE ReservationError("Room no disponible")
        
        // 2. Bloquear category para verificar disponibilidad
        category ← db.query(RoomCategory)
            .with_for_update()
            .filter(RoomCategory.id == reservation_data.category_id)
            .first()
        
        // 3. Crear guest
        guest ← create_or_update_guest(db, guest_data)
        
        // 4. Calcular pricing
        pricing ← calculate_reservation_pricing(db, ...)
        
        // 5. Crear reserva
        reservation ← NEW Reservation(
            hotel_id=hotel_id,
            guest_id=guest.id,
            room_id=room.id IF preferred ELSE NULL,
            category_id=category.id,
            check_in_date=reservation_data.check_in,
            check_out_date=reservation_data.check_out,
            total_amount=pricing.total_amount,
            deposit_amount=pricing.deposit_amount,
            status=PENDING,
            confirmation_code=generate_confirmation_code(),
            ...
        )
        db.add(reservation)
        
        // 6. Crear history entry
        history ← NEW ReservationStatusHistory(
            reservation_id=reservation.id,
            from_status=None,
            to_status=PENDING,
            changed_at=NOW(),
            changed_by_user_id=current_user.id,
            reason="Initial creation"
        )
        db.add(history)
        
        // 7. Commit (libera locks)
        db.commit()
        
        RETURN reservation
        
    CATCH Exception AS e:
        db.rollback()
        RAISE ReservationError(f"Failed to create reservation: {e}")
```

### 7.2 Isolation Level

```
SERIALIZABLE:
  - Máximo aislamiento
  - Previene race conditions
  - Posible contención en alta concurrencia
  
REPEATABLE_READ (PostgreSQL):
  - Buen balance
  - Previene lost updates
  - Permite dirty reads de datos old (aceptable para PMS)

Recomendación: REPEATABLE_READ para la mayoría de operaciones,
SERIALIZABLE solo para crear/cancelar reservas.
```

---

## 8. APIs y Schemas

### 8.1 Crear Reserva

```
POST /api/hotels/{hotel_id}/reservations

Request Body:
{
  "guest": {
    "first_name": "Juan",
    "last_name": "Pérez",
    "email": "juan@example.com",
    "phone": "+541122334455",
    "country_code": "AR"
  },
  "check_in_date": "2026-07-01",
  "check_out_date": "2026-07-05",
  "category_id": 3,
  "num_adults": 2,
  "num_children": 1,
  "rate_plan_id": 12,
  "channel_code": "website_direct",
  "notes": "Guest is VIP"
}

Response (201):
{
  "id": 1234,
  "confirmation_code": "RES-ABCD1234",
  "hotel_id": 1,
  "guest_id": 567,
  "status": "pending",
  "check_in_date": "2026-07-01",
  "check_out_date": "2026-07-05",
  "total_amount": 45000.0,
  "amount_paid": 0.0,
  "deposit_amount": 13500.0,
  "balance_due": 45000.0,
  "created_at": "2026-06-09T10:30:00Z"
}
```

### 8.2 Transicionar Estado

```
PATCH /api/hotels/{hotel_id}/reservations/{id}/status

Request Body:
{
  "new_status": "deposit_paid",
  "payment_method": "mercado_pago",
  "transaction_id": "TXN-123456"
}

Response (200):
{
  "id": 1234,
  "status": "deposit_paid",
  "amount_paid": 13500.0,
  "balance_due": 31500.0,
  "updated_at": "2026-06-09T10:35:00Z",
  "transitions": [
    {
      "from_status": "pending",
      "to_status": "deposit_paid",
      "changed_at": "2026-06-09T10:35:00Z"
    }
  ]
}
```

### 8.3 Mover Habitación

```
POST /api/hotels/{hotel_id}/reservations/{id}/move-room

Request Body:
{
  "to_room_id": 245,
  "reason_code": "guest_request",
  "notes": "Guest requested higher floor",
  "moved_by_user_id": 100
}

Response (200):
{
  "move_event": {
    "id": 888,
    "reservation_id": 1234,
    "from_room_id": 101,
    "to_room_id": 245,
    "move_type": "manual_move",
    "reason_code": "guest_request",
    "created_at": "2026-06-09T10:40:00Z"
  },
  "reservation": {
    "id": 1234,
    "room_id": 245,
    "category_id": 3
  }
}
```

### 8.4 Ejecutar Optimización Global

```
POST /api/hotels/{hotel_id}/reservations/optimize

Query Params:
  ?start_date=2026-07-01&end_date=2026-07-31
  ?include_locked=false  (default: true, respeta checked-in)
  ?max_time_seconds=30   (timeout del solver)

Request Body (opcional):
{
  "policy_constraints": {
    "max_category_upgrades": 5,
    "min_occupancy_threshold": 0.8
  },
  "policy_weights": {
    "minimize_one_night_gaps": 100,
    "stability": 5,
    "prefer_exact_match": 500,
    "unassigned_penalty": 10000
  }
}

Response (200):
{
  "success": true,
  "assignments": {
    "1234": 101,
    "1235": 203,
    ...
  },
  "moved_reservations": [1234, 1236],
  "unassigned_reservations": [],
  "objective_value": 45230.5,
  "solver_stats": {
    "wall_time_ms": 12500,
    "gap": 0.02,
    "status": "FEASIBLE"
  },
  "summary": {
    "total_reservations": 47,
    "assigned": 47,
    "moved": 2,
    "unassigned": 0,
    "occupancy_rate": 0.92
  }
}
```

---

## 9. Casos de Uso Operacionales

### 9.1 Nuevo Guest + Asignación Automática

```
1. POST /reservations con (guest_id, category_id, dates, ...)
2. Sistema genera confirmation_code
3. Room asignado automáticamente por allocation_engine
   (o dejado NULL si es pre-assignment workflow)
4. Status = PENDING, awaiting payment
5. Cuando llega pago → DEPOSIT_PAID o FULLY_PAID
```

### 9.2 Movimiento Manual (Front Desk)

```
1. Guest llama: "Puedo cambiar a un room más tranquilo?"
2. Receptionist busca disponibilidad
3. POST /reservations/{id}/move-room
   con to_room_id, reason_code="guest_request"
4. Sistema valida:
   - room destino no existe? Error
   - room ocupado en esas fechas? Error
   - si está checked_in? Error (locked)
5. Si OK: actualiza room_id, crea RoomMoveEvent
6. Log automático para tracking
```

### 9.3 Optimización Nocturna (Batch)

```
1. Schedule task @ 2am: POST /reservations/optimize
2. Parámetros:
   - horizon: today + 7 days (near future)
   - include_locked: true (respeta checked-in)
3. CP-SAT solver:
   - Asigna pending/unassigned
   - Mueve algunos assigned si mejora fitness
4. Resultado:
   - moved_reservations: crea RoomMoveEvent con reason="optimization"
   - unassigned_reservations: alert para manual review
5. Frontend muestra cambios:
   - "5 rooms relocated for better occupancy"
   - link a changelog con motivos
```

### 9.4 OTA Rebook (Cambiar de canal)

```
1. Booking.com reserva originalmente en category deluxe
2. Guest contacta: "Prefiero presupuesto. ¿Puedo standard?"
3. POST /reservations/{id}/ota-rebook-as-direct
   {
     "target_category_id": 1,  // standard
     "target_rate_plan_id": 5
   }
4. Sistema:
   - Calcula nuevo precio (con rate plan directo, no OTA)
   - Crea ReservationAdjustment (draft)
   - Calcula refund/surcharge (BillingAdjustment)
5. Manager revisa en UI, aprueba
6. Sistema:
   - Crea nueva Reservation (direct, standard)
   - Cancela la original de OTA (con reason="rebooked_as_direct")
   - Registra cambio en audit trail
```

### 9.5 Cancelación con Auditoría

```
1. PATCH /reservations/{id}/status
   {
     "new_status": "cancelled",
     "reason_code": "guest_request",
     "cancellation_reason_note": "Guest's business trip cancelled"
   }
2. Validaciones:
   - Si status=CHECKED_OUT → ERROR (terminal)
   - Si status=CHECKED_IN → puede cancelar con penalty
3. Cambios:
   - status → CANCELLED
   - cancelled_at ← NOW()
   - cancelled_by_user_id ← current_user.id
4. Financial:
   - Calcular refund según cancellation policy
   - Crear BillingAdjustment (refund o retention)
   - Procesar reembolso si amount_paid > 0
5. Operacional:
   - Room queda libre
   - Re-run optimization en esa habitación (si hay time)
```

---

## 10. Testing Strategy

### 10.1 Unit Tests (allocation_engine.py)

```
test_cp_sat_exact_match()
  - 5 reservas, 5 rooms, 1:1 match
  - Espera: todas asignadas, ninguna movida
  
test_cp_sat_fragmentation_penalty()
  - 3 reservas: [1-5], [6-10], [12-16]
  - Room: vacío
  - Espera: todas en mismo room, gap penalty mínimo
  
test_cp_sat_category_mismatch()
  - Reserva pide category_id=2
  - Solo rooms disponibles: category_id=3 (upgrade)
  - Espera: asignada con penalty en objective, pero assigned=true
  
test_cp_sat_locked_reservation()
  - Reserva checked_in en room 101
  - Espera: x[res, room101] = 1, no puede mover
  
test_cp_sat_infeasible()
  - 10 reservas overlapping, 1 room
  - Espera: unassigned_reservations no vacía
  
test_greedy_fallback()
  - Sin OR-Tools, fallback a greedy
  - Espera: assignments completos (aunque no óptimos)
```

### 10.2 Integration Tests (reservation_service.py)

```
test_create_reservation_with_automatic_assignment()
  - POST /reservations
  - Espera: reserva creada, room_id asignado o NULL
  
test_move_room_updates_audit_trail()
  - Crear reserva
  - POST /move-room
  - Espera: RoomMoveEvent en DB, reason_code registrado
  
test_state_machine_valid_transitions()
  - PENDING → DEPOSIT_PAID → FULLY_PAID → CHECKED_IN → CHECKED_OUT
  - Espera: cada transición crea StatusHistory
  
test_state_machine_invalid_transitions()
  - CHECKED_OUT → CANCELLED
  - Espera: ERROR, transición rechazada
  
test_pricing_with_tax_and_fees()
  - category=deluxe, nights=3, rate_plan=weekend
  - Espera: total = subtotal + tax + fee, deposit = 30%
  
test_pessimistic_locking_prevents_overbooking()
  - Thread 1 y Thread 2 crean reservas para mismo room/dates
  - Espera: solo 1 succeed, otro get error
```

### 10.3 End-to-End Tests

```
test_full_booking_workflow()
  - Crear guest
  - Crear reserva pending
  - Simular pago → DEPOSIT_PAID
  - Simular pago final → FULLY_PAID
  - Check-in → CHECKED_IN
  - Check-out → CHECKED_OUT
  - Espera: cada transición registrada

test_optimization_with_real_data()
  - Load 100 reservas de fixture
  - Ejecutar /optimize
  - Espera: resultado en < 30s, feasible, objective > 0
  
test_ota_rebook_workflow()
  - Crear reserva OTA
  - POST /ota-rebook-as-direct
  - Espera: original CANCELLED, new en PENDING
```

---

## 11. Métricas y Observabilidad

### 11.1 Métricas Clave

```
AllocationMetrics:
  - Tasa de asignación exitosa (%)
  - Tasa de movimientos por optimización (%)
  - Ocupancia promedio (%)
  - Gap de optimalidad CP-SAT (%)
  - Tiempo de ejecución solver (ms)
  - Fragmentación (gaps de 1 noche detectados)
  
ReservationMetrics:
  - Tasa de conversión (pending → deposit_paid)
  - Tiempo promedio hasta check-in
  - Tasa de cancellation por fase (pending, deposit, fully_paid)
  - Refund amount total
  
FinancialMetrics:
  - Revenue por channel (Booking, Direct, etc.)
  - Average room rate
  - RevPAR (Revenue Per Available Room)
  - Commission acumulado
```

### 11.2 Logging

```
allocation_engine.py:
  - DEBUG: x[r_idx, h_idx] assignments detallados
  - INFO: Final assignments, unassigned count
  - WARN: Time limit reached, using feasible solution
  - ERROR: Solver failure, fallback to greedy
  
reservation_service.py:
  - INFO: Reservation created {confirmation_code}
  - WARN: Transition to cancelled, amount paid {amount}
  - ERROR: Check-in failed, guest not validated
  
reservation_operations_service.py:
  - INFO: Room move from {from_room} to {to_room}
  - AUDIT: Recorded by user {user_id}, reason {reason}
```

---

## 12. Seguridad y Compliance

### 12.1 Validaciones de Seguridad

```
✓ Multi-hotel isolation: sempre filtrar por hotel_id
✓ Permission checks: user rol verificado antes de move/cancel
✓ Data sanitization: reason_note truncado a 500 chars
✓ Rate limiting: max 10 creaciones/min por hotel
✓ Soft delete: nunca borrar reservas, marcar como cancelled
✓ Audit trail: todos los cambios registrados
```

### 12.2 Cumplimiento Regulatorio

```
Argentina:
  - IVA registrado en cada transacción
  - Registro de huéspedes (DDJJ) completado at check-in
  - Cancelaciones >= 48hs antes de arrival → full refund
  - Depósito mínimo 30% o fecha arrival - 2 days

OTA Compliance:
  - Sync status con Booking/Expedia cada 15min
  - Overbooking cancellation refund inmediato
  - Commission registrado separadamente (audit)
```

---

## 13. Roadmap Futuro

### Fase 2 (Post-MVP)
- [ ] Machine Learning para predictive pricing
- [ ] Algoritmo de upgrade automático (match guest preferences)
- [ ] Revenue management: dynamic pricing por demanda
- [ ] Integration con housekeeping (status de limpieza)

### Fase 3
- [ ] Batch operations (cancel 50 reservas por channel)
- [ ] Revenue forecasting dashboard
- [ ] Guest analytics (repeat customer, LTV)

---

## Conclusión

Este diseño proporciona:

1. **Robustez**: CP-SAT + pessimistic locking previene overbooking
2. **Flexibilidad**: Greedy fallback si OR-Tools no disponible
3. **Auditabilidad**: Cada cambio registrado con user_id y timestamp
4. **Performance**: Indexación y queries optimizadas
5. **Escalabilidad**: Multi-hotel, transacciones aisladas
6. **UX**: APIs claras, feedback inmediato al usuario

El sistema maneja:
- 1000+ reservas simultáneamente
- Cambios de asignación automáticos
- Movimientos manuales con trail completo
- Estados de pago complejos
- Integración OTA fluida

```
