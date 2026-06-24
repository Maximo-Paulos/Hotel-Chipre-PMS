# Plan de Auditoría — Sistema actual vs. Business Requirements Master v72

> **Tipo:** Plan de ejecución por fases (orquestador + subagentes Codex con razonamiento variable)
> **Generado:** 2026-06-24
> **Fuente de verdad de requisitos:** `vault/hotel-chipre-pms/business-requirements-master-v72.md` (2672 líneas, 32 épicas / secciones 1–29)
> **Objetivo:** Determinar, con evidencia en código, qué % de cada épica del BRM v72 está realmente implementado **across todas las ramas**, y producir un reporte de gaps confiable que reemplace el tracker obsoleto `brm-status.md`.

---

## Phase 0 — Discovery (COMPLETADA por el orquestador)

### Hallazgos de scoping (con fuentes)

**Requisitos (la "brain"):**
- BRM canónico: `vault/hotel-chipre-pms/business-requirements-master-v72.md`. Secciones de negocio: §2 Huéspedes, §3 Reservas de empresa, §4 Habitaciones, §5 Motor de reservas, §6 Restricción motriz, §7 Check-in/out, §8 Cambios/extensiones, §9 Overbooking/lista de espera, §10 OTA/duplicados, §11 Reserva telefónica, §12 Pagos y links, §13 Calendario/planilla, §14 Bloqueos/mantenimiento, §15 Emails/Gmail, §16 API pública. §17–§29 = reglas de sprint/proceso.
- Tracker de estado: `vault/hotel-chipre-pms/brm-status.md` — **OBSOLETO** (2026-06-09, dice "20% completado", 32 épicas, gap analysis de 10 agentes). **No confiar en sus porcentajes** — los commits recientes (`feat: implement V72 backend`, `test: add 20 V72 feature tests`) y las migraciones `20260611_v72_*` indican avance muy posterior.
- Brain in-repo: `obsidian-system-brain/00_HOME.md`, `04_MODULES/{audit,payments,reservations-availability}.md`.
- Docs de apoyo: `docs/CURRENT_SYSTEM_BUSINESS_MODEL_AUDIT.md`, `docs/TARGET_DOMAIN_ARCHITECTURE_V1.md`, `docs/data-foundations/*`.

**Estado del repo (anti-pattern guard #1 — NO asumir "no existe"):** el backend ya tiene módulos para casi toda épica. Confirmado por `ls`:
- `app/api/`: guests, companies, rooms, reservations, checkin, payments, payment_links, payment_webhooks, ota_webhooks, email, gmail_integration, audit, allocation_policy, integrations, connections, reports, analytics.
- `app/services/`: allocation_engine, allocation_{learning,policy,runtime}_service, reservation_operations_service, reservation_action_service, checkin_service, payment_{link,webhook}_service, guest_service, guest_profile, audit_service, email/, ota/.
- `app/models/`: guest, company, room, reservation, movement, allocation, payment, payment_link_test, transaction, audit_log, operations, ota/ota_core, email_models, hotel_membership, hotel_config.
- Migraciones V72 aplicadas: `20260611_v72_guest_rating_alerts`, `20260611_v72_movement_groups`, `20260611_v72_reservation_fields`, `20260611_v72_room_score_accessibility`, `20260612_audit_logs_hotel_scope`, `20260612_query_performance_indexes`.

**Ramas a cubrir (anti-pattern guard #2 — el trabajo está disperso):** rama actual `fix/analytics-deploy-readiness`. Otras con trabajo de features relevante:
- `horde/t1-payment-req`, `horde/t2-checkin-gate`, `horde/t3-change-dates`, `horde/t4-waitlist`, `horde/t5-daily-rates`, `horde/t6-reoptimize` → mapean 1:1 a épicas BRM (pagos, check-in gate §7.1, cambio fechas §8.3/8.4, lista de espera §9.2, tarifas §13/calendario, reoptimización §5.2).
- `feature/rate-calendar-readonly`, `feature/adminpmsmaster`, `dashboard-de-datos`, `next`, `codex/access-check`, `codex/resend-transaccional-mail`, `horde/s02..s08`.
- Múltiples `worktree-agent-*` (probablemente WIP de agentes; verificar si tienen commits únicos no mergeados).

**Tooling confirmado:** `codex-cli 0.131.0` disponible en PATH → subagentes Codex viables. Agent type: `codex:codex-rescue` (vía Bash/runtime). Para fan-out de lectura: `Explore` / `general-purpose`.

### "Allowed methods" para esta auditoría (cómo medir, sin inventar)
- **Evidencia = código + tests, no docs.** Un requisito cuenta como "implementado" solo si hay: (a) modelo/campo, (b) lógica en servicio/endpoint, y (c) test que lo ejerce. Si falta (c), marcar "implementado sin verificación".
- **Verificar por rama** con `git log <branch> --oneline` y `git diff main...<branch> --stat` antes de afirmar dónde vive una feature.
- **Citar siempre** `archivo:línea`. Sin cita → el orquestador rechaza el hallazgo y redespliega (Subagent Reporting Contract).

### Anti-patterns a prevenir
1. Reportar "no implementado" sin un `grep`/`Read` que lo respalde (el repo está más avanzado que el tracker).
2. Confiar en los % de `brm-status.md` (obsoleto) o en docs `*_SUMMARY_*`/`*_COMPLETE*` autogenerados sin verificar contra código.
3. Auditar solo `main`/rama actual e ignorar ramas `horde/*` donde vive media feature.
4. Confundir "existe un endpoint" con "cumple la regla de negocio" (ej. §7.1 "pago completo antes de check-in" requiere un *guard*, no solo un endpoint de check-in).

---

## Modelo de delegación

- **Orquestador (este chat):** trocea el BRM en workstreams, redacta prompts de subagente, consolida hallazgos, resuelve conflictos entre ramas, escribe el reporte final. NO delega la síntesis.
- **Subagentes Codex (razonamiento variable):** un workstream por subagente. Reasoning asignado por complejidad/riesgo de la épica:
  - 🔴 **high** — lógica algorítmica o crítica de seguridad/dinero (Motor de reservas, Pagos/concurrencia, Multi-tenant/Auditoría).
  - 🟡 **medium** — máquinas de estado y flujos (Check-in/out, Cambios/extensiones, OTA, Overbooking/waitlist, Calendario).
  - 🟢 **low** — CRUD + reglas simples (Huéspedes, Empresa, Habitaciones, Bloqueos, Emails, API pública).
- Cada subagente DEBE devolver el **Subagent Reporting Contract**: (1) fuentes leídas, (2) hallazgos concretos con `archivo:línea`, (3) ubicación de tests que cubren/faltan, (4) confianza + gaps conocidos.

---

## Phase 1 — Inventario de ramas (barrera, 1 subagente, low)

**Qué hacer (copiar, no transformar):** para cada rama no-`main`, ejecutar y capturar:
```
git log main..<branch> --oneline          # commits únicos
git diff main...<branch> --stat            # archivos tocados
```
Producir una tabla `rama → épicas BRM tocadas (heurística por path) → ¿mergeada a main? → commits únicos`. Marcar `worktree-agent-*` sin commits únicos como descartables.

**Verificación:** la tabla cubre las 7 ramas `horde/t*`, las `feature/*`, `next`, `codex/*`. Cada fila cita al menos un path de archivo.
**Salida:** `BRANCH_INVENTORY` (tabla). El orquestador la usa para decirle a cada subagente de Phase 2 **qué rama(s) revisar** por épica.

---

## Phase 2 — Auditoría por workstream (paralelo, pipeline; subagentes Codex)

Cada workstream produce un `EPIC_AUDIT` con, por sub-regla del BRM: `estado ∈ {✅ implementado+test, 🟡 implementado sin test, 🟠 parcial, 🔴 ausente}`, evidencia `archivo:línea`, y la rama donde vive.

### WS-A 🔴 high — Motor de reservas y restricción motriz (BRM §5, §6, §9)
Reglas: §5.1 algoritmo de asignación, §5.2 reoptimización continua, §5.3 movimiento manual protege reserva, §5.4 grupos de movimientos, §5.5 auditoría de movimiento automático, §5.6 motor configurable por hotel, §6 restricción motriz, §9.1 overbooking manual, §9.2 lista de espera.
Código: `app/services/allocation_engine.py`, `allocation_{policy,runtime,learning}_service.py`, `app/models/{allocation,movement}.py`, `app/api/allocation_policy.py`. Ramas: `horde/t4-waitlist`, `horde/t6-reoptimize`.
Verificación: grep `movement_group`, `reoptim`, `waitlist`/`lista_espera`, `protect`; correlacionar con migración `20260611_v72_movement_groups`. Tests en `tests/` que ejerzan reasignación.

### WS-B 🔴 high — Pagos, links y webhooks (BRM §12, §3.5)
Reglas: §12.1 solicitar pago, §12.2 link compartible, §12.3 recargos por método, §3.5 pago diferido (empresa); concurrencia e idempotencia de webhooks.
Código: `app/services/payment_service.py`, `payment_link_service.py`, `payment_webhook_service.py`, `app/api/{payments,payment_links,payment_webhooks}.py`, `app/models/{payment,transaction}.py`. Ramas: `horde/t1-payment-req`. Migración `20260611_payment_core_tables`.
Verificación: tests `test_payment_service.py`, `test_mercadopago_webhook_signature.py`. Confirmar validación de firma, idempotencia (clave única), y recargos.

### WS-C 🔴 high — Multi-tenant, usuarios/roles y auditoría (BRM §1, Épicas 1 y 26)
Reglas: §1 obligatoriedad global, filtrado multi-tenant obligatorio, matriz de permisos, auditoría centralizada + soft delete + scope por hotel.
Código: `app/api/{auth,users,audit}.py`, `app/services/{security,audit_service}.py`, `app/models/{user,hotel_membership,audit_log}.py`. Migración `20260612_audit_logs_hotel_scope`.
Verificación: `test_runtime_security.py`, `test_rate_limiting.py`. Grep que TODA query de negocio filtre por `hotel_id`; detectar endpoints sin guard de tenant.

### WS-D 🟡 medium — Check-in/out (BRM §7)
Reglas: §7.1 pago completo antes de check-in (GUARD, no solo endpoint), §7.2 prefinalizado, §7.3 no parcial, §7.4 agregar huéspedes posteriores, §7.5 no check-out parcial, §7.6 tardío, §7.7 no-show.
Código: `app/api/checkin.py`, `app/services/checkin_service.py`. Ramas: `horde/t2-checkin-gate`.
Verificación: test que un check-in con saldo pendiente sea rechazado (regla §7.1).

### WS-E 🟡 medium — Reservas: cambios y extensiones (BRM §8, §11)
Reglas: §8.2 cambio de habitación durante estadía, §8.3 cambio de fechas sin pago, §8.4 cambio de fechas con pago, §8.5 extensión, §8.6 extensión con habitación ya vendida, §11 reserva telefónica/manual.
Código: `app/services/reservation_operations_service.py`, `reservation_action_service.py`, `app/api/reservations.py`, `app/schemas/reservation_operations.py`, `app/models/reservation.py`. Ramas: `horde/t3-change-dates`. Migración `20260611_v72_reservation_fields`.
Verificación: tests V72 recientes (commit `14d886f`). Confirmar manejo de extensión sobre habitación vendida (debe disparar movimiento/conflicto).

### WS-F 🟡 medium — OTA y duplicados (BRM §10)
Reglas: §10.1 Booking ID obligatorio, §10.2 OTA sin garantía / pisada interna.
Código: `app/api/ota_webhooks.py`, `app/services/ota/`, `ota_service.py`, `app/models/{ota,ota_core}.py`. Migraciones `*_ota_hardening`, `*_ota_allocation_foundation`.
Verificación: dedup por Booking ID; test de webhook OTA.

### WS-G 🟡 medium — Calendario/planilla y tarifas (BRM §13)
Reglas: §13.1 pendiente de pago, §13.2 OTA sin pago, §13.3 disponible con revisión; edición de tarifas/calendario.
Código: `app/api/{rooms,reports,analytics}.py`, `app/services/{pricing_policy_service,analytics_service,read_model_cache}.py`, `room_state_events.py`. Ramas: `horde/t5-daily-rates`, `feature/rate-calendar-readonly`.
Verificación: estados de celda del calendario reflejan las 3 reglas.

### WS-H 🟢 low — Huéspedes (BRM §2)
Reglas: §2.1 huésped único por hotel, §2.2 corrección de datos, §2.3 sin merge manual V1, §2.4 búsqueda rápida, §2.5 ficha rápida, §2.6 rating y tags, §2.7 prohibido alojar (alerts).
Código: `app/services/{guest_service,guest_profile}.py`, `app/api/guests.py`, `app/models/guest.py`. Migración `20260611_v72_guest_rating_alerts`.
Verificación: tests de alerts/rating del commit V72; unicidad por `(hotel_id, documento)`.

### WS-I 🟢 low — Empresa, Habitaciones, Bloqueos (BRM §3, §4, §14)
Reglas: §3 reservas de empresa (datos mínimos, vouchers, asignación manual), §4 habitaciones + §4.1 score + accesibilidad, §14 bloqueos/mantenimiento.
Código: `app/api/{companies,rooms,commercial}.py`, `app/services/{commercial_service,hotel_service}.py`, `app/models/{company,room,operations}.py`. Migración `20260611_v72_room_score_accessibility`.

### WS-J 🟢 low — Emails/Gmail y API pública (BRM §15, §16)
Reglas: §15.1 Gmail del hotel, §15.2 email plataforma; §16.1 WhatsApp bot, §16.2 web propia/booking engine.
Código: `app/services/email/`, `email_service.py`, `hotel_outbound_email_service.py`, `app/api/{email,gmail_integration,integrations,connections}.py`. Ramas: `codex/resend-transaccional-mail`.
Verificación: cruzar con docs `EMAIL_SYSTEM_*` (no autogenerados-confiables) contra código real.

---

## Phase 3 — Consolidación (orquestador, sin subagente)

1. Fusionar los 10 `EPIC_AUDIT` + `BRANCH_INVENTORY` en una matriz: **Épica → sub-regla → estado → evidencia → rama → acción pendiente**.
2. Calcular % real por épica (✅=1, 🟡=0.7, 🟠=0.4, 🔴=0) y % global. Contrastar explícitamente con el "20%" obsoleto de `brm-status.md`.
3. Listar **Top gaps bloqueadores** (reglas 🔴/🟠 en épicas marcadas BLOQUEADOR en BRM) y **riesgos de seguridad** (cualquier endpoint WS-C sin guard de tenant).
4. Escribir `docs/BRM_V72_AUDIT_RESULTS.md` y actualizar `vault/hotel-chipre-pms/brm-status.md`.

---

## Phase 4 — Verificación (cierre)

- [ ] Cada fila de la matriz cita `archivo:línea` real (muestreo: re-`Read` de 10 citas al azar; ninguna inventada).
- [ ] Toda rama `horde/t*` y `feature/*` aparece en `BRANCH_INVENTORY` con commits únicos resueltos (mergeada / pendiente).
- [ ] Las 32 épicas/secciones de negocio del BRM tienen veredicto (ninguna "sin auditar").
- [ ] `pytest` corre verde en la rama base; discrepancias test-vs-realidad anotadas.
- [ ] Anti-pattern check: `grep` confirma que ningún hallazgo "🔴 ausente" tenía en realidad implementación en otra rama.
- [ ] Reporte final entregado + `brm-status.md` actualizado con fecha 2026-06-24.

---

### Mapa rápido reasoning Codex → workstream
| Reasoning | Workstreams |
|---|---|
| 🔴 high | WS-A Motor, WS-B Pagos, WS-C Multi-tenant/Auditoría |
| 🟡 medium | WS-D Check-in, WS-E Cambios/extensiones, WS-F OTA, WS-G Calendario |
| 🟢 low | WS-H Huéspedes, WS-I Empresa/Hab/Bloqueos, WS-J Emails/API, + Phase 1 inventario |
