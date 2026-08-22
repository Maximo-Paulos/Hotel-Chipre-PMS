# Contrato canónico de auditoría

Estado: `VERIFY` para TECH-0070/TECH-0071. Este documento formaliza el
contrato sin fusionar tablas ni cambiar el esquema. La evidencia corresponde al
checkout `8a53fc309758735bf08b2cbe5d3dadfb6e2dd4ea8`.

## Alcance y reglas

Hay tres planos con trust boundaries diferentes:

| Tabla | Autoridad canónica | Alcance | Forma del evento |
|---|---|---|---|
| `audit_logs` (`AuditLog`) | Mutaciones de filas del dominio hotelero | Un hotel | `create`, `update`, `delete`, `status_change`, con `before/after` redactado por el writer |
| `security_audit_logs` (`SecurityAuditLog`) | Identidad, autenticación, autorización y operaciones sensibles de seguridad | Un hotel; los eventos de identidad se proyectan por membership activa | `action` libre, actor denormalizado, recurso y detalle operativo |
| `master_admin_audit_events` (`MasterAdminAuditEvent`) | Acciones del control plane del proveedor/Master Admin | Global, no tenant-scoped | Acción, outcome, target, request context y metadata redactada |

`HotelAuditEvent` es una cuarta proyección de eventos de negocio/analytics que
ya consume TECH-0070. No reemplaza a ninguna de las tres tablas de este
contrato y se mantiene separado explícitamente.

Reglas no negociables:

1. Una fila sólo tiene una tabla autoridad. Una coincidencia temporal o de
   recurso no se deduplica silenciosamente.
2. Los lectores deben conservar `source` y `source_id` para distinguir una
   mutación de fila, un evento de seguridad y un evento de negocio.
3. Ningún usuario del producto puede editar o borrar eventos mediante una ruta
   ordinaria. La escritura se hace por los writers existentes.
4. Los eventos críticos no se escriben en otra tabla sólo para hacerlos
   visibles en una pantalla. La visibilidad se resuelve en la proyección de
   lectura.

## Inventario real de escritores

### `AuditLog`: ledger de mutaciones

El writer canónico es `app/services/audit_log_service.py`: `create_audit_log`,
`queue_audit_log` y `safe_create_audit_log` construyen la fila y llaman
`db.add`; `safe_create_audit_log` usa un savepoint para que un fallo de la
auditoría no revierta la mutación del negocio. El decorator
`app/decorators/audit_hooks.py::audited_change` agrega el mismo tipo de fila
después de una mutación exitosa.

Los callers actuales cubren estas familias de `table_name` y acciones:

- `reservations`: create/update/delete/status change, incluidas operaciones de
  reservas y movimientos de habitación.
- `guests`, `guest_tags`, `guest_companions`: create/update/status change.
- `rooms`, `stock_items`, `stock_locations`, `linen_items` y
  `price_periods`: altas, cambios y bajas lógicas donde el caller lo indica.
- `hotel_memberships`, `staff_invitations` y `company_documents`: cambios de
  staff/documentos.
- `daily_rates`, `payment_surcharges`, `billing_adjustments` y
  `payment_proofs`: cambios de tarifas/cargos/evidencia de pago.

La cobertura no debe interpretarse como “toda mutación de toda tabla”: el
ledger sólo registra los callers que invocan los writers/decorator actuales.
`AuditActionEnum` es la autoridad del tipo de mutación; los detalles de
seguridad no pertenecen aquí.

### `SecurityAuditLog`: seguridad y acceso tenant-scoped

Las escrituras directas están en `app/api/auth.py`,
`app/api/settings_security.py` y servicios de permisos, memberships, grants,
check-in, huéspedes, restricciones, documentos, OTA y movimientos de
habitaciones. Las acciones concretas observadas son:

- identidad/MFA/sesiones: `auth.login.success`,
  `google_auth.linked`, `google_auth.account_reclaimed`,
  `google_auth.unlinked`, `apple_auth.linked`,
  `apple_auth.account_reclaimed`, `apple_auth.unlinked`, `mfa.enrolled`,
  `mfa.disabled`, `mfa.recovery_codes_regenerated` y
  `security.sessions.revoked_all`;
- permisos y autorización: `permission.override.updated`,
  `permission.user_override.updated`, sus variantes `restored`,
  `permission.role_overrides.restored`,
  `permission.user_overrides.restored` y `permission.denied`;
- operaciones sensibles: `membership.primary_owner.transferred`,
  `temporary_grant.requested|approved|denied|revoked|expired|consumed`,
  `checkin.prohibido_override`, `guest.restriction.override`,
  `company_document.signature_status_changed`,
  `room_movement_group.reverted`/`revert_partial`, y los eventos de OTA
  manual (`ota.manual_reservation.created|updated`,
  `ota.no_guarantee.internal_release|waitlist_promotion`);
- actividad sensible de huéspedes: `guest.tag.added`, `guest.tag.resolved` y
  `guest.rating.updated`.

Los eventos de login exitoso se proyectan una vez por cada membership activa
del usuario porque `SecurityAuditLog.hotel_id` es obligatorio. Un login fallido
normal no escribe ninguna de estas tres tablas: el endpoint rechaza las
credenciales antes de llamar al writer. En el plano Master, los fallos de
password/PIN actualizan `MasterAdminAuthLockout`, pero tampoco crean un
`MasterAdminAuditEvent`.

### `MasterAdminAuditEvent`: control plane global

`app/master_admin/security.py::audit_master_action` es el único writer
aplicativo. Sus callers cubren login/logout, enrolamiento/confirmación/
desactivación MFA, cambios de billing policy, endpoints de email retirados,
prueba de email, conexión/desconexión de Stripe, recepción de webhook Stripe y
`comped_override_grant` desde `app/api/subscription.py`. El evento conserva
`outcome`, target y request context; metadata pasa por la redacción del
control plane.

No se copia automáticamente a `AuditLog` ni a `SecurityAuditLog`: una acción
Master puede afectar varios hoteles y su autoridad es global.

## Solapamiento confirmado

El solapamiento no es un duplicado accidental; es una misma operación vista
desde dos autoridades:

| Operación | `AuditLog` | `SecurityAuditLog` | `MasterAdminAuditEvent` |
|---|---|---|---|
| Transferencia de Primary Owner | `UPDATE` de `hotel_memberships` con before/after | `membership.primary_owner.transferred` | No |
| Agregar/resolver tag o cambiar rating | `CREATE`/`STATUS_CHANGE`/`UPDATE` por `audited_change` | `guest.tag.added`, `guest.tag.resolved`, `guest.rating.updated` | No |
| Crear movimiento agrupado de habitación | `UPDATE` de la reserva | No en la creación | No |
| Revertir movimiento agrupado | No hay ledger de fila equivalente en ese método | `room_movement_group.reverted` o `revert_partial` | No |
| Login exitoso de owner | No | `auth.login.success`, una fila por membership activa | No |
| Login fallido de owner | No | No | No |
| Login/acción exitosa de Master Admin | No | No | Sí, si el flujo llega a `audit_master_action` |
| Login Master fallido | No | No | No; se actualiza `MasterAdminAuthLockout` |

La duplicación intencional debe reconciliarse por el contexto de la operación,
no por igualdad de texto: una fila `row_mutation` y una fila
`security_event` pueden compartir `hotel_id`, actor, recurso y ventana de
tiempo, pero siguen siendo dos evidencias distintas.

## Inmutabilidad y retención

### Evidencia actual

- `AuditLog` sólo se agrega desde los writers/decorator señalados; no hay
  `UPDATE`, `DELETE` ni endpoint de edición/borrado en `app/`.
- `SecurityAuditLog` sólo se agrega desde los writers de seguridad; los
  endpoints existentes son lectores y el timeline está protegido para
  `owner`/`co_owner`.
- `MasterAdminAuditEvent` se agrega y se consulta desde el panel Master; no
  hay ruta de mutación de eventos.
- La migración `7b14658560e1_restrict_audit_log_hotel_deletion` y el modelo
  `AuditLog.hotel_id` usan `RESTRICT`, por lo que el borrado de un hotel no
  puede destruir silenciosamente `audit_logs`.

Esto es una garantía append-only a nivel aplicación. No equivale a una
política contra un propietario directo de la base ni a una firma/hash de cada
fila; esos controles quedan fuera de este cambio.

### Retención: estado real y política canónica

No existe hoy un job de retención/purge para estas tres tablas en `app/` ni en
`app/tasks/`. Por tanto, el texto histórico del modelo `AuditLog` que menciona
un background job no es evidencia de que el job exista.

La política canónica queda definida así, con implementación pendiente donde se
indica:

| Tabla | Política | Estado actual |
|---|---|---|
| `audit_logs` | Retener durante la vida del hotel y conservarlo para reconciliación. Sólo un workflow explícito de retención/archivo aprobado puede eliminar datos vencidos; debe comprobar backup/archivo y dejar evidencia. | No hay purge; `RESTRICT` protege el borrado del hotel. |
| `security_audit_logs` | Misma retención mínima tenant-scoped que `audit_logs`; no borrar por una operación ordinaria del hotel. La retención debe ser explícita y auditable. | No hay purge. El FK/migración usa `CASCADE`, por lo que un borrado directo de hotel podría eliminar filas: es un gap de retención de esquema a resolver en un cambio posterior. No hay endpoint de borrado de hotel en `app/`. |
| `master_admin_audit_events` | Retener independientemente de hoteles y usuarios; `actor_user_id` puede quedar `NULL` por `SET NULL`. Sólo archivo/purge de plataforma con autorización de break-glass, motivo, ventana y evidencia. | No hay purge ni endpoint de mutación. |

El cambio actual no introduce una migración ni altera el `CASCADE` de
`security_audit_logs`, porque el alcance exige documentación/tests y no una
migración de esquema. TECH-0070/0071 no debe declararse `VERIFIED` por esta
documentación sola.

## Lectura unificada y reconciliación

La lectura existente de TECH-0070 no se reescribe aquí:

- `GET /api/settings/security/audit-timeline` y su export CSV delegan en
  `app/services/audit_timeline_service.py::list_audit_timeline`.
- El servicio consulta `AuditLog`, `HotelAuditEvent` y `SecurityAuditLog`,
  filtra por `hotel_id` y fechas, normaliza timestamps a UTC, ordena por
  `(created_at, source, source_id)`, pagina y aplica redacción antes de
  responder.
- La respuesta conserva `source` (`row_mutation`, `business_event` o
  `security_event`) y no intenta deduplicar solapamientos.
- `MasterAdminAuditEvent` no entra en esa timeline tenant-scoped. Se consulta
  por separado en `GET /api/master-admin/audit/events`, detrás de la sesión
  Master Admin. Para un informe cross-plane se deben consultar ambas
  superficies con privilegio explícito y reconciliar por `request_id` cuando
  exista, luego por actor/target/ventana temporal; nunca inferir equivalencia
  sólo por `action`.

Esta separación conserva el límite entre operaciones privadas de un hotel y
el control plane del proveedor. Un futuro informe que necesite ambos planos
debe ser una vista nueva con autorización, redacción, retención y auditoría
propias; no una fusión de tablas.

## Tests y estado de cierre

`tests/test_settings_security_api.py` verifica tenant scoping, roles,
redacción, orden/paginación y export de TECH-0070. La regresión añadida en ese
archivo fija además que las superficies de lectura de las tres auditorías no
aceptan `PUT`, `PATCH` ni `DELETE`.

Queda pendiente para cerrar el contrato en producción:

- implementar y probar jobs de retención/archivo por tabla;
- resolver el `CASCADE` de `security_audit_logs` mediante migración segura y
  definir el workflow autorizado de borrado/archivo de hotel;
- decidir si los fallos de login deben tener un evento de seguridad explícito
  sin reintroducir enumeración ni PII;
- verificar con PostgreSQL/RLS y un restore drill que la retención y la
  reconciliación sobreviven al ciclo operativo completo.
