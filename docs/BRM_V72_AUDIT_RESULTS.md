# Resultados de Auditoría — Sistema actual vs. BRM v72

> **Fecha:** 2026-06-24 · **Método:** 11 subagentes en paralelo (3 Codex high-reasoning: Motor, Pagos, Seguridad; 8 Claude). Evidencia con `archivo:línea`.
> **Base auditada:** `main` (la rama de release actual `fix/analytics-deploy-readiness` está **32 commits detrás de main**).
> **Reemplaza:** los porcentajes obsoletos de `vault/hotel-chipre-pms/brm-status.md` (decían "20%", de 2026-06-09).

---

## 🔴 Hallazgo estructural #1 — DOS líneas V72 paralelas, nunca fusionadas

Ambas nacen de `e0aec43` (2026-05-08):
- **Línea `main`** (hasta 2026-06-14): implementación V72 con **servicios dedicados** que la otra no tiene (`waitlist_service`, `room_movement_group_service`, `cash_register_service`, suite `analytics_*`, `rate_calendar_service`, adapters OTA booking/expedia/despegar).
- **Línea `horde/t1..t6` + `claude/fervent-jennings` + `claude/cranky-robinson`** (hasta 2026-06-11, **NO mergeada**): aporta lo que a `main` le **falta** → tests de gate §7.1 (414 LOC), tests de concurrencia (515 LOC), `change-dates` §8.3/§8.4, recargos de pago §12.3, **RBAC/roles §1** (`role_service.py`, solo en `cranky`), `daily_rates` §13.

**Implicación:** mucho trabajo V72 existe pero está **varado en ramas**. La consolidación real del sistema requiere un esfuerzo de *merge/port* deliberado, no más desarrollo desde cero. Ramas con trabajo único relevante: 6×`horde/t*`, `claude/fervent-jennings`, `claude/cranky-robinson`, `feature/rate-calendar-readonly`. Todas las `worktree-agent-*`, `horde/s0x`, `next`, `codex/*`, `feature/adminpmsmaster` = **descartables** (0 commits únicos / ya en main).

---

## 📊 Matriz de cumplimiento por épica (estado en `main`)

Leyenda: ✅ implementado+test · 🟡 implementado sin test · 🟠 parcial · 🔴 ausente · *(rama)* = existe solo en rama no mergeada.

| Épica BRM | % real en main | Estado resumido |
|---|---|---|
| §1/§26 Multi-tenant, roles, auditoría | **~55%** | Contexto de hotel ✅, audit log con hotel-scope ✅, redacción PII ✅. 🔴 **soft delete ausente** (hard deletes), 🟠 múltiples endpoints sin guard de tenant, RBAC parcial (matriz completa solo en rama `cranky`) |
| §2 Huéspedes | **~66%** | Dedup lógico, rating, tags, "prohibido alojar" (bloqueo check-in) ✅ con test. 🔴 **sin UNIQUE en DB** `(hotel_id, documento)`, endpoint `POST /guests` **evade la dedup**, **sin auditoría**, rating/alerts/summary no expuestos en API |
| §3 Reservas de empresa | **~25%** | 🔴 **reserva de empresa NO creable** (`company_id` no está en el schema), precio por empresa, pago diferido y vouchers **inexistentes**; faltan email/teléfono/contacto en `Company` |
| §4 Habitaciones / score | **~40%** | Score 1-10 como desempate ✅ con test. 🔴 `score`/`is_accessible`/`description` **no expuestos en schemas** ni editables vía `PATCH /rooms` (quedan en default) |
| §5/§6 Motor de reservas | **~43%** | Motor configurable por hotel ✅ con test. 🟠 algoritmo no modela capacidad/personas ni locks duros (empresa/mantenimiento). §5.2 reoptimización y grupos de movimiento **solo en rama** |
| §7 Check-in/out | **~69%** | Guard §7.1 (rechaza check-in con saldo) ✅ existe; su **test exhaustivo solo en `horde/t2`**. 🔴 §7.2 prefinalizado ausente. 🟠 **bug §7.7 no-show**: transiciona a `CANCELLED` en vez de `NO_SHOW` y **excluye al recepcionista** |
| §8 Cambios y extensiones | **~55%** | §8.2 cambio de habitación ✅. 🔴 **§8.6 (extensión sobre habitación vendida) solo rechaza**, sin flujo de movimiento/conflicto. 🟠 §8.3/§8.4 **solo en `horde/t3`**. ⚠️ **bug latente** en `extend_stay` (kwarg `reason_note` enmascarado por monkeypatch en el test) |
| §9 Overbooking / lista de espera | **~40%** | `waitlist_service` existe en main; endpoint/schema y tests (687 LOC) **en `horde/t4`**. Falta exponer `is_wait_listed`, bloquear pago para waitlisted, excluir de calendario |
| §10 OTA / duplicados | **~45%** | §10.1 dedup por Booking ID vía **webhook** ✅ con test (unique constraint DB). 🟠 carga **manual** no exige external_id ni deduplica. 🔴 **§10.2 (liberar OTA sin garantía) ausente** |
| §12 Pagos y links | **~30%** | 🔴 **firma de webhook MercadoPago mal calculada** (algoritmo no estándar; el correcto existe en `payment_link_test_service`). 🟠 idempotencia no forzada (webhook duplicado → 500). 🔴 **sin locking de concurrencia**. Recargos §12.3 **solo en rama**. Entrega de links (email/SMS/WhatsApp) = TODO/501 |
| §13 Calendario / tarifas | **~30%** | 🔴 **tarifas diarias + edición masiva solo en `horde/t5`** (no en main). 🟠 los 3 estados de celda (pendiente/OTA-sin-pago/revisión) **no existen como concepto unificado**; los datos sí (`balance_due`, `source`, `requires_manual_review`) |
| §14 Bloqueos / mantenimiento | **~40%** | Bloqueo vía `PATCH /rooms/status` ✅. 🔴 **recepcionista NO puede bloquear** (el BRM lo exige); roles hardcodeados, no configurables por hotel |
| §15 Emails / Gmail | **~55%** | §15.2 transaccional vía Resend ✅ con test; links de pago desde Gmail del hotel ✅. 🔴 **reportes/alertas (`email_cron`) violan §15.1**: salen por `EmailService` legacy a `MASTER_ADMIN_EMAIL`, no per-hotel. ⚠️ **dos sistemas de email coexisten** |
| §16 API pública (WhatsApp, booking engine) | **~5%** | 🔴 **épica entera ausente**: sin API key por hotel, sin endpoints públicos, sin WhatsApp bot, sin booking engine, sin rate-limit por clave |

**Estimación global real en `main`: ~45%** (vs. el "20%" obsoleto del tracker, y lejos de un "V72 completo"). Sumando el trabajo varado en ramas no mergeadas, el sistema cubriría notablemente más, pero **hoy, en main, está al ~45%**.

---

## 🚨 Top bloqueadores (prioridad por riesgo)

### Seguridad (atacar primero)
1. **Firma de webhook MercadoPago incorrecta** — `app/services/payment_webhook_service.py:71-72` concatena en vez de usar el manifest HMAC. El algoritmo correcto YA existe en `app/services/payment_link_test_service.py:173-174`. Un webhook falsificado podría pasar la validación. *(Riesgo de dinero/seguridad.)*
2. **Endpoints sin guard de tenant (fuga multi-hotel)** — router Gmail completo (`app/api/gmail_integration.py:66-238`, `EmailLog` sin `hotel_id`), `connections.py`, `demo.py` (`/api/reset` dropea TODAS las tablas), y patrón "load-by-id-before-hotel-check" en payment-links/payments/reservations. Ver lista completa en el reporte WS-C.
3. **Idempotencia y concurrencia de webhooks** — duplicado → IntegrityError/500 (`payment_webhook_service.py:127-136`); sin `with_for_update` al mutar estado de pago (`:169-201`).
4. **Soft delete ausente** — hard deletes en audit/bookings/rooms/demo; viola la auditoría exigida (§26).

### Integridad de datos
5. **Sin UNIQUE DB `(hotel_id, documento)` en huéspedes** + `POST /api/guests:51-70` evade `find_or_create_guest` → duplicados reales en prod.
6. **Reserva de empresa no creable** — `company_id` no está en `ReservationCreate` ni se asigna en `reservation_service`.

### Reglas de negocio críticas
7. **Bug §7.7 no-show** — `app/api/reservations.py:297-299` usa `CANCELLED` en vez de `NO_SHOW`; excluye al recepcionista (`:284`).
8. **§8.6 extensión sobre habitación vendida** — solo rechaza; sin flujo de movimiento/conflicto (`MovementGroup` existe en DB pero no se conecta).
9. **§15.1 reportes/alertas por canal equivocado** — `email_cron.py:51,98,142` no usa `send_hotel_email`; el beat schedule está activo.

### Features faltantes grandes
10. **§16 API pública completa** (WhatsApp bot, booking engine, API key por hotel) — prácticamente inexistente.
11. **Merge/port del trabajo varado** — tarifas diarias (`t5`), change-dates (`t3`), recargos (`t1`), RBAC (`cranky`), tests de gate/concurrencia (`t2`/`fervent`).

---

## ⚠️ Notas de confianza
- Los subagentes leyeron el BRM desde copias en worktrees/`docs/` porque `vault/hotel-chipre-pms/business-requirements-master-v72.md` **no existe dentro del checkout** (vault externo). Contenido verificado coincidente; números de línea ±2.
- No se ejecutó `pytest`: los estados ✅ se basan en presencia de implementación **+** presencia de test, no en que el test pase. **Verificación pendiente:** correr la suite en `main`.
- `git show`/`git diff` entre ramas estuvo limitado por sandbox en algunos agentes; usaron worktrees hermanos como fallback (no se confirmó paridad exacta con el HEAD de cada rama).
