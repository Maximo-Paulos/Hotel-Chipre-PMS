# TECH-0000 — Auditoría sistémica y matriz canónica

Fecha de auditoría: 2026-08-21  
Checkout auditado: `codex/tech0000-audit-matrix`  
Código auditado: `6fd71f08de84b5c891b9ea9e47d8f802831f964f` (`origin/main`)  
Tipo de evidencia: checkout local, `git log`, código, tests y migraciones versionados.

## 1. Alcance y método

Se leyó completo `docs/HOTEL_PMS_MASTER_DEVELOPMENT_SPEC.md`, además de `CLAUDE.md` y `knowledge/00-control/STATUS-TODAY.md`. Se inspeccionaron `app/api/`, `app/services/`, `app/models/`, `frontend/src/`, `frontend/public/`, `alembic/versions/`, `tests/`, `.github/workflows/`, `render.yaml` y `vercel.json`.

La fuente de verdad usada para el estado es, en este orden: código/configuración del checkout, tests versionados, migraciones y commits alcanzables desde `HEAD`. El Graphify local fue consultado como orientación, pero no se usó para cerrar estados porque `graphify check-update` reporta que fue construido desde `b6cd93c`, mientras `HEAD` es `6fd71f0`.

`VERIFIED` exige implementación y evidencia de test suficiente para el alcance completo del bloque. `VERIFY` significa que hay implementación y regresiones reproducibles en el repo, pero falta una parte del acceptance, una prueba de ambiente, cobertura exhaustiva o ejecución actual. La auditoría no ejecutó pytest: este worktree no contiene `.venv/bin/python` y el Python del sistema no tiene `pytest` instalado (`No module named pytest`). Las referencias a tests abajo son archivos y tests presentes en el checkout, no una afirmación de ejecución en esta sesión.

## 2. Inventario canónico vigente

| Dominio | Autoridad vigente observada | Evidencia | Mapa objetivo | Riesgo de transición |
|---|---|---|---|---|
| Identidad y credenciales | `User`, `app/services/security.py`, JWT HS256; Argon2id por defecto y bcrypt heredado | `app/models/user.py:13-31`; `app/services/security.py:23-65`; `tests/test_auth_security.py:223-270` | Identidad global separada de membership y proveedores OIDC por `sub` | `User.role` aún existe como rol de plano plataforma; JWT y cookie conviven |
| Sesiones | `UserSession` revocable, cookie opaca y CSRF; bearer JWT sigue activo | `app/models/user_session.py:17-38`; `app/services/user_session_service.py:106-229`; `app/dependencies/auth.py:59-90` | Sesión revocable como autoridad primaria por superficie | Dos mecanismos activos con semánticas de revocación distintas |
| Multi-tenancy | `AuthContext` resuelve membership activa; filtros `hotel_id`; RLS PostgreSQL declarativo | `app/dependencies/auth.py:93-150`; `alembic/versions/20260724_tenant_rls_context.py:25-183` | Defensa en profundidad con aislamiento probado en PostgreSQL real | Falta prueba exhaustiva de todas las superficies y RLS real ejecutado |
| RBAC | `permission_service` granular más `require_roles` legado | `app/services/permission_service.py:31-117,387-429`; `app/dependencies/auth.py:153-308` | Una autoridad de permisos por hotel, con roles solo como perfiles/defaults | Rutas role-gated y permission-gated siguen mezcladas |
| Membership/Primary Owner | `HotelMembership.is_primary_owner` y `membership_service` | `app/models/hotel_membership.py:12-38`; `app/services/membership_service.py:19-124` | Membership canónica por hotel, Primary Owner separado del rol | `HotelConfiguration.owner_email` se mantiene como proyección legacy |
| Invitaciones | `StaffInvitation` con token hash, consumo atómico y ciclo de vida | `app/services/invitation_service.py:35-124`; `app/api/invitations.py:89-188` | Invitación single-use ligada a hotel, actor, rol e identidad autenticada | Límite de staff depende de entitlements; Apple todavía no está en `HEAD` |
| Auditoría hotel | `AuditLog` para mutaciones, `audit_log_service`, timeline unificado y CSV | `app/models/audit_log.py:34-77`; `app/services/audit_log_service.py:84-153`; `app/api/settings_security.py:180-208` | Ledger append-only consultable por tenant con retención y cobertura completa | Hay otros planos de auditoría y no hay prueba externa de inmutabilidad |
| Auditoría seguridad | `SecurityAuditLog` para eventos de seguridad free-form | `app/models/security_audit_log.py:1-39`; `app/api/auth.py:196-218`; `app/services/permission_service.py:443-455` | Eventos de identidad/seguridad integrados a la trazabilidad canónica | `hotel_id ON DELETE CASCADE` y proyecciones separadas requieren decisión/validación |
| Auditoría master | `MasterAdminAuditEvent` separado del tenant | `app/master_admin/models.py:32-64`; `app/master_admin/security.py:495-560` | Plano de control independiente, con PII mínima y soporte excepcional auditado | Cobertura funcional y métricas SaaS no equivalen todavía al panel objetivo |
| Suscripciones/entitlements | Tablas legacy `subscription_*` y tablas v2 `subscriptions`, con sincronización | `app/models/subscription.py:11-80`; `app/models/subscription_v2.py:29-124`; `app/services/subscription_entitlements.py:76-98` | Un modelo contractual/versionado, separado de permisos, con ledger append-only | Hay dos esquemas y dos caminos de lectura/escritura |
| Analytics | Facts PostgreSQL (`FactReservationDaily`, `FactRoomOccupancyDaily`) y proyección opcional ClickHouse | `app/services/analytics_facts.py:134-364`; `app/services/analytics_warehouse.py:1-99,213-300` | Warehouse elegido por Product Lead, marts versionados y lineage | BigQuery vs ClickHouse/facts sigue abierto; provider no está verificado |
| Master SaaS | Router y sesión master separados, billing policy, hoteles, email, Stripe y audit | `app/master_admin/router.py:63-135,272-351`; `app/master_admin/security.py:1-120` | Control plane con permisos propios, MFA obligatorio, métricas SaaS y soporte temporal | MFA en `HEAD` es opt-in; no se observan MRR/ARR ni operación completa de jobs |
| Infraestructura/CI | Render/Vercel/Supabase declarativos y workflows de preview/release | `render.yaml:1-60`; `.github/workflows/preview-qa.yml:1-40`; `.github/workflows/verify-preview-providers.yml:1-236` | Ambientes separados, manifest ligado a SHA, restore/rollback probado | No hay evidencia de proveedor cloud ejecutada para este SHA |

## 3. Matriz completa de TECH-XXXX

| TECH | Estado | Prioridad | Evidencia verificable en `HEAD` | Gap que impide un estado superior / siguiente acción |
|---|---|---:|---|---|
| 0000 | **VERIFIED** | P0 | Este informe; inventario, duplicados, mapa, threat model y rollout contra `6fd71f0`. | Mantenerlo como referencia; actualizarlo si cambia una autoridad canónica. |
| 0010 | **VERIFY** | P0 | `AuthContext` exige membership activa (`app/dependencies/auth.py:93-150`); RLS está versionado (`alembic/versions/20260724_tenant_rls_context.py:25-183`); hay pruebas cross-hotel en `tests/test_reservation_search.py`, `tests/test_rate_calendar_api.py` y `tests/test_permissions_api.py`. | No existe prueba exhaustiva de endpoints/jobs/exports/integraciones ni ejecución PostgreSQL actual; `tests/test_master_admin_rls_bypass_pg.py:1-16` documenta que SQLite no sirve y que el test real se omite sin DSN aislado. |
| 0020 | **VERIFY** | P0 | Argon2id por defecto, bcrypt compatible y `needs_rehash` (`app/services/security.py:23-65`); tests de hash, upgrade, longitud y no truncamiento (`tests/test_auth_security.py:223-278`). | Falta benchmark reproducible/versionado, filtro de contraseñas comprometidas y evidencia de ambiente real. |
| 0021 | **VERIFY** | P0 | Modelo hash-only, cookie y CSRF, expiración absoluta/inactividad, rotación y revocación (`app/models/user_session.py:17-38`; `app/services/user_session_service.py:106-286`); tests focales en `tests/test_user_sessions.py:85-291`. | Es migración aditiva: `app/dependencies/auth.py:59-90` aún autentica bearer JWT y `app/api/auth.py:149-193` sigue entregando `access_token`; falta cerrar inventario mobile/API y demostrar sesión robada/revocada en todos los consumidores. |
| 0022 | **VERIFY** | P0 | Tokens persistidos, respuestas anti-enumeración, rate limits y revocación por reset en `app/api/auth.py:296-430,700-752`; tests `tests/test_auth_security.py:278-424,558-590`. | Falta evidencia del proveedor transaccional cloud, política completa de sesiones/dispositivos y QA E2E real. |
| 0023 | **VERIFY** | P0 | TOTP cifrado, replay guard y recovery codes single-use (`app/services/mfa_service.py:41-123,154-212`); login MFA y rate limit en `app/api/auth.py:247-289,445-487`; tests `tests/test_auth_security.py:955-1108` y `tests/test_temporary_action_grants.py:119-237`. | En `HEAD` Master Admin MFA todavía puede ser opt-in (`tests/test_master_admin_panel.py:367`); no hay step-up general ligado a sesión/hotel/propósito para todo el catálogo crítico. |
| 0024 | **TODO** | P1 | Google OIDC por `google_sub`, `email_verified`, unlink con reauth y tests (`app/api/auth.py:490-626`; `tests/test_auth_security.py:639-883`). | No hay Apple en `HEAD`: no existe `apple_auth_service`, migración, botón ni test Apple. El trabajo está en la rama no incorporada `codex/tech0024-apple-signin` (`3e20987`). |
| 0025 | **DEFERRED** | P2 | El spec lo marca diferido; no se evaluó como implementación requerida. | No iniciar sin decisión humana sobre passkeys/Face ID y superficies móviles. |
| 0030 | **VERIFY** | P0 | Membership por hotel, Primary Owner único e invariantes transaccionales (`app/models/hotel_membership.py:12-38`; `app/services/membership_service.py:19-124`); tests `tests/test_invitations.py:500-591`. | Falta demostrar todos los flujos de transferencia, recovery, billing owner y cierre/cancelación con PostgreSQL/concurrencia real; la proyección legacy `owner_email` aún existe. |
| 0031 | **VERIFY** | P1 | Token persistente hasheado, vencimiento, consumo atómico (`app/services/invitation_service.py:35-124`); cuenta existente exige su bearer (`app/api/invitations.py:89-162`); ciclo resend/revoke/audit y baja con revocación están en `tests/test_invitations.py:116-410`. | Límite de staff depende de `TECH-0050`; Google/Apple no cubren Apple en `HEAD`; falta E2E cloud y política de rollback/operación. |
| 0040 | **VERIFY** | P0 | Catálogo, defaults, overrides de rol/usuario, precedencia deny, ceilings, version conflict y restore (`app/services/permission_service.py:387-429,457-750`); tests `tests/test_permissions_api.py:68-340` y `tests/test_permission_overrides_v2.py:84-414`. | Persisten rutas `require_roles` y aliases legacy; no se probó la matriz completa de endpoints ni roles personalizados/versionado ETag como contrato. |
| 0041 | **VERIFY** | P1 | Solicitud/aprobación MFA, token hash single-use, estados y consumo atómico en `app/services/temporary_action_grant_service.py:119-342`; tests `tests/test_temporary_action_grants.py:119-237`. | El propio código/entrega deja fuera la integración con pagos/descuentos y el vínculo a sesión, parámetros y monto; no debe declararse autorización efectiva de negocio. |
| 0050 | **VERIFY** | P1 | Catálogo `starter/pro/ultra`, límites room/staff, entitlements y enforcement (`app/services/subscription_entitlements.py:21-30,231-313`; `app/services/subscription_service.py:118-246`); tests `tests/test_subscription_tiers.py:120-149,297-350`. | No hay snapshot contractual/versionado completo de precio/moneda/impuestos ni observabilidad de usage para todos los límites; convive tabla legacy. |
| 0051 | **VERIFY** | P1 | Estados trial/comped, eventos y ledger idempotente con FK restrict (`app/models/subscription_v2.py:56-124`; `app/services/subscription_entitlements.py:174-228,343-412`); tests `tests/test_subscription_tiers.py:151-269`. | No hay billing provider completo ni step-up específico antes del comped override; el panel usa auditoría master pero falta validar separación/forense end-to-end. |
| 0060 | **VERIFY** | P1 | Search tenant-scoped, escape de LIKE, ranking, límite y offset (`app/services/guest_service.py:158-205`; `app/api/guests.py:121-150`); hay cobertura de búsqueda y aislamiento en `tests/test_reservation_search.py`. | No hay benchmark p95/query plan versionado ni cursor pagination; la auditoría no midió comportamiento de una tabla grande. |
| 0061 | **VERIFY** | P1 | Servicio de quote con token de pricing revision (`app/services/reservation_quote_service.py:16-129`); calendario de rates/restrictions e invalidación contractual en `tests/test_reservation_quote_contract.py:27-94` y `tests/test_rate_calendar_service.py:141-389`. | Falta prueba completa de todos los canales, caché/invalidation y disponibilidad bajo concurrencia; no hay métrica p95. |
| 0062 | **VERIFY** | P1 | Engine, runtime persistido, policy versions, feedback y explicaciones (`app/services/allocation_engine.py:127-385`; `app/services/allocation_runtime_service.py:55-326`); tests `tests/test_allocation_v72_rules.py`, `tests/test_allocation_policy_service.py` y `tests/test_allocation_policy_api.py`. | No se cerró evidencia de worker Celery/Redis, retries/concurrencia/idempotencia a escala ni ejecución asíncrona no bloqueante en ambiente real. |
| 0063 | **VERIFY** | P1 | Índices OLTP y correcciones de carga están en modelos/migración `alembic/versions/20260820_tech0063_oltp_hot_path_indexes.py`; test `tests/test_tech0063_performance.py:1-18` comprueba índices. | Ese test no es `EXPLAIN ANALYZE BUFFERS`, p95/p99, locks ni crecimiento; no hay benchmark real reproducible contra PostgreSQL. |
| 0070 | **VERIFY** | P0 | `AuditLog` tenant-scoped y `ondelete=RESTRICT` (`app/models/audit_log.py:34-77`), safe writer (`app/services/audit_log_service.py:84-153`), timeline/CSV (`app/services/audit_timeline_service.py`, `app/api/settings_security.py:180-208`), tests `tests/test_audit_coverage.py` y `tests/test_audit_hooks.py`. | Cobertura no prueba todos los dominios exigidos ni inmutabilidad DB contra actor privilegiado; seguridad y master usan otros modelos. |
| 0071 | **VERIFY** | P1 | Plano master separado, cookie/CSRF/lockout/session y panel (`app/master_admin/security.py:1-120`; `app/master_admin/router.py:63-351`); MFA y TTL tienen tests en `tests/test_master_admin_panel.py:180-205,367-480`. | MFA aún opt-in en `HEAD`; no se observan métricas MRR/ARR, jobs/errors y soporte excepcional completo; falta validación real PostgreSQL/provider. |
| 0080 | **BLOCKED** | P2 | Facts PostgreSQL y frontera ClickHouse PII-free/reconciliable (`app/services/analytics_facts.py:134-364`; `app/services/analytics_warehouse.py:1-99,213-300`); tests `tests/test_analytics_facts.py` y `tests/test_analytics_warehouse.py:42-240`. | Bloqueado por la decisión abierta de sección 7 sobre BigQuery frente a facts actuales/ClickHouse/otra opción. Esta auditoría no decide esa cuestión. Tampoco hay CDC/ELT provider-bound ejecutado. |
| 0081 | **VERIFY** | P2 | Marts operativos de hotel sobre facts, tenant-scoped, freshness y métricas/segmentos/canales (`app/services/analytics_service.py:66-83,896-1007,1209-1297`); tests `tests/test_analytics_api.py`, `tests/test_analytics_facts.py` y `tests/test_analytics_freshness.py`. | No es todavía un mart warehouse elegido/operado; queda condicionado a `TECH-0080` y no se resuelve BigQuery vs ClickHouse. |
| 0082 | **BLOCKED** | P2 | El panel master cuenta hoteles y estados (`app/master_admin/router.py:272-301`), pero no existe un SaaS Owner Data Mart ni facts de MRR/ARR/churn/API/storage/jobs. | Bloqueado por la fundación/decisión de warehouse `TECH-0080` y por el alcance master SaaS aún incompleto. |
| 0090 | **VERIFY** | P2 | Manifest, service worker que nunca cachea `/api`, registro en producción y banner offline (`frontend/public/manifest.webmanifest:1-14`; `frontend/public/sw.js:1-97`; `frontend/src/main.tsx:27-32`; `frontend/src/ui/AppShell.tsx:300-312`). | Falta evidencia manual desktop/mobile/tablet, installability real y prueba de que cada pantalla crítica degrada correctamente; el endurecimiento de maskable icons/offline está en rama no incorporada `codex/tech0090-pwa-audit` (`661e71d`). |
| 0091 | **DEFERRED** | P3 | El spec lo marca diferido; existen shells Capacitor pero no se cierra publicación ni dispositivos reales. | Esperar `TECH-0090`, OIDC Apple/passkeys y responsabilidad humana sobre cuentas/stores. |
| 0092 | **DEFERRED** | P3 | El spec lo marca diferido. | No evaluar Tauri sin requisito operativo concreto. |
| 0100 | **DEFERRED** | P3 | El spec lo marca diferido; `gemma_chat` existe pero no constituye el contrato de tools requerido. | No habilitar IA read-only como autoridad hasta cerrar RBAC, entitlements, audit y marts. |
| 0101 | **DEFERRED** | P3 | El spec lo marca diferido; hay grants temporales pero no escritura IA confirmada completa. | Mantener fuera de transacciones hasta `TECH-0100` y evaluación humana. |
| 0110 | **TODO** | P1 | Solo existe runbook de incident/recovery (`knowledge/30-operations/incident-and-recovery.md`); no hay backup/restore/PITR implementado en `HEAD`. | Falta configurar backups, retención, RPO/RTO, restore drill real y alertas. La rama `codex/tech0110-backups-continuity` (`900a571`) no es evidencia del checkout auditado. |
| 0111 | **VERIFY** | P0 | Validación fail-closed de secretos, CORS, HTTPS, efectos externos y rate limits (`app/config.py:241-520`); headers y rate-limit tests; Render declara `JWT_SECRET` generado (`render.yaml:38-59`). | No hay prueba de DB/Redis privados, WAF/DDoS, KMS/IAM mínimo ni rotación cloud para este SHA; proveedor real no verificado. |
| 0112 | **VERIFY** | P0 | PR validation, preview sin secretos y trusted release/provider-manifest workflows (`.github/workflows/pr-validation.yml:1-55`; `.github/workflows/preview-qa.yml:1-40`; `.github/workflows/trusted-release-gate.yml:1-80`). | El ciclo cloud no fue ejecutado; hay acciones no SHA-pinned en workflows actuales y el endurecimiento adicional está fuera de `HEAD` en `codex/tech0112-cicd-pipeline` (`474ec06`). |
| 0120 | **DEFERRED** | P2 | El spec lo marca diferido y prohíbe cutover sin autorización. | No iniciar migración Render/Supabase→GCP antes de P0/P1, staging, restore y aprobación humana. |
| 0130 | **DEFERRED** | P0 antes de hoteles reales | El spec lo marca diferido. Los tests internos y gates no son un pentest independiente. | Contratar pentest externo después de cerrar P0 y exigir cero críticos/altos revalidados. |

No se clasificó ningún bloque como `REJECTED`.

## 4. Duplicaciones y fragmentación reales

### 4.1 Auth activo en dos planos

No es solo documentación: el backend acepta bearer JWT en `app/dependencies/auth.py:59-90`, mientras login también crea `UserSession` y cookies en `app/api/auth.py:177-193`. El response conserva `access_token` y la sesión cookie es aditiva. Esto crea dos mecanismos válidos para la misma autenticación normal, con revocación distinta: `token_version` para JWT frente a fila revocable/rotada para la cookie. Es una transición explícita de TECH-0021, pero sigue siendo duplicación operativa y debe consolidarse antes de cerrar P0.

### 4.2 Dos autoridades de autorización en rutas

`require_permission`/`resolve` consulta la matriz granular (`app/dependencies/auth.py:153-273`; `app/services/permission_service.py:387-429`), pero muchas rutas siguen usando `require_roles` (`app/dependencies/auth.py:294-308`, por ejemplo `app/api/bookings.py`, `app/api/onboarding.py`, `app/api/users.py` y `app/api/subscription.py`). Los aliases legacy del catálogo (`app/services/permission_service.py:90-117`) agregan una tercera capa de compatibilidad. Es una duplicación real de decisión de acceso, no se arregla en TECH-0000.

### 4.3 Suscripciones legacy y v2

`SubscriptionPlan`/`HotelSubscription`/`SubscriptionEntitlement` viven en `app/models/subscription.py:11-80`, mientras `Subscription`/`SubscriptionEvent`/`SubscriptionAdjustment` viven en `app/models/subscription_v2.py:29-124`. El servicio nuevo mantiene explícitamente tablas legacy sincronizadas (`app/services/subscription_entitlements.py:76-98,231-251`) y `subscription_service.py` lee ambas (`app/services/subscription_service.py:249-270`). Hay dos almacenamientos y más de un camino para el mismo contrato de plan/límite; la sincronización reduce la ruptura pero no define una única autoridad.

### 4.4 Fragmentación de auditoría, no duplicado puro

`AuditLog`, `SecurityAuditLog` y `MasterAdminAuditEvent` tienen propósitos distintos y por eso no los marco como tres duplicados idénticos. Sí son tres persistencias que cubren eventos parcialmente superpuestos y luego se proyectan a timelines distintos. La separación de trust boundary es razonable, pero requiere un contrato canónico de cobertura, retención, inmutabilidad y reconciliación antes de llamar `VERIFIED` a TECH-0070/0071.

### 4.5 Analytics: derivación intencional, no duplicado accidental

Las facts PostgreSQL son fuente operativa y ClickHouse es una proyección PII-free (`app/services/analytics_warehouse.py:1-5,213-300`). Lo clasifico como duplicación de representación deliberada, no como dos servicios que compiten por autorizar o mutar negocio. La decisión de warehouse sigue abierta y no se resuelve aquí.

## 5. Threat model P0

| Superficie | Ataque considerado | Mitigación con evidencia | Residual / estado |
|---|---|---|---|
| Auth/credenciales | password stuffing, hashes heredados, enumeración y reset abusivo | Argon2id + bcrypt upgrade (`security.py:23-65`), rate limits y anti-enumeración (`auth.py:296-430`), tests `test_auth_security.py:223-424` | Falta filtro de contraseñas comprometidas, benchmark y QA real. `VERIFY`. |
| Sesiones | robo/replay de cookie, CSRF, sesión revocada, logout global | token hash-only, CSRF double-submit, rotación y expiración (`user_session_service.py:106-229`), tests `test_user_sessions.py:85-291` | JWT bearer largo sigue habilitado y no todos los consumidores están migrados. `VERIFY`. |
| OAuth/invitaciones | account takeover por email coincidente o replay de invitación | Google usa `sub` y email verificado (`auth.py:534-577`); invitación existente exige bearer del mismo usuario (`invitations.py:89-118`), consumo atómico (`invitation_service.py:105-124`), tests `test_invitations.py:176-250` | Apple no está en `HEAD`; provider cloud y E2E pendientes. `TODO` para TECH-0024 / `VERIFY` para 0031. |
| RBAC | privilege escalation, override cross-hotel, role spoofing | membership server-side (`dependencies/auth.py:124-150`), precedencia/ceiling/deny (`permission_service.py:387-429`), tests `test_permissions_api.py:219-240` | Rutas role-only y permission-only conviven; falta inventario exhaustivo y una autoridad única. `VERIFY`. |
| Multi-tenancy/IDOR | manipular `hotel_id`, IDs de reserva/guest/payment, acceso por jobs/exports | `AuthContext` comprueba membership; filtros tenant y RLS declarativo (`dependencies/auth.py:93-150`; migration `20260724_tenant_rls_context.py:149-183`); pruebas parciales | RLS real se omite sin PostgreSQL aislado; cobertura no prueba cada endpoint/job/export/integración. `VERIFY`, riesgo P0 abierto. |
| Pagos/caja | cross-tenant payment lookup, doble cobro, replay webhook, secretos de gateway | idempotencia y comprobación de hotel en `payment_service.py:81-109,233-258,520-561`; firmas/efectos externos y rate limits en configuración/workflows; tests de pagos y webhooks | La búsqueda inicial de reserva ocurre por ID antes de resolver tenant (`payment_service.py:233-240`); proveedores reales/PCI/WAF no están verificados. `VERIFY`. |
| Auditoría | borrar o alterar evidencia, pérdida al borrar tenant/usuario, PII en logs | `AuditLog` restringe borrado del hotel (`audit_log.py:41-46`), safe writer y redacción tests `test_audit_coverage.py`, `test_settings_security_api.py` | Otros logs security/master tienen contratos distintos; no hay prueba de inmutabilidad contra DB owner ni retención/restore. `VERIFY`. |

## 6. Mapa vigente versus objetivo y decisiones abiertas

El objetivo de sección 3 del spec exige separar identidad, sesión, membership, permiso, entitlement, step-up y auditoría. El checkout ya contiene piezas para cada capa, pero todavía tiene dos decisiones de acceso activas (JWT/cookie y role/permission), dos modelos de suscripción y tres persistencias de auditoría. El objetivo de sección 4 (GCP/Cloud SQL/Redis/warehouse) es orientativo y no autoriza migración: el runtime vigente continúa siendo Vercel + Render + Supabase.

Quedan explícitamente fuera de esta auditoría las decisiones de sección 7: esquema de sesiones mobile/API, modelo canónico RBAC/subscriptions, roles/overrides, calendario MFA, RLS y Primary Owner/recovery/retención, BigQuery frente a ClickHouse/facts, región/HA/RPO/RTO/presupuesto, y proveedor/ventana del pentest. En particular, este informe no recomienda BigQuery ni ClickHouse.

## 7. Plan de rollout y prioridad

### P0 — Confianza y bloqueo de riesgo

1. **TECH-0010:** ejecutar el catálogo exhaustivo cross-tenant contra PostgreSQL aislado; cerrar RLS, jobs, exports, analytics, invitaciones, archivos e integraciones. No aceptar SQLite como prueba de RLS.
2. **TECH-0021/0022/0023/0024:** definir el consumidor canónico de sesión; terminar recovery, MFA obligatorio de Master Admin, step-up por propósito y Apple OIDC antes de retirar rutas legacy.
3. **TECH-0030/0031/0040/0041:** consolidar membership/Primary Owner, llevar todas las rutas sensibles a permisos canónicos y conectar grants a acciones de negocio con parámetros revalidados.
4. **TECH-0070/0071:** fijar cobertura, retención, inmutabilidad y reconciliación de los tres planos de auditoría; completar control plane y soporte excepcional.
5. **TECH-0111/0112:** verificar secretos, aislamiento de proveedores, workflow trusted y evidencia ligada al SHA; recién después habilitar el gate P0.
6. **TECH-0130:** pentest externo como gate antes de aceptar hoteles reales; nunca sustituirlo por pytest o escáner interno.

### P1 — Operación segura y escala inmediata

1. Resolver la autoridad única de suscripciones (`TECH-0050/0051`) antes de ampliar límites de staff, descuentos o billing.
2. Medir `TECH-0060/0061/0062/0063` con PostgreSQL real: p95/p99, `EXPLAIN ANALYZE BUFFERS`, locks, concurrencia, idempotencia y jobs.
3. Implementar `TECH-0110` con restore drill real, RPO/RTO y alertas; un backup no cuenta como verificado sin restauración.

### P2 — Analytics y experiencia operacional

1. Product Lead debe resolver la decisión de `TECH-0080`; hasta entonces no elegir warehouse ni iniciar un cutover.
2. Sobre esa decisión, completar `TECH-0081` y `TECH-0082` con lineage, freshness, reconciliación, mínimos de PII y marts separados por tenant/plano SaaS.
3. Completar QA manual de `TECH-0090` en desktop/mobile/tablet; mantener offline sin cola de escrituras ni datos operativos falsamente actuales.

### P3 — Diferido

Mantener `TECH-0091`, `TECH-0092`, `TECH-0100` y `TECH-0101` diferidos hasta que P0/P1 y los contratos de datos/RBAC/auditoría estén cerrados. `TECH-0120` permanece diferido hasta backups, seguridad cloud, CI/CD, staging y autorización humana de cutover.

## 8. Limitaciones y conclusión

- No se ejecutaron tests en esta sesión por falta del runtime `.venv` y de `pytest` del sistema; el informe identifica tests versionados y no los presenta como pasados ahora.
- No se consultaron proveedores cloud ni se hicieron efectos externos. No hay evidencia de release QA cloud para `6fd71f0` en este checkout.
- No se modificó código de aplicación: `app/`, `frontend/src/`, modelos, servicios, migraciones y workflows solo fueron leídos.
- La auditoría sí modifica documentación: este informe y el status/evidencia de TECH en el spec maestro.

