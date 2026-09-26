# Auth, seguridad y tenancy

## Estado

`confirmed` para el diff local de autorización basado en `main` `1b6ca04597722a24f7cfe7a1d5b6e7ce82688d1e` y sus pruebas; `needs-verification` para publicación, QA autenticada por rol y cobertura exhaustiva. El diff descrito aquí todavía no está desplegado.

## Modelo vigente

El rol operativo pertenece a `HotelMembership` (hotel + usuario + rol + estado), no al usuario global. Cada ruta sensible debe autenticar y resolver una capability dentro del tenant actual. La precedencia es `invariant > user override > hotel/role override > role default > deny`; las decisiones de alcance inmutable se aplican antes de los overrides. El backend es autoridad; las consultas tenant-scoped y PostgreSQL RLS son barreras separadas.

Las APIs de `app/api` ya no invocan `require_roles()` ni `require_roles_and_permission()` directamente. Se conservaron verificaciones de rol que expresan invariantes de negocio, administración de jerarquías o redacción de campos; no son equivalentes a una autorización gruesa de ruta. El contrato AST está en `tests/test_rbac_permission_consolidation.py`.

El catálogo local tiene 94 permisos canónicos. Quince capabilities tienen alcance de rol inmutable: configuración sensible/usuarios, suscripción, seguridad, pruebas, reportes diarios, acciones del asistente, grants temporales y configuración comercial se limitan a owner/co-owner; demo-seed y borrado lógico de reservas se limitan a owner/co-owner/manager. El seed es idempotente y corre con el inicio de la aplicación; no se agregó migración ni dependencia.

La aprobación de diferencia de caja y la recepción de custodia usan capabilities distintas y step-up MFA: el ticket es corto, de un solo uso y ligado a la acción/ruta. La capability de custodia es owner-only. La aprobación adicional de caja se verifica solo cuando el cierre solicita explícitamente aprobar una diferencia. El cierre deja la recepción en `PENDING`; no auto-confirma efectivo por el hecho de que quien cierra sea owner. La confirmación se realiza aparte por el endpoint owner-only con step-up.

## Validación local de esta revisión

- Backend completo en SQLite en memoria: 2.136 passed, 21 skipped, 12 xfailed, 37 warnings. Se excluyeron la prueba de migración destructiva `tests/integration/test_postgres_migrations.py` y la prueba que necesita PostgreSQL real `tests/test_rls_live_verification.py`.
- Pruebas focales de permisos/caja/guards: 123 passed.
- Frontend sin cambios de fuente: 44 tests, typecheck, lint y build aprobados; la build mantiene el warning de chunk principal grande (~637 kB minificado).
- `git diff --check` pasó. Ruff no está instalado. No hubo QA autenticada de este diff, consultas directas a Supabase, pagos, correo, webhooks ni sincronización OTA. No se pidió ni se usó otro TOTP.

## Decisiones/riesgos abiertos

- Decisión de producto (2026-09-25): al cambiar el rol se limpian, en la misma transacción, los `UserPermissionOverride` con `allowed=true` para que una concesión individual no se arrastre silenciosamente a un puesto nuevo. Los overrides con `allowed=false` se conservan como restricciones explícitas. La operación deja un `SecurityAuditLog`; la UI advierte y pide confirmación. Se aplica tanto al cambio directo de rol como al flujo de invitación que cambia una membership existente.
- `/api/movement-groups/{id}/revert` comparte `reservation:move`; el default incluye receptionist. Confirmar si la reversión de grupos debe usar una capability más estrecha. Esta ruta no forma parte del diff actual.
- Hace falta comprobar allow/deny por identidad owner/manager/recepción/housekeeping en el deploy después de resolver los gates de producto. La carga histórica de la matriz no es evidencia de esta revisión.
- El informe de decisión y detalle histórico están en `docs/decisions/authorization-engine-evaluation-adr.md`. La recomendación sigue siendo conservar el motor actual y no añadir Casbin/OpenFGA/SpiceDB/OPA hasta validar casos ReBAC reales.
