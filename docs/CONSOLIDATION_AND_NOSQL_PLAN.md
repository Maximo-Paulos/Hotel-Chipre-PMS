# Plan — Consolidación a fuente única de verdad + Persistencia Polyglot (SQL + NoSQL)

> **Tipo:** Plan de ejecución por fases (orquestador + subagentes para fact-gathering).
> **Generado:** 2026-06-24
> **Objetivos del usuario:**
> 1. Unificar TODO en una sola rama; que dejen de existir cambios/mejoras fuera de esa rama (fuente única de verdad).
> 2. Commitear todo verificando que **no rompa**; si algo rompe, encontrar la forma de integrarlo sin romper.
> 3. Incorporar NoSQL **obligatorio**: **Cassandra + Redis + MongoDB + Neo4j** (polyglot) para lectura/escritura más rápida y eficiente.
> 4. Reconciliar **toda** la rama `cranky-robinson` (aunque sea costoso).

---

## Phase 0 — Discovery (COMPLETADA por el orquestador)

### Hechos confirmados (con evidencia)

**Líneas divergentes a consolidar (3, no 1):**
- **`main`** — HEAD `1f19859` (2026-06-14). La más completa en servicios. **Será la BASE / fuente de verdad.** 34 migraciones Alembic.
- **`claude/fervent-jennings-1299c4`** — 30 commits. **Es el superset exacto de las 6 ramas `horde/t1..t6`** (verificado: `git rev-list horde/tN ^fervent` = 0 para las 6). Consolidar la línea horde = consolidar **solo fervent**. Tiene archivos que main no tiene (`app/api/{blocks,cash_register,daily_rates,fx_rates,movement_groups,payment_surcharges}.py`) y 13 migraciones `20260611_v72_*` con **contenido divergente** del de main.
- **`claude/cranky-robinson-89dfad`** — 2 commits, 64 archivos `.py`. **Reimplementación paralela** con nomenclatura distinta: `app/api/{cashbox,checkin_endpoints,motor_endpoints,pms_endpoints,roles,rate_tariff}.py`, `app/models/{role,cashbox,audit}.py`, `app/services/role_service.py` (**RBAC que main NO tiene** — confirmado `role_service.py` ausente en main). Migraciones propias fechadas `20260609_*`/`20260610_*` (audit_schema_v1, rbac_tables, cashbox_module, guest_module_v2, payment_links_and_surcharges, reservation_prefinalized).
- **`feature/rate-calendar-readonly`** — 3 commits, archivos disjuntos (frontend grid + `app/services/rate_calendar_service.py` + `app/api/rate_calendar.py`). **Bajo conflicto.**
- **Rama actual `fix/analytics-deploy-readiness`** — 32 commits **detrás de main**, con cambios sin commitear y archivos en disco que no están en main. NO usar como base.
- **Descartables (0 commits únicos / ya en main):** todas las `worktree-agent-*`, `horde/s0x`, `next`, `feature/adminpmsmaster`, `dashboard-de-datos`, `codex/*`, y 6 `claude/*` de tooling.

**🔴 Riesgo técnico #1 — Alembic multi-head.** main, fervent y cranky tienen **tres historias de migración divergentes** (34/34/+9 revisiones) con conceptos solapados (movement_groups, surcharges, cashbox, guest v2) implementados distinto. Un `git merge` produce *multiple heads* irresolubles automáticamente y conflictos masivos en `reservations.py`, `rooms.py`, `guests.py`, `main.py`, `models/`. **Conclusión: NO se hace `git merge` de ramas enteras. Se PORTAN features sobre `main` y se LINEALIZA la cadena Alembic a un solo head.**

**Estado NoSQL actual:**
- `redis==5.1.1` ya en `requirements.txt`; `app/services/read_model_cache.py` ya usa Redis (read-through con `REDIS_URL`); Celery sobre Redis (`app/config.py:27-30`).
- `docker-compose.yml` solo tiene `postgres:15` (sin servicios redis/mongo/cassandra/neo4j).
- No existe MongoDB, Cassandra ni Neo4j en el código.

### "Allowed tech / drivers" (versiones y patrones a copiar, no inventar)
| Store | Driver Python | Patrón a seguir | Uso asignado |
|---|---|---|---|
| Redis | `redis==5.1.1` (ya presente) | Copiar el cliente de `app/services/read_model_cache.py:1-40` | Caché read/write-through de modelos calientes (disponibilidad, calendario, tarifas), colas, rate-limit |
| MongoDB | `pymongo` (motor sync) | Cliente nuevo `app/db/mongo.py` análogo a `read_model_cache._get_redis_client` | Documental/append-heavy: audit logs, payloads OTA crudos, contexto IA/Gemma, analytics facts, email logs |
| Cassandra | `cassandra-driver` | Cliente nuevo `app/db/cassandra.py` | Time-series / write-heavy: `room_state_events`, snapshots de disponibilidad, histórico de tarifas diarias, movement logs |
| Neo4j | `neo4j` (official driver) | Cliente nuevo `app/db/neo4j.py` | Grafo: relaciones del motor (habitación↔reserva↔movimiento), dedup/relaciones de huéspedes, jerarquías de empresa |

### Anti-patterns a prevenir (toda la ejecución)
1. **NO `git merge fervent`/`cranky` a main.** Port feature-by-feature; cada port compila + pasa tests antes de commit.
2. **NO mover el core transaccional (reservas/pagos/caja) a NoSQL.** Postgres sigue siendo la fuente de verdad ACID; NoSQL son stores derivados/especializados sincronizados vía outbox/eventos.
3. **NO dejar Alembic con múltiples heads.** Tras cada fase, `alembic heads` debe devolver **exactamente 1**.
4. **NO commitear con tests rojos.** Si un port rompe, aislar (feature flag / adaptación) hasta verde.
5. **NO inventar APIs de drivers.** Copiar firmas reales del driver instalado; verificar con `python -c "import X"` antes de usar.

---

## Modelo de delegación
- **Orquestador (Claude):** decide orden de port, resuelve la cadena Alembic, define límites de fase, redacta el reporte de consolidación. NO delega la síntesis.
- **Subagentes (fact-gathering + ports acotados):** un subagente por módulo a portar (devuelve diff aplicable + resultado de tests) y un subagente por store NoSQL para extraer firmas reales del driver. Contrato obligatorio: fuentes leídas, hallazgos con `archivo:línea`, snippet copy-ready, confianza + gaps.

### Asignación de motores IA + razonamiento por fase (OBLIGATORIO)

Cada fase se ejecuta con subagentes **Codex** usando el motor y nivel de razonamiento indicado. Invocación: `codex -m <modelo> -c model_reasoning_effort=<low|medium|high>` (vía el agente `codex:codex-rescue` o el runtime Codex). El nivel se asigna por **riesgo/complejidad** de la fase: a más conflicto o lógica crítica, motor más capaz y razonamiento más alto.

| Fase | Motor | Razonamiento | Por qué |
|---|---|---|---|
| **1** Base + red de seguridad | **GPT-5.4** | medium | Baseline mecánico pero hay que leer estado divergente |
| **2** Port de `fervent` + linealización Alembic | **GPT-5.5** | high | Re-encadenar migraciones y conciliar servicios duplicados = alto riesgo |
| **3** Reconciliar `cranky` completo | **GPT-5.5** | high | Máximo conflicto (reimplementación paralela, colisiones en reservations/rooms/guests) |
| **4** rate-calendar + WIP sin commitear | **GPT-5.4** | medium | Archivos disjuntos, bajo conflicto |
| **5** Cierre Alembic + suite + fixes seguridad | **GPT-5.5** | high | Un solo head + firma webhook + guards de tenant = crítico |
| **6** Infra NoSQL (compose + clientes) | **GPT-5.4** | medium | Patrón claro a copiar (cliente Redis existente) |
| **7** Adopción NoSQL por workload (outbox/paridad) | **GPT-5.5** | high | Outbox, paridad y fallback de 4 stores = lógica delicada |
| **8** Limpieza de ramas | **GPT-5.4-mini** | low | Operación git mecánica con checklist |
| **9** Verificación final | **GPT-5.4-mini** | low | Greps, corridas de test, checklist; sin decisiones de diseño |
| **Fact-gathering** (todas las fases) | **GPT-5.4-mini** | low | Extracción de firmas/diffs/paths; barato y paralelizable |

Regla: si un subagente con motor menor reporta baja confianza o se bloquea, **escalar** a GPT-5.5 high antes de avanzar (el orquestador decide la escalada). Cada subagente Codex respeta el Subagent Reporting Contract.

---

## Phase 1 — Fuente única de verdad + red de seguridad
> **Motor:** GPT-5.4 · razonamiento medium · fact-gathering con GPT-5.4-mini low

**Qué hacer:**
1. Correr baseline en `main`: `pytest -q` y `alembic upgrade head` sobre SQLite y sobre Postgres (docker-compose). Registrar nº de tests verdes/rojos → `CONSOLIDATION_BASELINE.md`. Este es el "no romper" de referencia.
2. Crear la rama de consolidación desde main: `git switch -c consolidation/v72-unified main`. **Esta es la nueva fuente de verdad**; todo lo de aquí en más se commitea acá.
3. Stash/branch de los cambios sin commitear de `fix/analytics-deploy-readiness` para no perderlos (`git stash push -u` documentado), pero NO basar nada en esa rama.
4. Documentar la regla operativa en `CLAUDE.md` y `AGENTS.md`: "única rama activa = `consolidation/v72-unified`; ramas legacy congeladas pendientes de borrado en Phase 8".

**Verificación:** baseline registrado (nº tests, 1 solo `alembic heads`); rama creada; `git status` limpio en la nueva rama.
**Anti-pattern guard:** no empezar ports sin baseline verde documentado.

---

## Phase 2 — Consolidar `fervent` (= superset horde/t1..t6) sobre la rama de consolidación
> **Motor:** GPT-5.5 · razonamiento high (Alembic + conciliación de servicios) · fact-gathering con GPT-5.4-mini low

Portar, en este orden (dependencias primero), adaptando a los modelos/migraciones de main. Cada ítem: 1 subagente, aplica, `pytest` del módulo, commit atómico.

1. **Migraciones primero (linealización):** para cada migración `20260611_v72_*` de fervent que main no tiene, reescribir su `down_revision` para encadenarla al head actual de la rama de consolidación (no al head divergente de fervent). Referencia de orden: `docs/data-foundations/ALEMBIC_INTEGRATION_PLAN.md`. Verificar `alembic upgrade head` verde tras cada una.
2. **§5.2 Reoptimización** — portar `app/api/reservations.py` background task (`_trigger_reoptimization_bg`) y `allocation_engine` reoptim de fervent. Tests: `tests/test_v72_reoptimization_trigger.py`.
3. **§9 Waitlist/overbooking** — endpoints/schema `is_wait_listed`; conciliar con el `waitlist_service.py` que YA existe en main (quedarse con la versión de main + tests de fervent `test_v72_waitlist_overbooking.py`).
4. **§8.3/§8.4 Change-dates** — portar endpoints `change-dates-no-payment`/`change-dates` + `tests/test_v72_change_dates.py`.
5. **§12.3 Recargos** — portar `app/models/payment_surcharge.py`, `app/api/payment_surcharges.py`, lógica en `payment_service.py` + tests.
6. **§13 Daily rates** — portar `app/models/daily_rate.py`, `app/api/daily_rates.py` + `tests/test_v72_daily_rates.py`.
7. **§7.1 Gate tests + §5 concurrencia** — portar `tests/test_v72_checkin_gate.py` (414 LOC) y `test_v72_concurrency.py` (515 LOC); adaptar al guard ya presente en main (`checkin_service.py:92-96`). Verificar flag `require_full_payment_for_checkin` (la auditoría detectó que los tests lo asumen y no existe → crearlo en `hotel_config`).
8. **Caja (§17)** — conciliar `cash_register_service.py` (main) con tests `test_v72_cash_register.py` (920 LOC) de fervent.

**Verificación de fase:** `alembic heads` = 1; `pytest -q` ≥ baseline + nuevos tests verdes; `git diff main...HEAD` muestra solo features esperadas.
**Anti-pattern guard:** no duplicar servicios que main ya tiene (waitlist, cash register, movement groups) — conciliar a UNA implementación, no dejar dos.

---

## Phase 3 — Reconciliar `cranky` COMPLETO (decisión del usuario)
> **Motor:** GPT-5.5 · razonamiento high (máximo conflicto) · fact-gathering con GPT-5.4-mini low

Reimplementación paralela → conciliación **módulo por módulo**, eligiendo la mejor versión entre main y cranky y unificando nomenclatura (preferir nombres de main: `cash_register` no `cashbox`).

1. **RBAC/roles (§1/§26) — prioridad, gap real:** portar `app/services/role_service.py`, `app/models/role.py`, `app/api/roles.py`, `alembic/versions/20260609_rbac_tables.py` (re-encadenada). Integrar la matriz de permisos con el `require_roles` existente (`app/dependencies/auth.py`). Tests `test_roles.py`.
2. **Audit hooks (§26):** portar `app/decorators/audit_hooks.py` + diseño `AUDIT_HOOKS_*.md`; conectar al `audit_service.py`/`audit_log.py` de main (no duplicar el modelo). Cubre el gap "auditoría ausente en huéspedes/override".
3. **Cashbox vs cash_register:** comparar ambas; quedarse con una sola (recomendado main), portar de cranky solo lo que falte. Migración: NO aplicar `20260610_cashbox_module.py` si choca con la de main; portar columnas faltantes vía migración nueva encadenada.
4. **Motor/checkin/pms/rate_tariff endpoints:** mapear `motor_endpoints.py`/`checkin_endpoints.py`/`pms_endpoints.py`/`rate_tariff.py` a los endpoints equivalentes de main; portar solo lógica faltante (no rutas duplicadas). Resolver colisiones en `reservations.py`, `rooms.py`, `guests.py`, `main.py` a mano.
5. **Modelos `guest v2`, `reservation_prefinalized`, `accessibility`:** portar campos faltantes como migraciones nuevas encadenadas (no reemplazar tablas de main).
6. **Docs de diseño:** mover los 25 `.md` de cranky a `docs/design/` (valor de referencia, sin código).

**Verificación de fase:** `alembic heads` = 1; sin rutas/endpoints duplicados (grep de paths repetidos en `app/main.py`); RBAC con test; `pytest -q` verde.
**Anti-pattern guard:** no dejar `cashbox.py` Y `cash_register.py` coexistiendo; no dejar dos modelos de audit/guest.

---

## Phase 4 — Conciliar `rate-calendar-readonly` + cambios sin commitear
> **Motor:** GPT-5.4 · razonamiento medium · fact-gathering con GPT-5.4-mini low

1. Portar `app/api/rate_calendar.py` + `app/services/rate_calendar_service.py` + frontend (`RateCalendarGrid.tsx`, hooks, router). Bajo conflicto (archivos disjuntos). Tests `test_rate_calendar_*`.
2. Revisar los cambios sin commitear de `fix/analytics-deploy-readiness` (stash de Phase 1): rescatar lo válido (analytics deploy fixes) como commits sobre la rama de consolidación; descartar lo redundante.
3. Unificar los 3 estados de celda del calendario (§13) entre `rate_calendar_service` y los datos (`balance_due`, `source`, `requires_manual_review`).

**Verificación:** calendario sirve los 3 estados; frontend compila (`npm run build`); tests verdes.

---

## Phase 5 — Cierre Alembic + suite completa
> **Motor:** GPT-5.5 · razonamiento high (single-head + fixes de seguridad) · fact-gathering con GPT-5.4-mini low

1. `alembic heads` debe ser **1**. Si hay >1, crear migración `merge` explícita y verificar `upgrade head` + `downgrade base` + `upgrade head` en SQLite y Postgres limpios (referencia: el bug de idempotencia PG documentado en memoria `pg_migration_idempotency`).
2. Correr suite completa en SQLite y Postgres. Arreglar lo que rompa antes de seguir.
3. Aplicar de paso los **bloqueadores de seguridad de la auditoría** que son baratos y tocan archivos ya abiertos: firma webhook MercadoPago (`payment_webhook_service.py:71-72` → usar manifest HMAC de `payment_link_test_service.py:173-174`), idempotencia webhook, guard de tenant en router Gmail/connections/demo. (Detalle en `docs/BRM_V72_AUDIT_RESULTS.md`.)

**Verificación:** `alembic heads`=1; `pytest -q` 100% verde en ambos motores; grep confirma webhook usa manifest HMAC.

---

## Phase 6 — Fundación NoSQL (infra + clientes), sin cambiar lógica todavía
> **Motor:** GPT-5.4 · razonamiento medium · fact-gathering de firmas de drivers con GPT-5.4-mini low

**Qué hacer (copiar patrón del cliente Redis existente):**
1. `requirements.txt`: agregar `pymongo`, `cassandra-driver`, `neo4j` (redis ya está). Fijar versiones; verificar import (`python -c "import pymongo, cassandra, neo4j"`).
2. `docker-compose.yml`: agregar servicios `redis:7`, `mongo:7`, `cassandra:4`, `neo4j:5` con volúmenes y healthchecks (hoy solo está `postgres:15`).
3. `app/config.py`: agregar `MONGO_URL`, `CASSANDRA_HOSTS`/`CASSANDRA_KEYSPACE`, `NEO4J_URI`/`NEO4J_AUTH`, y flags `*_ENABLED` (default off en tests, como `READ_MODEL_CACHE_ENABLED`).
4. Clientes con fallback defensivo (copiar el patrón try/except de `read_model_cache.py:25-33`): `app/db/mongo.py`, `app/db/cassandra.py`, `app/db/neo4j.py`. Cada uno: `get_client()` que devuelve `None` si el flag está off o el server no responde (para no romper tests/CI).
5. Healthcheck endpoint `/health/datastores` que reporte estado de los 4 stores.

**Verificación:** `docker-compose up` levanta los 4; `/health/datastores` responde; con flags off, `pytest` sigue verde (sin dependencia dura).
**Anti-pattern guard:** ningún store NoSQL puede ser dependencia dura del arranque ni de los tests (flag + fallback obligatorio). No inventar métodos del driver: copiar de la doc oficial del driver instalado.

---

## Phase 7 — Adopción por workload (polyglot persistence, vía outbox/eventos)
> **Motor:** GPT-5.5 · razonamiento high (outbox + paridad + fallback de 4 stores) · fact-gathering con GPT-5.4-mini low

Postgres sigue siendo la fuente de verdad transaccional. Cada store recibe su workload como **store derivado** sincronizado por un **patrón outbox** (escribir evento en Postgres en la misma transacción → proyector asíncrono que escribe al store NoSQL). Pipeline por workload (cada uno: implementar → verificar paridad con Postgres → test).

1. **Redis (read/write-through):** extender `read_model_cache.py` a disponibilidad, calendario y tarifas calientes; invalidación en escrituras de reserva/tarifa. Verificación: lectura cacheada == lectura Postgres; invalidación correcta.
2. **MongoDB (documental/append-heavy):** proyectar audit logs, payloads OTA crudos (`ota_core` raw_payload), contexto IA/Gemma y analytics facts a colecciones Mongo; lecturas de reporting/historial leen de Mongo. Verificación: count/spot-check Mongo == Postgres.
3. **Cassandra (time-series/write-heavy):** `room_state_events`, snapshots de disponibilidad por día, histórico de `daily_rate`, movement logs → tablas wide-column particionadas por `(hotel_id, fecha)`. Verificación: escritura de evento aparece en Cassandra; query por rango de fechas.
4. **Neo4j (grafo):** modelar habitación↔reserva↔movimiento y huésped↔reserva↔empresa; el motor de asignación (§5) consulta el grafo para reoptimización y el dedup de huéspedes (§2.1) usa relaciones. Verificación: grafo refleja las asignaciones actuales; query de movimiento devuelve el mismo grupo que Postgres.

**Verificación de fase:** por cada store, test de **paridad** (NoSQL refleja Postgres) + test de fallback (store caído → la app sigue sirviendo desde Postgres). Benchmark antes/después de una lectura caliente (objetivo: latencia menor).
**Anti-pattern guard:** no dual-write sin outbox (riesgo de divergencia); no leer de NoSQL sin fallback a Postgres; el core (crear reserva/pago) nunca depende de que el NoSQL esté arriba.

---

## Phase 8 — Limpieza de ramas (que "dejen de existir" cambios fuera de la fuente de verdad)
> **Motor:** GPT-5.4-mini · razonamiento low (operación git mecánica con checklist)

1. Confirmar que todo lo valioso de fervent/horde/cranky/rate-calendar está portado (checklist contra `docs/BRM_V72_AUDIT_RESULTS.md`).
2. Hacer de `consolidation/v72-unified` la nueva `main`: merge fast-forward a `main` (o renombrar), `git push origin main`.
3. **Borrar** ramas locales y remotas ya consolidadas: 6×`horde/t*`, `claude/fervent-jennings`, `claude/cranky-robinson`, `feature/rate-calendar-readonly`, `fix/analytics-deploy-readiness`, y todas las descartables (`worktree-agent-*`, `horde/s0x`, `next`, `feature/adminpmsmaster`, `dashboard-de-datos`, `codex/*`, `claude/*` tooling). Worktrees: `git worktree prune`.
4. Configurar protección: a partir de acá, todo sale de `main` (la única fuente de verdad).

**Verificación:** `git branch -a` muestra solo `main` (+ ramas de trabajo nuevas explícitas); `git worktree list` limpio.
**Anti-pattern guard:** no borrar una rama sin verificar que su contenido único está portado (`git log main..<branch>` vacío de features no portadas).

---

## Phase 9 — Verificación final
> **Motor:** GPT-5.4-mini · razonamiento low (greps, tests, checklist)

1. `alembic heads` = 1; `alembic upgrade head` + ciclo downgrade/upgrade verde en SQLite y Postgres.
2. `pytest -q` 100% verde (baseline + todos los tests portados + tests NoSQL de paridad/fallback).
3. `docker-compose up` levanta Postgres + Redis + Mongo + Cassandra + Neo4j; `/health/datastores` todo OK.
4. Frontend `npm run build` verde.
5. Grep anti-patterns: sin módulos duplicados (`cashbox` vs `cash_register`), sin webhook con firma no-estándar, sin lecturas NoSQL sin fallback.
6. Solo existe `main` como fuente de verdad; ramas legacy borradas.
7. Actualizar `docs/orchestrator-status.md`, `obsidian-system-brain/06_SESSIONS/`, y `brm-status.md` con el estado consolidado.

---

### Resumen de secuencia
`Phase 1 (base+seguridad)` → `2 (fervent)` → `3 (cranky)` → `4 (rate-calendar+WIP)` → `5 (Alembic+suite+sec fixes)` → `6 (infra NoSQL)` → `7 (workloads NoSQL)` → `8 (limpieza ramas)` → `9 (verificación)`.

**Principio rector en cada commit:** verde antes de avanzar. Si un port rompe, aislar con flag/adaptación hasta que pase, nunca commitear rojo.
