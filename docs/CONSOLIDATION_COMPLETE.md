# Consolidación V72 + NoSQL — COMPLETADA

**Fecha:** 2026-06-25 · **Fuente de verdad única: `main`** (= origin/main) @ `92eca64`

## Resultado

- **Suite:** 641 passed, 8 skipped, 35 xfailed, **0 fallos** (SQLite + PostgreSQL real). Baseline era 498 → +143 tests, sin un solo rojo.
- **Alembic:** 1 solo head (`20260624_fx_rate_snapshots`), 38 migraciones aplican limpio en SQLite y PostgreSQL.
- **Una sola rama activa:** `main`. Todo lo legacy borrado (local + remoto). Origin solo tiene `main`.
- **Respaldo:** 11 tags `backup/*` preservan toda rama con trabajo único (reversible).

## Qué se consolidó (14 commits sobre main)

| Fase | Entregable |
|---|---|
| 1 | Rama fuente + baseline verde + fix de estado sucio PG |
| 2 | Port de fervent: daily_rates §13, payment_surcharges §12.3, reoptimización §5.2, movement_groups API §5.4, blocks §14, fx_rates + red de tests V72 (7 archivos, 74 pass/35 xfail) + fix colisión constraint PG |
| 3 | Cosecha de cranky: decorator `@audited_change` (primer escritor real de AuditLog, gap §26) + 25 docs a `docs/design/`. Resto descartado (redundante) |
| 4 | Cosecha del WIP: `read_model_cache` Redis + wiring analytics. rate-calendar ya estaba en main |
| 5 | Alembic 1-head + **fix seguridad: firma webhook MercadoPago → manifest HMAC** |
| 6 | Fundación NoSQL: Redis/Mongo/Cassandra/Neo4j en docker-compose + clientes defensivos + `/health/datastores` |
| 7 | Adopción NoSQL (best-effort, core en Postgres intacto): **Redis** caché disponibilidad · **Mongo** proyección auditoría · **Cassandra** time-series (room_state_events, daily_rate_history) · **Neo4j** grafo (Reservation/Room/Guest/Company) |
| 8 | main promovida (ff + push) + limpieza total de ramas/worktrees con respaldo |

## Arquitectura de datos (polyglot)

- **PostgreSQL** = fuente de verdad transaccional (reservas, pagos, caja). Nunca depende de NoSQL.
- **Redis** = caché read-through de lecturas calientes (analytics, disponibilidad).
- **MongoDB** = documental/append-heavy (audit logs).
- **Cassandra** = time-series/write-heavy (eventos de estado, histórico de tarifas).
- **Neo4j** = grafo (motor de asignación, relaciones huésped/empresa).
- Todos los stores son **best-effort con flag + fallback**: apagados o caídos, el sistema sigue sirviendo desde Postgres. Los tests pasan sin los drivers instalados (import lazy).

## Pendiente (no bloqueante)

- 3 worktrees `agent-*` quedaron bloqueados por un proceso vivo (pid 21940), en `e0aec43` sin trabajo único — limpiar con `git worktree remove -f -f` cuando el proceso termine.
- **35 xfail = gaps reales documentados** para próximas iteraciones: §9 waitlist (main usa tabla WaitlistEntry, no flags), §2 dedup huéspedes (`find_or_create_guest`), §8.3-8.5 cambio fechas/extensión, §17 caja endpoints avanzados.
- Tabla huérfana `payment_surcharge_configs` (modelo `payment_config` sin cablear) — candidata a eliminar.
- Validación de paridad NoSQL real requiere `docker-compose up` con los 4 stores y flags `*_ENABLED=true`.
