# Checkpoint — v72 Gaps Phase 1

Fecha: 2026-06-12

## Estado

Etapa completada. **DATABASE_FOUNDATION_NOT_COMPLETE** — pendientes bloqueantes detallados al final.

## Objetivo

Auditar y cerrar todos los gaps identificados en `business-requirements-master-v72.md` contra el modelo de datos del worktree `clever-chebyshev-98b486`.

## Cambios implementados

### Float → Numeric(12, 2) (precision financiera)

Todos los campos monetarios migrados de `Float` a `Numeric(12, 2)`:

| Modelo | Campos |
|--------|--------|
| `Reservation` | `total_amount`, `amount_paid`, `deposit_amount`, `subtotal_amount`, `tax_amount`, `fee_amount`, `commission_amount`, `net_amount` |
| `Transaction` | `amount`, `gross_amount`, `tax_amount`, `fee_amount`, `net_amount` |
| `HotelVoucher` | `original_amount`, `remaining_amount` |
| `VoucherRedemption` | `amount_used` |
| `RefundRequest` | `amount` |
| `RoomCategory` | `base_price_per_night` |

**Impacto en servicios:**
- `payment_service.py` — todo el stack aritmético migrado a `Decimal`; se usa `Decimal(str(v))` como conversión segura en todos los puntos de mezcla float/Decimal
- `reservation_service.py` — `_compute_deposit_amount` usa `float(gross_total)`; `json.dumps` de snapshots usa `default=lambda o: float(o) if isinstance(o, Decimal) else str(o)`
- `bookings.py` — `balance_due` se serializa con `float()` explícito
- `reservation.py` — propiedad `balance_due` usa `Decimal(str(v))` para evitar mezcla de tipos
- `test_reservation_operations_service.py` — assertions de float actualizadas a `pytest.approx`

### Guest deduplication (v72 §2.1)

`UniqueConstraint("hotel_id", "document_type", "document_number", name="uq_guest_document_per_hotel")` agregado a `guests`.

### Guest rating + tags (v72 §2.6)

- `GuestRatingEnum`: `normal` / `excelente` / `complicado` — campo `rating` en `Guest`
- `GuestTag` + `GuestTagTypeEnum`: tabla `guest_tags` con tipos `no_pago`, `robo`, `conflictivo`, `vip`, `alergias`, `otro`

### Room score + accessibility (v72 §4)

- `score: Integer (1-10)` + `CHECK(score IS NULL OR (score >= 1 AND score <= 10))`
- `is_accessible: Boolean` — guía asignación a piso más bajo para huésped con restricción motriz

### Reservation mobility_restriction (v72 §6)

- Campo `mobility_restriction: Boolean` en `reservations` — señal para el solver de asignación

### Cash register / Caja (v72 §13 — Sprint 1)

Tablas creadas: `cash_sessions`, `cash_movements`, `cash_close_reports`

Lifecycle:
- `CashSession` (`open` → `closed` / `pending_approval`)
- `CashMovement` (`income` / `expense` / `adjustment`)
- `CashCloseReport` — arqueo, diferencia, aprobación supervisor

### Waitlist / Lista de espera (v72 §9)

Tabla `waitlist_entries` — separada de `reservations` para que la disponibilidad nunca cuente huéspedes en espera como ocupantes reales.

### Payment surcharge config / Recargos (v72 §12.3)

Tabla `payment_surcharge_configs` — `UniqueConstraint(hotel_id, payment_method)`. Soporta `surcharge_pct` (%) y `surcharge_fixed` (monto fijo).

### Hotel API keys (v72 §16)

Tabla `hotel_api_keys` — credentials por hotel para WhatsApp bot, web engine, channel managers. Almacena `key_hash` + `key_prefix` (8 chars); nunca el secreto en claro.

## Migración

Alembic head único: `20260612_v72_gaps_phase1`

Cadena: `20260612_vouchers_refunds_pending_actions` → `20260612_v72_gaps_phase1`

La migración detecta `is_postgres` en runtime y usa batch_alter_table para compatibilidad SQLite.

## Validación

- Suite principal (excl. onboarding_flow, rate_limiting, smoke): **347 passed, 7 skipped**
- Nuevos tests en `tests/test_business_requirements_db.py`: 13 tests adicionales cubriendo todos los modelos nuevos
- Gate `test_database_foundation_complete` — VERDE

## Declaración

`DATABASE_FOUNDATION_NOT_COMPLETE`

### Pendientes bloqueantes

1. **PostgreSQL no validado** — todas las pruebas corren en SQLite. El código maneja diferencias runtime (`is_postgres`), pero no hay test contra una instancia real de PostgreSQL. La migración de `ALTER COLUMN` Float→Numeric puede requerir pasos adicionales en datos existentes.

2. **Main branch diverge** — el main branch tiene `Payment` + `PaymentLink` + `PaymentLinkTest` con `Numeric(12,2)` y head `20260612_query_performance_indexes`. El worktree tiene modelos distintos. Antes de declarar fundación completa hay que hacer merge y verificar que las cadenas Alembic se fusionen sin conflicto.

3. **Convergencia transactions ↔ payments sin definir** — `transactions` sigue como ledger operativo; `payments` como capa gateway/link/webhook (main branch). No existe aún una regla definitiva de source of truth por flujo documentada y bloqueante para A1.

4. **Alembic histórico con ramas** — `20260408_security_tokens (branchpoint)` es una rama histórica. No bloquea el head actual pero complica `alembic upgrade head` si algún downgrade toca esa cadena.

### No bloqueantes (post-fundación)

- Pydantic warning `Expected float but got Decimal` en serialización — no rompe funcionalidad; el valor se serializa como float correctamente. Puede suprimirse con `Annotated[float, PlainValidator(float)]` en los schemas afectados.
- PayPal webhook verification pendiente contra proveedor real.
- Audit redaction no cerrada.
