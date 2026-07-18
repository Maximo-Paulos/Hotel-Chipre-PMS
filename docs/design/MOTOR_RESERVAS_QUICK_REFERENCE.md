# Motor de Reservas — Quick Reference para Desarrolladores

## 1. Estructura de Archivos

```
app/
├── models/
│   ├── reservation.py          # Reservation, ReservationStatusEnum
│   └── operations.py           # RoomMoveEvent, ReservationAdjustment, BillingAdjustment
├── services/
│   ├── allocation_engine.py    # run_allocation(), _run_allocation_greedy()
│   ├── reservation_service.py  # create_reservation(), calculate_pricing()
│   └── reservation_operations_service.py  # move_reservation_room(), ota_rebook
├── schemas/
│   ├── reservation.py          # ReservationCreate, ReservationUpdate
│   └── allocation.py           # AllocationResult, RoomMoveIntent
└── routes/
    └── reservations.py         # POST/PATCH/DELETE endpoints
```

---

## 2. Funciones Clave

### 2.1 Crear Reserva

```python
# app/services/reservation_service.py
def create_reservation(
    db: Session,
    guest_id: int,
    category_id: int,
    check_in_date: date,
    check_out_date: date,
    hotel_id: int,
    rate_plan_id: Optional[int] = None,
    num_adults: int = 1,
    num_children: int = 0
) -> Reservation:
    """Create pending reservation with automatic pricing."""
    pass

# app/routes/reservations.py
@router.post("/hotels/{hotel_id}/reservations")
def create_booking(hotel_id: int, req: ReservationCreate):
    return create_reservation(db, ...)
```

### 2.2 Optimizar Asignación

```python
# app/services/allocation_engine.py
def run_allocation(
    reservations: list[ReservationSlot],
    rooms: list[RoomSlot],
    optimization_horizon: Optional[tuple[date, date]] = None,
    policy_weights: Optional[dict] = None
) -> AllocationResult:
    """CP-SAT solver para asignación óptima."""
    pass

# app/routes/reservations.py
@router.post("/hotels/{hotel_id}/reservations/optimize")
def optimize_allocation(hotel_id: int):
    """Run optimization, apply assignments, return result."""
    pass
```

### 2.3 Mover Habitación

```python
# app/services/reservation_operations_service.py
def move_reservation_room(
    db: Session,
    reservation: Reservation,
    to_room_id: int,
    hotel_id: int,
    moved_by_user_id: Optional[int] = None,
    reason_code: Optional[str] = None
) -> RoomMoveEvent:
    """Move reservation atomically with audit trail."""
    pass

# app/routes/reservations.py
@router.post("/hotels/{hotel_id}/reservations/{id}/move-room")
def move_room(hotel_id: int, id: int, intent: RoomMoveIntent):
    """Execute room move with validation."""
    pass
```

### 2.4 Transicionar Estado

```python
# app/services/reservation_service.py
def transition_reservation_status(
    db: Session,
    reservation: Reservation,
    new_status: ReservationStatusEnum,
    transition_reason: str,
    transitioned_by_user_id: Optional[int] = None
) -> bool:
    """Move reservation through state machine."""
    pass

# app/routes/reservations.py
@router.patch("/hotels/{hotel_id}/reservations/{id}/status")
def change_status(hotel_id: int, id: int, req: StatusChangeRequest):
    """Validate and transition."""
    pass
```

---

## 3. Estructura de Datos

### 3.1 ReservationSlot (entrada CP-SAT)

```python
@dataclass
class ReservationSlot:
    reservation_id: int
    category_id: int
    check_in: date
    check_out: date
    current_room_id: Optional[int]
    is_locked: bool                      # True si checked_in
    allowed_category_ids: list[int] = field(default_factory=list)
```

### 3.2 AllocationResult (salida CP-SAT)

```python
@dataclass
class AllocationResult:
    success: bool
    assignments: dict[int, int]          # reservation_id → room_id
    moved_reservations: list[int]
    unassigned_reservations: list[int]
    objective_value: float
    solver_status: str                   # "OPTIMAL" | "FEASIBLE" | "INFEASIBLE"
```

### 3.3 RoomMoveEvent (auditoría)

```python
class RoomMoveEvent(Base):
    __tablename__ = "room_move_events"
    
    id: int
    reservation_id: int (FK)
    from_room_id: Optional[int]
    to_room_id: int
    move_type: RoomMoveTypeEnum          # MANUAL, OPTIMIZATION, UPGRADE
    reason_code: Optional[str]           # guest_request, damage, optimization
    notes: Optional[str]
    created_by_user_id: Optional[int]
    created_at: datetime
```

---

## 4. Estado Machine Simplificado

```
        ┌─→ DEPOSIT_PAID ─→ FULLY_PAID ─→ CHECKED_IN ─→ CHECKED_OUT
        │                                      ↓
PENDING ├─────────────→ FULLY_PAID (skip deposit)
        │
        ├─→ CANCELLED (refund)
        │
        └─→ NO_SHOW (if fully paid)
```

**Transición:**
```python
# Validar
is_valid, error = validate_transition(current_status, new_status)
if not is_valid: raise ReservationError(error)

# Ejecutar
success = transition_reservation_status(
    db, reservation, new_status,
    transition_reason="Payment received",
    transitioned_by_user_id=user_id
)
```

---

## 5. Patrón de Transacción Pessimistic

```python
# ✓ Correcto (con lock)
def create_reservation_safe(db, ...):
    try:
        # Bloquear recursos
        room = db.query(Room)\
            .with_for_update()\
            .filter(Room.id == preferred_room_id)\
            .first()
        
        category = db.query(RoomCategory)\
            .with_for_update()\
            .filter(RoomCategory.id == category_id)\
            .first()
        
        # Crear entidades
        reservation = Reservation(...)
        db.add(reservation)
        
        # Commit (libera locks)
        db.commit()
        return reservation
        
    except Exception as e:
        db.rollback()
        raise ReservationError(str(e))

# ✗ Incorrecto (sin lock)
def create_reservation_unsafe(db, ...):
    # RACE CONDITION RISK
    room = db.query(Room).filter(...).first()
    if room:  # Check-then-act
        # Another thread could book room here!
        reservation = Reservation(room_id=room.id)
        db.add(reservation)
        db.commit()
```

---

## 6. Tuning del CP-SAT

```python
# Pesos de penalidad (ajustar según necesidad)
policy_weights = {
    "minimize_one_night_gaps": 100,      # Fragmentación
    "stability": 5,                       # Estabilidad
    "prefer_exact_match": 500,            # Evitar upgrades
    "unassigned_penalty": 10_000,         # Asignaciones
    "room_usage_penalty": 50              # Uso de salas
}

# Timeout
max_solver_time_seconds = 30

# Para test rápido: reduce timeout y aumenta stability
# Para optimización nocturna: aumenta timeout y reduce stability
```

**Efectos:**
- **Aumentar `unassigned_penalty`:** Fuerza más asignaciones
- **Aumentar `prefer_exact_match`:** Evita upgrades innecesarios
- **Aumentar `stability`:** Menos movimientos
- **Aumentar `minimize_one_night_gaps`:** Mejor continuidad

---

## 7. APIs Rápidas

### Crear Reserva
```bash
POST /api/hotels/1/reservations
{
  "guest": {
    "first_name": "Juan",
    "email": "juan@example.com"
  },
  "check_in_date": "2026-07-01",
  "check_out_date": "2026-07-05",
  "category_id": 3,
  "num_adults": 2
}
```

### Cambiar Estado
```bash
PATCH /api/hotels/1/reservations/1234/status
{
  "new_status": "deposit_paid",
  "reason": "Payment received"
}
```

### Mover Habitación
```bash
POST /api/hotels/1/reservations/1234/move-room
{
  "to_room_id": 245,
  "reason_code": "guest_request"
}
```

### Optimizar
```bash
POST /api/hotels/1/reservations/optimize?start_date=2026-07-01&end_date=2026-07-31
{
  "policy_weights": {
    "minimize_one_night_gaps": 100
  }
}
```

---

## 8. Validaciones Críticas

```python
# ✓ Validar antes de crear
def create_reservation_validated(db, req):
    # 1. Guest válido
    guest = validate_or_create_guest(req.guest)
    
    # 2. Category existe
    category = db.query(RoomCategory).get(req.category_id)
    if not category:
        raise ValueError("Category not found")
    
    # 3. Fechas válidas
    if req.check_out <= req.check_in:
        raise ValueError("Invalid dates")
    
    # 4. Pricing calculable
    pricing = calculate_reservation_pricing(db, req.category_id, ...)
    
    # 5. Crear
    return create_reservation(db, guest_id, category_id, ...)

# ✓ Validar antes de mover
def move_room_validated(db, res, to_room_id, hotel_id):
    # 1. Reserva existe y pertenece a hotel
    if res.hotel_id != hotel_id:
        raise ValueError("Wrong hotel")
    
    # 2. No locked (checked_in)
    if res.status == ReservationStatusEnum.CHECKED_IN:
        raise ValueError("Cannot move checked-in")
    
    # 3. Room existe
    to_room = db.query(Room).get(to_room_id)
    if not to_room:
        raise ValueError("Room not found")
    
    # 4. Room disponible
    conflicts = db.query(Reservation).filter(
        Reservation.room_id == to_room_id,
        Reservation.id != res.id,
        Reservation.check_in_date < res.check_out_date,
        Reservation.check_out_date > res.check_in_date,
        Reservation.status.in_([ReservationStatusEnum.CHECKED_IN, ReservationStatusEnum.FULLY_PAID])
    ).count()
    
    if conflicts > 0:
        raise ValueError("Room occupied")
    
    # 5. Mover
    return execute_room_move(db, res, to_room_id, ...)
```

---

## 9. Debugging

### Ver estado de reserva
```python
# app/services/reservation_service.py
def get_reservation_detail(db, reservation_id):
    res = db.query(Reservation).get(reservation_id)
    history = db.query(ReservationStatusHistory)\
        .filter_by(reservation_id=reservation_id)\
        .order_by(ReservationStatusHistory.changed_at.desc())\
        .all()
    moves = db.query(RoomMoveEvent)\
        .filter_by(reservation_id=reservation_id)\
        .order_by(RoomMoveEvent.created_at.desc())\
        .all()
    
    return {
        "reservation": res,
        "status_history": history,
        "room_moves": moves
    }
```

### Ver ocupancia
```python
# app/services/allocation_engine.py
def get_room_occupancy(db, room_id, start_date, end_date):
    stays = db.query(Reservation)\
        .filter(
            Reservation.room_id == room_id,
            Reservation.check_in_date < end_date,
            Reservation.check_out_date > start_date,
            Reservation.status.in_([
                ReservationStatusEnum.CHECKED_IN,
                ReservationStatusEnum.FULLY_PAID,
                ReservationStatusEnum.CHECKED_OUT
            ])
        ).order_by(Reservation.check_in_date)\
        .all()
    
    return {
        "room_id": room_id,
        "stays": [(r.confirmation_code, r.check_in_date, r.check_out_date) for r in stays]
    }
```

---

## 10. Testing Cheat Sheet

### Setup Fixtures
```python
@pytest.fixture
def hotel(db):
    return create_hotel(db, name="Test Hotel")

@pytest.fixture
def guest(db):
    return create_guest(db, email="test@example.com")

@pytest.fixture
def category(db, hotel):
    return create_room_category(db, hotel_id=hotel.id, name="Standard")

@pytest.fixture
def room(db, category):
    return create_room(db, category_id=category.id, room_number="101")
```

### Test Básico
```python
def test_create_reservation_pending(db, hotel, guest, category):
    res = create_reservation(
        db,
        guest_id=guest.id,
        category_id=category.id,
        check_in_date=date(2026, 7, 1),
        check_out_date=date(2026, 7, 5),
        hotel_id=hotel.id
    )
    
    assert res.status == ReservationStatusEnum.PENDING
    assert res.confirmation_code
    assert res.total_amount > 0
```

### Test Move
```python
def test_move_room_creates_event(db, hotel, guest, category, room):
    res = create_reservation(db, guest_id=guest.id, ...)
    room2 = create_room(db, category_id=category.id, room_number="102")
    
    event = move_reservation_room(
        db,
        reservation=res,
        to_room_id=room2.id,
        hotel_id=hotel.id,
        reason_code="guest_request"
    )
    
    assert res.room_id == room2.id
    assert event.from_room_id == None or == room.id
    assert event.reason_code == "guest_request"
```

---

## 11. Logging

```python
import logging

logger = logging.getLogger(__name__)

# En allocation_engine.py
logger.info(f"Optimizing {len(reservations)} reservations")
logger.debug(f"Solver status: {status_str}, wall_time: {elapsed_ms}ms")
logger.warning(f"Unassigned: {len(unassigned)} reservations")
logger.error(f"CP-SAT failed: {error}")

# En reservation_service.py
logger.info(f"Reservation created: {confirmation_code}")
logger.warning(f"Low room availability: {available_count} rooms")
logger.error(f"Pricing calculation failed: {exception}")

# En reservation_operations_service.py
logger.info(f"Room move: {reservation_id} {from_room} → {to_room}")
logger.audit(f"Move recorded: reason={reason_code}, user={user_id}")
```

---

## 12. Performance Checklist

- [ ] ¿Todos los queries tienen índices? (`ix_reservation_dates`, `ix_reservation_hotel_id`)
- [ ] ¿Pessimistic lock en creación de reserva?
- [ ] ¿CP-SAT timeout configurado? (default: 30s)
- [ ] ¿Greedy fallback si OR-Tools no disponible?
- [ ] ¿Logging estructurado con JSON?
- [ ] ¿Métricas de solver (gap, tiempo, status)?
- [ ] ¿Batch operations (no 1 por 1)?
- [ ] ¿Caché de room occupancy?

---

## 13. Common Errors & Fixes

| Error | Causa | Fix |
|-------|-------|-----|
| `ReservationError: check-out must be after check-in` | Fechas invertidas | Validar check_out > check_in |
| `ReservationError: Room not found` | Room no existe | Verificar room_id existe en hotel |
| `ReservationOperationsError: Room occupied` | Overlap en fechas | check_room_availability() |
| `ReservationError: Cannot move checked-in` | Reservation locked | Solo desbloquear si not CHECKED_IN |
| `IntegrityError: duplicate key` | Confirmation code repetido | generate_confirmation_code() debería ser único |
| `CP-SAT timeout` | Problema muy grande | Reducir horizon o aumentar workers |

---

## 14. Roadmap de Implementación

1. **Semana 1:** Models + Services (reservation_service, allocation_engine)
2. **Semana 2:** APIs básicas (create, status, optimize)
3. **Semana 3:** Room moves + Auditoría
4. **Semana 4:** Testing + Tuning de pesos

---

## 15. Recursos

- **Documentación Principal:** `MOTOR_RESERVAS_DESIGN.md`
- **Pseudocódigo Detallado:** `MOTOR_RESERVAS_PSEUDOCODE.md`
- **Summary (JSON):** `MOTOR_RESERVAS_SUMMARY.json`
- **OR-Tools Docs:** https://developers.google.com/optimization/cp/cp_solver
- **Grafo técnico:** Ver `.graphify/graph.json`

---

**Última actualización:** 2026-06-09  
**Versión:** 1.0  
**Status:** Ready for Implementation
