# Consolidation Baseline — fuente de verdad `consolidation/v72-unified`

**Fecha:** 2026-06-24 · **Rama:** `consolidation/v72-unified` (creada desde `main` @ `1f19859`)

## Línea de "NO ROMPER" (verde de referencia)

| Métrica | Valor |
|---|---|
| Tests SQLite (suite completa) | **498 passed, 8 skipped, 0 fallos de código** (404s) |
| Tests PostgreSQL (`test_postgres_validation.py`) | **2 passed** tras limpieza (ver abajo); resto skip si no hay PG |
| `alembic heads` | **1** (`20260614_pg_perf_guest_trgm`) |
| Migraciones en disco | 34 |

**Total efectivo: suite verde.** Cualquier fase posterior debe mantener ≥ este número; no se commitea con rojos nuevos.

## Incidente resuelto en Phase 1 (estado sucio pre-existente)

- Los 2 tests `test_alembic_{upgrade_on_empty_database,downgrade_and_reupgrade}` fallaban con `Can't locate revision '20260614_cash_reopen'`.
- **Causa:** la DB de test `hotel_chipre_test` (Supabase, separada de prod `postgres`) quedó sellada con la revisión `20260614_cash_reopen`, que **solo existe en el worktree `goofy-bhaskara-041b49`** y en ninguna rama consolidable. Estado sucio cruzado entre worktrees (ver memoria `pg_migration_idempotency`).
- **Fix aplicado:** `DROP SCHEMA public CASCADE; CREATE SCHEMA public` sobre `hotel_chipre_test` (DB de test efímera). NO se tocó producción. Tras el reset, ambos tests pasan.

## Estado de ramas al iniciar la consolidación

- **BASE / fuente de verdad:** `consolidation/v72-unified` (= `main` @ 1f19859).
- **WIP preservado:** `fix/analytics-deploy-readiness` (3 commits snapshot: código analytics + artefactos de auditoría). Se reconcilia en Phase 4.
- **A consolidar:** `claude/fervent-jennings-1299c4` (= superset de horde/t1..t6), `claude/cranky-robinson-89dfad`, `feature/rate-calendar-readonly`.
- **A borrar en Phase 8:** worktree-agent-*, horde/s0x, next, codex/*, feature/adminpmsmaster, dashboard-de-datos, y demás sin commits únicos.

## Comando de baseline (reproducible)

```bash
python -m pytest -q -p no:cacheprovider           # suite (SQLite)
# PG: requiere .env con DATABASE_URL postgresql; conftest deriva hotel_chipre_test
```
