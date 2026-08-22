# Plan de consolidación de modelos de suscripción

## Resumen ejecutivo

**Estado: VERIFY / no seguro para consolidar sólo el ORM.** La consolidación de
`subscription_plans`/`hotel_subscriptions`/`subscription_entitlements` y
`subscriptions`/`subscription_events`/`subscription_adjustments` requeriría
resolver datos productivos existentes, conflictos por hotel y trazabilidad de
ajustes. En esta tarea no se migraron filas, no se eliminó ninguna tabla o
modelo y no se cambió el schema.

El código nuevo (`subscription_entitlements.py`) trata `Subscription` v2 como
la autoridad de su snapshot contractual y mantiene una proyección compatible
en legacy. Sin embargo, partes operativas todavía consultan legacy
directamente. Por eso hoy no hay una única autoridad global ni un orden de
precedencia que permita afirmar que una consolidación de código, sin backfill,
sea segura para hoteles reales.

## 1. Estado real verificado en código

Verificado en el checkout `codex/debt-subscription-model-consolidation`, base
`origin/main`, SHA `8a53fc3` (cambios de esta tarea aún sin commit), contra el
código ejecutable, tests locales y migraciones presentes.

### 1.1 Modelos y campos

| Familia | Fuente/uso actual |
| --- | --- |
| Legacy `SubscriptionPlan` | Catálogo persistido: `code`, `name`, `room_limit`, precio/features y filas `SubscriptionEntitlement`. |
| Legacy `HotelSubscription` | Estado por hotel, `plan_id`, `status`, `room_limit_override` y fechas de billing legacy. Tiene unicidad por hotel. |
| Legacy `HotelEntitlementOverride` | Overrides por hotel para códigos como `rooms.max_active`, `reports.advanced` y `ota.sync`. |
| V2 `Subscription` | Snapshot canónico del servicio nuevo: `plan`, `status`, `room_limit`, `staff_limit`, fechas de trial/período/gracia y `can_write_cache`. Un registro por hotel. |
| V2 `SubscriptionEvent` | Eventos append-only de transiciones v2. |
| V2 `SubscriptionAdjustment` | Ledger append-only de ajustes comped/override, con idempotencia y actor. |
| `HotelConfiguration.subscription_active` | Bandera adicional legacy leída por `require_subscription_active`; no es una derivación exclusiva de v2. |

### 1.2 Qué decide cada servicio

`app/services/subscription_entitlements.py`:

- `get_subscription_snapshot()` consulta sólo `Subscription` v2 para plan,
  estado, límites de habitaciones/staff y `can_write`.
- Si falta v2 y el enforcement está apagado, crea `Subscription` starter y
  llama a `_sync_legacy_tables()`. Si el enforcement está encendido y no hay
  fila, devuelve un snapshot virtual starter/suspended sin persistirlo.
- Trial, suspensión, comped y cambio de plan escriben v2, registran eventos
  cuando corresponde y actualizan `SubscriptionPlan`, `HotelSubscription` y
  `HotelConfiguration.subscription_active` mediante `_sync_legacy_tables()`.
- El middleware opcional de enforcement, `/api/subscription/status`, el
  onboarding y `master_admin` usan este snapshot v2.

`app/services/subscription_service.py` mantiene el camino operativo legacy:

- `get_entitlements()` hace `ensure_subscription()` sobre
  `HotelSubscription`, carga `SubscriptionPlan.entitlements`, aplica
  `HotelEntitlementOverride` y, al final, deja que
  `HotelSubscription.room_limit_override` gane para `rooms.max_active`.
- `ensure_room_within_limit()` y, por tanto, creación/reactivación de rooms,
  leen ese resultado legacy. `require_subscription_active()` consulta
  `HotelConfiguration.subscription_active` y `HotelSubscription.status`.
- `get_effective_staff_limit()` usa v2 primero si existe `staff_limit`; si no,
  cae al plan legacy y `PLAN_CATALOG`. Este es el único fallback v2-first
  explícito; no constituye una regla global para los demás límites.
- `/api/subscription/entitlements`, sus overrides y la inicialización de
  `/api/subscription/plans` siguen pasando por este servicio legacy.

Por lo tanto, cuando hay conflicto no existe un orden único:

| Decisión | Precedencia real |
| --- | --- |
| Snapshot/status/write access | V2 `Subscription`; legacy sólo se actualiza como proyección. |
| Límite de habitaciones usado por rooms | Legacy `HotelEntitlementOverride`/`HotelSubscription.room_limit_override`/plan; el `room_limit` v2 no participa directamente. |
| Límite de staff | V2 `staff_limit`; fallback a plan legacy sólo si falta v2. |
| Estado para `require_subscription_active` | `HotelConfiguration.subscription_active` y `HotelSubscription.status`, condicionado al flag de enforcement. |
| Conteos y dashboard master-admin | V2 `Subscription`. |

## 2. Inconsistencias de escritura encontradas y corregidas ahora

Se encontraron caminos reales que podían crear o cambiar sólo legacy:

1. `app/services/hotel_service.py::_ensure_membership_and_subscription()`
   creaba directamente `HotelSubscription` durante el bootstrap de login/auth.
2. `app/services/subscription_service.py::ensure_subscription()` creaba
   directamente una suscripción legacy cuando se invocaba desde plans o
   entitlements.
3. `set_subscription_plan()` era un entry point legacy que cambiaba sólo
   `HotelSubscription`; aunque no tiene caller activo en `app/`, podía dejar
   inconsistencia a cualquier consumidor interno futuro.
4. El override operativo `rooms.max_active` actualizaba sólo el override
   legacy. Ahora su escritura/restauración también actualiza
   `Subscription.room_limit` y vuelve a proyectar legacy.

Corrección aplicada: las nuevas altas, cambios de plan y cambios de límite de
habitaciones pasan por funciones de `subscription_entitlements.py`, que
actualizan v2 y su proyección legacy dentro de la misma sesión/transacción del
caller. Se agregaron regresiones para bootstrap, cambio de plan y override de
room limit. No se hizo backfill de hoteles que ya tengan sólo legacy o valores
conflictivos.

Queda deliberadamente legacy-only el almacenamiento de códigos de entitlement
arbitrarios como `reports.advanced` y `ota.sync`: v2 no tiene un modelo
equivalente para esos códigos. No se inventó una tabla o mapping nuevo en una
tarea que toca billing vivo.

## 3. Por qué no se ejecuta una consolidación de datos ahora

Una consolidación segura debe responder, por hotel:

- cuál fila es activa en cada familia y si ambas familias existen;
- cómo mapear planes legacy fuera de `starter/pro/ultra`;
- cómo resolver diferencias entre `room_limit`, `room_limit_override`, filas de
  entitlement y `staff_limit`;
- cómo conservar eventos y ajustes v2 como evidencia append-only;
- cómo tratar trial, past-due, paused, suspended, comped y
  `subscription_active` sin cortar escritura de un hotel real;
- cómo hacer rollback sin perder una decisión comercial ya aplicada.

El repositorio no contiene evidencia provider-bound de los datos productivos ni
una autorización humana para cambiar billing. La spec maestra exige cambios
backward-compatible y prohíbe migrar producción sin autorización humana. En
consecuencia, este cambio queda en código compatible y el plan de datos queda
pendiente de aprobación.

## 4. Plan de migración por fases — requiere aprobación humana

### Fase 0 — Preparación y freeze de contrato

1. Nombrar formalmente `Subscription` v2 como autoridad futura y mantener
   legacy read-compatible durante la transición.
2. Acordar el mapping de estados/planes y la política para conflictos; ningún
   valor se sobreescribe silenciosamente.
3. Obtener backup verificable, ventana de mantenimiento/downtime aprobada,
   rollback probado y snapshot cifrado de conteos/checksums por hotel.
4. Medir filas, duplicados, hoteles legacy-only, v2-only y diferencias por
   plan/status/límites/overrides. Emitir un reporte de conflictos antes de
   escribir.

### Fase 1 — Backfill controlado y reversible

1. Ejecutar en una base restaurada de prueba y luego por lotes pequeños en la
   ventana aprobada; no borrar legacy.
2. Crear o completar v2 desde legacy sólo para filas clasificadas como
   unívocas. Separar conflictos para decisión humana.
3. Conservar el identificador/origen legacy y generar eventos de backfill
   auditables, sin convertirlos en eventos comerciales falsos.
4. Reconciliar conteos y snapshots v2↔legacy después de cada lote; detenerse
   ante cualquier pérdida, duplicación o cambio inesperado.

### Fase 2 — Dual-read observado y canary

1. Mantener dual-write a través del servicio único.
2. Leer v2 para status, límites y enforcement con una comparación shadow
   contra legacy, métricas de divergencia y alertas por hotel.
3. Habilitar por un conjunto pequeño de hoteles sintéticos y luego un canary
   humano aprobado; observar reservas, rooms, staff invitations y panel
   master-admin.

### Fase 3 — Cutover y retiro futuro

1. Tras reconciliación sostenida y aprobación del responsable de billing,
   cambiar el read path operativo a v2 mediante flag reversible.
2. Mantener tablas/modelos legacy en read-only durante el período de retención
   acordado y conservar el plan de rollback.
3. Sólo con otra aprobación explícita, backup y ventana controlada, evaluar
   retirar escrituras legacy y mucho después retirar tablas/modelos. Eso queda
   fuera de esta tarea.

## 5. Validación y riesgos

- Código cambiado: `app/services/hotel_service.py`,
  `app/services/subscription_entitlements.py`,
  `app/services/subscription_service.py` y regresiones en
  `tests/test_subscription_tiers.py`.
- Migraciones/schema: ninguna.
- Datos productivos: no consultados, no modificados y no migrados.
- Validación local: compilación, `git diff --check` y un chequeo directo de
  servicios pasaron. `.venv/bin/python -m pytest -q` no pudo completar la
  colección en este sandbox porque faltan `pyotp` y `argon2-cffi` y la red a
  PyPI está bloqueada; no se reporta como suite verde.
- Riesgo pendiente: mientras exista el dual-read legacy/v2, una edición fuera
  de los servicios o una fila histórica conflictiva puede producir respuestas
  distintas entre status, enforcement, rooms/staff y entitlements.
- Certeza: `confirmed` para los caminos de código y tests locales citados;
  `needs-verification` para conteos, conflictos y estado de datos productivos.
