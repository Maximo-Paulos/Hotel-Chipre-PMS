# Módulo Motor de Reservas — Índice Maestro

## Documentos Generados

### 1. **MOTOR_RESERVAS_DESIGN.md** (42.6 KB)
**Propósito:** Documentación técnica completa y arquitectura.

**Contenido:**
- Visión general y arquitectura en 3 capas
- Modelo de datos completo (Reservation, RoomMoveEvent, ReservationAdjustment)
- Formulación matemática del CP-SAT (variables, constraints, objetivo)
- Pseudocódigo principal del algoritmo
- Fallback greedy (sin OR-Tools)
- Sistema de movimiento de reservas (validación, ejecución, auditoría)
- Máquina de estados (7 estados, transiciones válidas)
- Pipeline de cálculo de precios
- Manejo de transacciones ACID (pessimistic locking)
- APIs REST documentadas
- 5 casos de uso operacionales
- Testing strategy (unit, integration, E2E)
- Métricas y observabilidad
- Seguridad y cumplimiento normativo (Argentina, OTA)
- Roadmap futuro (fases 2-3)

**Para quién:** Arquitectos, lead developers, product managers

**Cómo usarlo:** Leer para entender diseño global, compartir con stakeholders

---

### 2. **MOTOR_RESERVAS_PSEUDOCODE.md** (47.0 KB)
**Propósito:** Implementación detallada en pseudocódigo, lista para traducir a código.

**Contenido:**
- Estructuras de datos clave:
  - `ReservationSlot` — Entrada del solver
  - `RoomSlot` — Recursos disponibles
  - `AllocationResult` — Salida del solver
  - `RoomMoveIntent` — Solicitud de movimiento
- **Función principal `run_allocation()`** — Pseudocódigo completo con:
  - Validaciones y early exits
  - Carga de librerías
  - Extracción de parámetros
  - Cálculo de horizonte de optimización
  - Creación del modelo CP-SAT
  - Definición de variables de decisión
  - Constraints duros (1-4)
  - Soft constraints (gap penalties, estabilidad)
  - Función objetivo (5 términos)
  - Configuración y ejecución del solver
  - Procesamiento de resultado
- **Fallback greedy** — Algoritmo alternativo sin OR-Tools
- **Room move execution** — Validación atomic y ejecución
- **State machine transitions** — Validators y transiciones
- **Testing strategies** — Unit, integration, E2E con fixtures

**Para quién:** Developers (Python/FastAPI), code reviewers

**Cómo usarlo:** Copiar pseudocódigo línea por línea a Python, adaptar sintaxis

---

### 3. **MOTOR_RESERVAS_SUMMARY.json** (18.2 KB)
**Propósito:** Resumen ejecutivo estructurado en JSON, fácil para parsing programático.

**Contenido:**
- Resumen ejecutivo (objetivo, documentos)
- Arquitectura (4 capas: API, Service, Optimization, Persistence)
- Algoritmo CP-SAT (variables, constraints duros/blandos, tuning)
- Movimiento de reservas (flujo, constraints, auditoría)
- Máquina de estados (7 estados, transiciones válidas, side effects)
- Pricing (pipeline, componentes, políticas)
- Transacciones ACID (isolation level, locking strategy)
- APIs (4 endpoints principales con ejemplos)
- 5 casos de uso descritos
- Testing (unit, integration)
- Métricas y observabilidad (allocation, reservation, financial)
- Seguridad y compliance (Argentina, OTA)
- Stack (FastAPI, SQLAlchemy, OR-Tools)
- Roadmap futuro
- Conclusiones

**Para quién:** PMs, QA, frontend developers, documentation

**Cómo usarlo:** Referencia rápida, fuente de verdad para specs, compartir c/ equipos

---

### 4. **MOTOR_RESERVAS_QUICK_REFERENCE.md** (14.6 KB)
**Propósito:** Cheat sheet para developers, referencia rápida en el IDE.

**Contenido:**
- Estructura de archivos (dónde va cada función)
- Funciones clave (4 principales con ejemplos)
- Estructuras de datos (3 principales)
- State machine simplificado (diagrama)
- Patrón pessimistic locking (correcto vs incorrecto)
- Tuning de CP-SAT (pesos y efectos)
- APIs rápidas (curl examples)
- Validaciones críticas (qué revisar antes de crear/mover)
- Debugging (ver estado de reserva, ocupancia)
- Testing cheat sheet (fixtures, tests básicos)
- Logging (dónde y cómo)
- Performance checklist (12 items)
- Common errors & fixes (tabla)
- Roadmap de implementación (4 semanas)
- Recursos (links a otros docs)

**Para quién:** Developers durante implementación

**Cómo usarlo:** Pegarlo al lado del IDE, consultar constantemente

---

### 5. **MOTOR_RESERVAS_INDEX.md** (Este archivo)
**Propósito:** Índice y guía de navegación entre documentos.

**Contenido:**
- Descripción de cada documento
- Qué contiene
- Para quién es
- Cómo usarlo
- Roadmap de lectura

---

## Roadmap de Lectura

### Escenario 1: Entender el Sistema Completo
1. Lee `MOTOR_RESERVAS_SUMMARY.json` (15 min) — Overview general
2. Lee `MOTOR_RESERVAS_DESIGN.md` (1 hora) — Arquitectura profunda
3. Consulta `MOTOR_RESERVAS_PSEUDOCODE.md` (30 min) — Detalles técnicos
4. Guarda `MOTOR_RESERVAS_QUICK_REFERENCE.md` para referencia

### Escenario 2: Implementar el Código
1. Consulta `MOTOR_RESERVAS_QUICK_REFERENCE.md` — Estructura de archivos
2. Lee `MOTOR_RESERVAS_PSEUDOCODE.md` — Pseudocódigo a traducir
3. Verifica `MOTOR_RESERVAS_DESIGN.md` — Constraints y edge cases
4. Usa `MOTOR_RESERVAS_SUMMARY.json` para specs

### Escenario 3: Code Review
1. Lee `MOTOR_RESERVAS_PSEUDOCODE.md` (función en cuestión)
2. Verifica `MOTOR_RESERVAS_DESIGN.md` (constraints aplicables)
3. Consulta `MOTOR_RESERVAS_QUICK_REFERENCE.md` (common errors)

### Escenario 4: Debugging en Producción
1. Abre `MOTOR_RESERVAS_QUICK_REFERENCE.md` (debugging section)
2. Busca error en `MOTOR_RESERVAS_QUICK_REFERENCE.md` (tabla de errores)
3. Verifica constraints en `MOTOR_RESERVAS_DESIGN.md`
4. Revisa test similar en `MOTOR_RESERVAS_PSEUDOCODE.md`

### Escenario 5: Documentar para Stakeholders
1. Usa `MOTOR_RESERVAS_SUMMARY.json` como fuente de verdad
2. Extrae diagramas de `MOTOR_RESERVAS_DESIGN.md`
3. Usa casos de uso de `MOTOR_RESERVAS_DESIGN.md` para demostración

---

## Mapa Mental del Sistema

```
                        MOTOR DE RESERVAS
                             │
                ┌────────────┼────────────┐
                │            │            │
             DATOS      ALGORITMO      OPERACIONES
             │            │            │
    ┌─────────────┐  ┌────────────┐  ┌────────────────┐
    │Reservation  │  │ CP-SAT     │  │ RoomMoveEvent  │
    │- status     │  │ Solver     │  │ - from_room    │
    │- room_id    │  │ + Greedy   │  │ - to_room      │
    │- dates      │  │ Fallback   │  │ - reason_code  │
    └─────────────┘  └────────────┘  └────────────────┘
         │                │                │
         ├─ Pricing       ├─ Constraints   ├─ Auditoría
         ├─ State         ├─ Objective     ├─ Validación
         │  Machine       ├─ Optimization  ├─ Execution
         │                │  Horizon       └─ Feedback
         └─ Transactions  └─ Tuning
```

---

## Checklist de Implementación

### Fase 1: Setup & Modelos (Semana 1)
- [ ] Crear `app/models/operations.py` con `RoomMoveEvent`, `ReservationAdjustment`, `BillingAdjustment`
- [ ] Actualizar `app/models/reservation.py` con `allocation_status`, `allocation_locked`
- [ ] Crear `app/schemas/allocation.py` con `AllocationResult`, `RoomMoveIntent`
- [ ] Crear `app/schemas/operations.py` con schemas de operaciones

### Fase 2: Servicios Core (Semana 1-2)
- [ ] Implementar `run_allocation()` en `app/services/allocation_engine.py`
- [ ] Implementar `_run_allocation_greedy()` (fallback)
- [ ] Implementar `transition_reservation_status()` en `app/services/reservation_service.py`
- [ ] Actualizar `calculate_reservation_pricing()` si es necesario

### Fase 3: Room Operations (Semana 2-3)
- [ ] Implementar `move_reservation_room()` en `app/services/reservation_operations_service.py`
- [ ] Implementar `validate_room_move_intent()`
- [ ] Implementar `execute_room_move()` (atomic)
- [ ] Implementar `record_manual_override_feedback()`

### Fase 4: APIs (Semana 2-3)
- [ ] POST `/reservations` con auto-assignment
- [ ] PATCH `/reservations/{id}/status` con transición
- [ ] POST `/reservations/{id}/move-room` con validación
- [ ] POST `/reservations/optimize` con CP-SAT

### Fase 5: Testing (Semana 3-4)
- [ ] Unit tests para CP-SAT (exactness, fragmentation, lock)
- [ ] Integration tests para state machine
- [ ] Integration tests para room moves
- [ ] E2E tests para workflow completo
- [ ] Load tests (100+ reservas, 50 habitaciones)

### Fase 6: Observabilidad (Semana 4)
- [ ] Logging estructurado (JSON)
- [ ] Métricas (allocation success rate, gap, tiempo)
- [ ] Dashboards (Grafana o similar)
- [ ] Alertas (unassigned, optimization timeout)

---

## Referencias Cruzadas

### Por Función
| Función | Documento | Sección |
|---------|-----------|---------|
| `run_allocation()` | PSEUDOCODE | 2.1 |
| `_run_allocation_greedy()` | PSEUDOCODE | 2.2 |
| `move_reservation_room()` | PSEUDOCODE | 3.1 |
| `transition_reservation_status()` | PSEUDOCODE | 4.2 |
| `validate_transition()` | PSEUDOCODE | 4.1 |
| `execute_room_move()` | PSEUDOCODE | 3.2 |

### Por Constraint
| Constraint | Documento | Sección |
|-----------|-----------|---------|
| C1 - Locked | DESIGN | 3.5 |
| C2 - Category | DESIGN | 3.5 |
| C3 - Overlap | DESIGN | 3.5 |
| C4 - Exactitud | DESIGN | 3.5 |
| S1 - Fragmentación | DESIGN | 3.1 |
| S2 - Estabilidad | DESIGN | 3.1 |

### Por Caso de Uso
| Caso | Documento | Sección |
|-----|-----------|---------|
| Nuevo Guest | DESIGN | 9.1 |
| Movimiento Manual | DESIGN | 9.2 |
| Optimización Nocturna | DESIGN | 9.3 |
| OTA Rebook | DESIGN | 9.4 |
| Cancelación | DESIGN | 9.5 |

---

## Métricas Clave

### Éxito de Implementación
| Métrica | Target | Documento |
|---------|--------|-----------|
| Asignación exitosa | > 95% | DESIGN 11.1 |
| Tiempo solver | < 30s (medio) | DESIGN 3.5 |
| Fragmentación | < 5% gaps | DESIGN 3.1 |
| Cobertura tests | > 85% | DESIGN 10 |
| Latencia API | < 2s (p99) | SUMMARY |

---

## Integración con Grafify

Estos documentos están integrados con el grafo de conocimiento del proyecto:

```
MOTOR_RESERVAS_DESIGN.md
  ├─ Usa conceptos de: AllocationEngine (Community 0)
  ├─ Referencias modelos: Reservation (god node 2), Room (god node 4)
  ├─ Cubre operaciones: ReservationAdjustment, RoomMoveEvent
  └─ Afecta servicios: reservation_service, allocation_engine

MOTOR_RESERVAS_PSEUDOCODE.md
  ├─ Implementación de: run_allocation(), _run_allocation_greedy()
  ├─ Usa estructuras: ReservationSlot, RoomSlot, AllocationResult
  └─ Integra: transition_reservation_status(), move_reservation_room()
```

**Para actualizar grafo:**
```bash
graphify update .
```

---

## FAQ Rápido

**P: ¿Por dónde empiezo?**
R: Lee `MOTOR_RESERVAS_SUMMARY.json` (15 min), luego `MOTOR_RESERVAS_QUICK_REFERENCE.md`

**P: ¿Qué es el CP-SAT?**
R: Google OR-Tools Constraint Programming Solver. Ver DESIGN sec. 3.1 y PSEUDOCODE sec. 2.1

**P: ¿Qué pasa si OR-Tools no está instalado?**
R: Fallback a algoritmo greedy. Ver PSEUDOCODE sec. 2.2

**P: ¿Cómo evitar overbooking?**
R: Pessimistic locking (with_for_update()). Ver QUICK_REFERENCE sec. 5

**P: ¿Cómo cambiar pesos del solver?**
R: policy_weights dict. Ver QUICK_REFERENCE sec. 6

**P: ¿Dónde va el código?**
R: app/services/allocation_engine.py, app/services/reservation_operations_service.py. Ver QUICK_REFERENCE sec. 1

**P: ¿Cómo debuggear?**
R: Ver QUICK_REFERENCE sec. 9 y DESIGN sec. 11.1

---

## Cambios Históricos

| Fecha | Versión | Cambio |
|-------|---------|--------|
| 2026-06-09 | 1.0 | Versión inicial — 4 documentos + índice |

---

## Contacto & Soporte

Para preguntas sobre:
- **Arquitectura general:** Ver DESIGN cap. 1
- **Implementación CP-SAT:** Ver PSEUDOCODE sec. 2.1
- **APIs:** Ver SUMMARY > apis
- **Testing:** Ver PSEUDOCODE sec. 5
- **Debugging:** Ver QUICK_REFERENCE sec. 9

---

**Última actualización:** 2026-06-09  
**Total de documentación:** 122.4 KB (4 archivos)  
**Tiempo de lectura estimado:**
- Overview rápido: 30 min
- Implementación completa: 8 horas
- Dominio experto: 2 semanas

**Status:** Ready for Development ✓

