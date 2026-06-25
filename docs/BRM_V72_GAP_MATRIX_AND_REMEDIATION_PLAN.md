# BRM v72 — Matriz de Gaps (main consolidado) + Plan de Remediación en Fases

> **Fecha:** 2026-06-25 · **Base:** `main` consolidado @ 92bc1e7 · **Método:** re-auditoría de 10 subagentes (Codex high + Claude) con evidencia `archivo:línea` contra el estado ACTUAL.
> Reemplaza la auditoría vieja `docs/BRM_V72_AUDIT_RESULTS.md` (que corría sobre estado pre-consolidación y tenía hallazgos falsos para main).

## Estado global por dominio

| Dominio BRM | % real | Avances confirmados | Gaps principales |
|---|---|---|---|
| §1/§26 Multi-tenant/RBAC/Auditoría | **58%** | RBAC completa (override>default>deny + audit de denegación), cableada en 10+ endpoints | Tenant-leak (queries por id, check post-fetch); auditoría solo cubre 3 mutaciones; hard deletes; sin middleware global default-deny |
| §2 Huéspedes | **78%** | UNIQUE DB ✅, búsqueda c/teléfono ✅, rating/tags/override auditados ✅ | `find_or_create_guest` falta (POST /guests da 500); `update_guest` sin auditar; `first_name` no en search; quick_profile sin paginación/desglose |
| §3 Empresa | **53%** | company_id creable en reserva ✅, vouchers/documentos ✅, consumo de precio-empresa ✅ | Campos contacto/email/precio/deferred existen en modelo pero **no expuestos en schemas** |
| §4 Habitaciones | **20%** | score/is_accessible/description en modelo + validación DB ✅ | **No expuestos en schemas ni editables vía PATCH** (quick win) |
| §5/§6/§9 Motor/Restricción/Waitlist | **64%** | reoptimización ✅, motor configurable por hotel ✅, movement_groups API ✅ | Waitlist: modelo `WaitlistEntry` vs flags esperados por BRM; overbooking manual sin flujo; `mobility_restriction` no en schema; capacidad no en solver |
| §7 Check-in/out | **73%** | gate §7.1 ✅, **bug §7.7 no-show CORREGIDO** (NO_SHOW + recepcionista) ✅ | §7.4 no valida capacidad (permite overbooking de personas); §7.2 paso "prefinalizado" no expuesto |
| §8/§11 Cambios/extensiones | **62%** | cambio habitación/fechas/extensión con misma reserva ✅ | **§8.6 flujo de conflicto inexistente (solo rechaza)**; §8.4 detecta pago por Transaction no por estado; §8.3 no valida check-in pasado; §11 documento/teléfono opcionales |
| §10 OTA | **78%** | §10.1 carga manual ahora exige external_id ✅, §10.2 lógica release_no_guarantee ✅ con tests | **§10.2 sin endpoint API (código muerto en runtime)**; dedup manual↔webhook con claves distintas |
| §12/§3.5 Pagos | **55%** | surcharges §12.3 ✅, **firma webhook → manifest HMAC ✅** | MP preference real nunca se crea (link sin checkout URL); delivery de links solo en tooling; race en idempotencia; §3.5 diferido sin flujo AR real |
| §13 Calendario/tarifas | **45%** | tarifas diarias + edición masiva + periodos ✅ | **3 estados de celda no existen en payload**; §13.3 routing hoy/futuro y scheduler ausentes |
| §14 Bloqueos | **50%** | recepcionista puede bloquear / gerente desbloquea ✅ | Roles hardcodeados, no configurable por hotel |
| §15 Emails/Gmail | **70%** | Resend (plataforma) ✅, Gmail per-hotel ✅, legacy retirado ✅ | Sin scheduler de reportes; solo 1 de ~8 tipos de email operativo sale por Gmail |
| §16 API pública | **85%** | API keys per-hotel ✅, rate-limit por clave ✅, WhatsApp hooks ✅, booking engine ✅ | Falta endpoint público de estado reserva/pago; enums de origen incompletos (sin company/teléfono/web distinguidos) |

**Promedio ≈ 63%** (la auditoría vieja estimaba ~45%). El sistema avanzó mucho; el patrón dominante de gaps es **lógica/datos presentes pero no expuestos en la capa API/schema**, más algunos flujos de negocio de borde faltantes.

---

## Patrones transversales (claves para priorizar)

1. **Gap de exposición schema/API** (recurrente y barato de cerrar): Room §4, Company §3, find_or_create §2.1, release_no_guarantee §10.2. Datos+lógica ya existen → quick wins de alto valor.
2. **Cobertura de auditoría §26**: solo 3 mutaciones auditadas de ~30. Expandir `@audited_change` sistemáticamente.
3. **Higiene multi-tenant §1.2**: varias queries filtran por id y validan hotel post-fetch en vez de predicado en la query.
4. **Soft delete §26**: hard deletes en reservas/rooms/documentos/stock/etc.
5. **Scheduler ausente**: no hay Celery beat → §13.3 (reporte matutino) y §15.1 (reportes automáticos) bloqueados.
6. **Flujos de negocio de borde**: §8.6 conflicto de extensión, §9 overbooking/waitlist, §12.2 delivery real de pagos.

---

## Plan de Remediación en Fases

Cada fase: scope acotado, verificable con tests, sin romper. Esfuerzo: S (chico), M (medio), L (grande).

### Fase R1 — Quick wins de exposición (máximo valor / mínimo esfuerzo) · S-M
Cierra ~4 dominios subexpuestos tocando solo schemas/endpoints.
- §4/§4.1: agregar `score`/`is_accessible`/`description` a `RoomBase`/`RoomUpdate`/`RoomRead` + loop de `update_room`. (20%→~90%)
- §3.3-3.5: exponer `contact_name/email/phone`, `base_price`, `payment_deferred/deferred_days`, `requires_voucher/signature` en schemas Company + create/update. (53%→~95%)
- §2.1: implementar `find_or_create_guest` y cablearlo en `POST /guests` (hoy da 500). + §2.4 `first_name` en `search_guests`.
- §10.2: exponer `release_no_guarantee` vía `POST /reservations/{id}/release-no-guarantee` con permiso propio (gerente/dueño/codueño).
- **Verificación:** convertir los xfail relacionados (§2.1 dedup, score editable) a green.

### Fase R2 — Auditoría completa + soft delete + higiene tenant (§1/§26) · M-L
- Expandir `@audited_change` (o helper de service) a TODAS las mutaciones: guest CRUD, ciclo de reserva (create/cancel/no-show/change/move), room CRUD, pricing, user invite/revoke/role, surcharges. + `update_guest` (§2.2).
- Soft delete: agregar `deleted_at`/`is_deleted` y reemplazar `db.delete()` en reservas/rooms/company_documents/price_periods/stock.
- Higiene multi-tenant: agregar predicado `hotel_id` en las queries con check post-fetch (reservation_service, pricing_service, allocation_engine, bookings, rooms).
- Middleware global default-deny + allowlist explícito de rutas públicas (auth/webhooks/public).

### Fase R3 — Reglas de negocio de reservas (§7, §8, §6) · M-L
- **§8.6 (el gap más grande):** flujo de conflicto en extensión — consultar seña de reserva futura, mover futura autoasignable, reasignar a superior con motivo, conectar `RoomMovementGroup` (hoy solo rechaza).
- §8.4: detectar "pago" por `amount_paid`/estado `DEPOSIT_PAID`, no solo por filas Transaction.
- §8.3: validar check-in en el pasado. §7.4: validar capacidad al agregar huéspedes.
- §11: hacer documento/teléfono obligatorios en alta telefónica. §5.3/§8.2: `reason_code` obligatorio en move. §6: exponer `mobility_restriction` en schema + trigger reoptimización.

### Fase R4 — Overbooking y lista de espera (§9) · M
- **Decisión de diseño:** unificar waitlist — agregar flags `is_wait_listed`/`wait_list_reason` a `Reservation` (lo que espera el BRM y los 15 xfail) manteniendo `WaitlistEntry` como detalle, o re-alinear el BRM. Recomendado: flags en Reservation + tabla de detalle.
- Flujo de overbooking manual (consumir `allow_overbooking` en `create_reservation`, endpoint owner/co_owner).
- Link de pago para waitlisted; exclusión del calendario principal.

### Fase R5 — Pagos en producción (§12, §3.5) · M-L
- Crear preferencia MercadoPago real desde `/api/payment-links` (persistir `external_checkout_url`, preference id, expiración).
- Delivery real de links: email en prod (mover lógica de tooling), WhatsApp con mensaje real, SMS stub.
- Fix race de idempotencia: asignar `idempotency_key` antes del flush; `db.add(event)` dentro del savepoint.
- §3.5: flujo de pago diferido empresa (vencimiento AR, estados de settlement, recording de cobro).
- Eliminar tabla huérfana `payment_surcharge_configs` (modelo `payment_config`) vía migración drop.

### Fase R6 — Calendario + Scheduler (§13, §15.1) · M
- Proyectar los 3 estados de celda (`pending_payment`, `ota_unpaid`, `available_with_review`) al payload de `rate_calendar_service`.
- Agregar Celery beat scheduler: reporte matutino + nocturno automáticos por hotel vía `send_hotel_email`.
- §13.3 routing: revisión para HOY → alerta inmediata a personas configuradas; FUTURO → reporte matutino.
- Cobertura de tipos de email per-hotel (reportes diarios, links de pago al huésped, caja, mantenimiento).

### Fase R7 — API pública, origen y bloqueos configurables (§16, §14, §2.5) · S-M
- Endpoint público read-only de estado de reserva/pago.
- Alinear enums de origen: añadir `company` a channel, distinguir manual vs API, o derivar origen reportable de channel_code + company_id (con migración).
- §14: roles de bloqueo configurables por hotel (campo en `hotel_configuration`).
- §2.5: quick_profile con paginación "Mostrar más", `observations`, y desglose previas/futuras/canceladas/no-show.

### Fase R8 — Validación de paridad NoSQL (cierre) · S
- `docker-compose up` con los 4 stores + flags `*_ENABLED=true`; correr los tests de paridad real (hoy pasan con stores off por fallback).
- Benchmark de lecturas calientes (Redis) y verificación de proyecciones (Mongo/Cassandra/Neo4j).

---

## Secuencia recomendada
`R1 (quick wins)` → `R2 (auditoría/tenant/soft-delete)` → `R3 (reglas reservas)` → `R4 (waitlist)` → `R5 (pagos prod)` → `R6 (calendario/scheduler)` → `R7 (API pública/origen)` → `R8 (paridad NoSQL)`.

R1 sola sube el cumplimiento global de ~63% a ~75% con esfuerzo bajo (es casi todo exposición de schemas). R2 cierra la deuda de seguridad/auditoría. R3-R5 son el grueso de negocio. R6-R8 completan operación y validación.
