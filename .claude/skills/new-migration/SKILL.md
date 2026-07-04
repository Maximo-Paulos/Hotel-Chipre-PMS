---
name: new-migration
description: Create and verify an Alembic migration for Hotel Chipre PMS the safe way (multi-tenant, money-as-Numeric, no NOT NULL without default, reversible). Use when adding/altering tables or columns, or when the user asks for a "migración", "nueva tabla", or schema change.
---

# new-migration — migración Alembic segura

Este proyecto: SQLAlchemy 2 en `app/models/`, Alembic en `alembic/versions/`, SQLite en tests / PostgreSQL (Supabase) en prod. Head actual se ve con `alembic heads`.

## Procedimiento
1. **Modelo primero**: editá/creá el modelo en `app/models/`. Reglas duras:
   - Dinero → `Numeric`, nunca `Float`.
   - Tablas de tenant llevan `hotel_id`; FKs/uniques por-hotel deben incluirlo.
   - Índices para hot paths (búsqueda de huéspedes, reservas por fecha/hotel).
2. **Generar la revisión**:
   ```sh
   cd /Users/maximopaulos/Desktop/Hotel-Chipre-PMS
   DATABASE_URL="sqlite:///$(mktemp -d)/gen.db" .venv/bin/python -m alembic revision -m "descripcion corta"
   ```
   (o `--autogenerate` si el modelo ya está y querés que infiera el diff — revisá SIEMPRE el archivo generado a mano).
3. **Reglas al escribir el `upgrade()`/`downgrade()`**:
   - `down_revision` correcto; mantené la cadena lineal (un solo head).
   - `downgrade()` real, no `pass`, salvo que sea irreversible y esté documentado.
   - **NUNCA** una columna `NOT NULL` sin `server_default` o un backfill explícito — rompe deploys sobre datos existentes.
   - Enums: en Postgres cambiar valores requiere `ALTER TYPE ... ADD VALUE` además del cambio de modelo (SQLite es permisivo, Postgres no).
4. **Verificar upgrade + downgrade** sobre SQLite virgen:
   ```sh
   D="sqlite:///$(mktemp -d)/mig.db"
   DATABASE_URL="$D" .venv/bin/python -m alembic upgrade head
   DATABASE_URL="$D" .venv/bin/python -m alembic downgrade -1
   DATABASE_URL="$D" .venv/bin/python -m alembic upgrade head
   ```
5. **Tests**: corré los que tocan schema (`tests/test_business_requirements_db.py`, tests de aislamiento) con `.venv/bin/python -m pytest`.

## Escalá antes de continuar
Si la migración puede perder datos, pará y reportá opciones. No adivines.
