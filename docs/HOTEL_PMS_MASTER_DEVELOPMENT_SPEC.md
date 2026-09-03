---
title: "Hotel-Chipre-PMS — Especificación Maestra Única de Desarrollo"
status: "living-document"
document_type: "canonical-technical-executable-backlog"
last_updated: "2026-09-02"
project: "Hotel-Chipre-PMS"
tags: [hotel-pms, master-spec, orchestrator, backlog, security, saas]
---

# Hotel-Chipre-PMS — Especificación Maestra Única de Desarrollo

> **Éste es el único archivo que debe entregarse al agente encargado de auditar, planificar y desarrollar las funcionalidades futuras del proyecto.**

Reemplaza como punto de entrada operativo a:

- `docs/Hotel_PMS_Technical_Orchestrator_Backlog.md`;
- `docs/auth-rbac-saas-data-architecture.md`.

Esos documentos se conservan como fuentes históricas. Ante una diferencia, este archivo expresa el objetivo consolidado más reciente. El código, tests, migraciones, configuración y runtime siguen siendo la evidencia del estado real.

## 1. Objetivo del producto

Hotel-Chipre-PMS es un SaaS multi-tenant para centralizar y operar:

- hoteles, usuarios, empleados y permisos;
- reservas, disponibilidad, habitaciones, tarifas y huéspedes;
- check-in/check-out, caja, pagos y reportes;
- stock, limpieza, ropa blanca y lavandería;
- integraciones, canales y automatizaciones;
- analytics del hotel y métricas del negocio SaaS;
- suscripciones, planes, límites y bonificaciones;
- optimización de asignación de habitaciones;
- posteriormente, un asistente de IA que consulte y opere mediante herramientas controladas.

Debe soportar desde los primeros hoteles hasta miles de tenants sin sacrificar aislamiento, seguridad, trazabilidad, rendimiento ni facilidad de evolución.

## 2. Contrato obligatorio del agente orquestador

Cuando reciba este archivo, el agente debe:

1. leer `AGENTS.md`, memoria/router del proyecto y Graphify según las reglas del repo;
2. resolver checkout, rama, SHA y ambiente antes de afirmar estados;
3. inventariar modelos, APIs, servicios, UI, migraciones, jobs, tests e infraestructura existentes;
4. clasificar cada `TECH-XXXX` como `VERIFIED`, `VERIFY`, `TODO`, `BLOCKED`, `DEFERRED` o `REJECTED`;
5. no crear un sistema paralelo cuando ya existe una base adaptable;
6. proponer un plan por cambios pequeños, backward-compatible y verificables;
7. respetar dependencias y prioridad P0 > P1 > P2 > P3;
8. implementar en loops acotados, con tests y evidencia;
9. actualizar este mismo archivo después de cada auditoría o entrega;
10. no desplegar, migrar producción, cambiar billing, crear cuentas cloud, rotar secretos ni hacer cutovers sin autorización humana explícita.

### 2.1 Estados permitidos

| Estado | Significado |
|---|---|
| `AUDIT_REQUIRED` | Requisito definido, estado real aún no comprobado. |
| `TODO` | Falta confirmado y listo para implementar. |
| `IN_PROGRESS` | Existe trabajo activo sobre el bloque. |
| `BLOCKED` | Una dependencia concreta impide avanzar. |
| `VERIFY` | Parece implementado, pero falta evidencia suficiente. |
| `VERIFIED` | Cumple criterios con evidencia reproducible. |
| `DEFERRED` | Se posterga deliberadamente. |
| `REJECTED` | Requisito eliminado o reemplazado, con motivo. |

Nunca marcar `VERIFIED` por la mera existencia de una clase, ruta, pantalla o test aislado.

### 2.2 Formato de evidencia

Cada bloque cerrado debe registrar:

- estado y fecha;
- commit/SHA y archivos modificados;
- migraciones aplicadas;
- tests ejecutados y resultado;
- evidencia E2E/manual cuando corresponda;
- métricas antes/después para performance;
- riesgos, deuda y rollback/forward-fix;
- ambiente exacto validado.

### 2.3 Definition of Done general

- [ ] comportamiento y criterios de aceptación completos;
- [ ] aislamiento multi-hotel preservado;
- [ ] autorización server-side y entitlements aplicados;
- [ ] tests unitarios, integración, negativos y E2E proporcionales al riesgo;
- [ ] migraciones seguras y datos existentes preservados;
- [ ] concurrencia, idempotencia y errores considerados;
- [ ] logs sin secretos, tokens, OTPs ni PII innecesaria;
- [ ] UI desktop/mobile/tablet con loading, empty y error states;
- [ ] observabilidad y auditoría incorporadas;
- [ ] documentación y este backlog actualizados;
- [ ] evidencia de release asociada al SHA correcto.

## 3. Principios de arquitectura no negociables

### 3.1 Separación de controles

```text
Identidad     ¿Quién es la persona?
Sesión        ¿Qué sesión/dispositivo la autenticó?
Membership    ¿En qué hotel trabaja y en qué estado?
Permiso       ¿Qué puede hacer en ese hotel?
Entitlement   ¿Qué contrató ese hotel?
Step-up       ¿Debe volver a autenticarse para esta acción?
Auditoría     ¿Quién intentó o ejecutó qué y con qué resultado?
```

Una acción sensible sólo se ejecuta si todas las puertas necesarias son positivas. La UI no es una barrera de seguridad.

### 3.2 Multi-tenancy

- Hotel A jamás accede a recursos de Hotel B.
- Toda entidad operacional debe tener alcance de hotel inequívoco.
- El backend resuelve y verifica identidad, membership, hotel y recurso.
- Nunca confiar en `hotel_id`, rol o permisos declarados por el navegador.
- Incorporar constraints, índices, FKs y tests cross-tenant.
- Evaluar RLS como defensa adicional compatible con el pool/transacciones, no como sustituto del servicio.

### 3.3 Datos

- PostgreSQL es la fuente de verdad operacional.
- Redis sirve para caché, locks, rate limiting, sesiones/jobs cuando se justifique.
- Data Warehouse/Data Marts sirven analytics y no autorizan transacciones.
- No activar MongoDB, Cassandra, Neo4j, ClickHouse u otra base por moda o anticipación.
- Antes de otra DB: optimizar query, índices, búsqueda PostgreSQL, Redis, materialized views y read models.

### 3.4 Propiedad tecnológica

Serán propios: usuarios, cuentas internas, memberships, sesiones, RBAC, entitlements, audit logs y contratos de negocio. Se usarán estándares/librerías maduras para criptografía, Argon2id, OAuth/OIDC, TOTP y WebAuthn. Email, TLS, WAF/DDoS, PostgreSQL administrado y auditoría externa pueden ser servicios reemplazables.

### 3.5 Adaptar antes de reescribir

El repo ya contiene bases de Auth, permisos configurables, invitaciones, auditoría, suscripciones, Master Admin, Analytics, Celery, Redis, OR-Tools, PWA/Capacitor y despliegues. Cada bloque exige auditoría previa y consolidación de implementaciones duplicadas.

## 4. Arquitectura objetivo orientativa

La selección final debe basarse en evidencia y costo real. La dirección preferida discutida es:

```text
React/Vite + PWA + Capacitor
             ↓
         Vercel
             ↓
       FastAPI / Cloud Run
        ├── Cloud SQL PostgreSQL HA
        ├── Redis/Memorystore
        ├── Cloud Tasks/Pub/Sub + workers OR-Tools
        ├── Cloud Storage
        └── CDC/ELT → BigQuery → Data Marts

Protección: Cloud Armor, IAM, KMS, Secret Manager
Operación: Logging, Monitoring, Sentry, backups/PITR, Terraform
```

Esto no autoriza una migración. El stack actual Vercel + Render + Supabase + Resend debe mantenerse hasta que staging y la nueva infraestructura demuestren paridad y exista aprobación de cutover.

## 5. Orden global

```text
P0  Confianza: tenant isolation, Auth, sesiones, recovery, RBAC, MFA, audit
P1  Operación: invitaciones, permisos temporales, planes, performance, backups
P2  Analytics, Master SaaS completo, PWA/mobile e infraestructura objetivo
P3  IA avanzada, apps/store y tecnologías adicionales no esenciales
```

## 5.1 Baseline TECH-0140 — Task 0

**Estado:** `VERIFIED` para la trazabilidad local de este checkout; la
configuración privada de proveedores y la QA cloud siguen `needs-verification`.

Baseline documentada el 2026-09-02 desde la rama
`feature/tech-0140-realtime-recovery-contract`, commit completo
`0fc3f497841b8da166631d5ca5d476943ed1dbd5`. El árbol estaba limpio antes de
la actualización documental. La cabeza Alembic observada es
`20260902_ota_lifecycle_enum_lowercase (head)`.

Task 2 ya implementada en ese commit expone
`GET /api/events/recovery?after_cursor=N`: responde sólo
`latest_cursor`, `domains`, `reset_required` y `has_more`; está limitada al
hotel de la membresía autenticada y barre como máximo 500 filas. El cursor
actual es el `id` entero de `domain_event_outbox`; el reemplazo por
`stream_cursor` queda para T4.

La fuente de verdad operacional continúa siendo PostgreSQL. Redis/Valkey sólo
transporta invalidaciones, locks y estado efímero; una caída del transporte no
deshace una escritura confirmada. No se provisionaron proveedores, se
ejecutaron migraciones remotas ni se importaron los seis cambios `.graphify`
del checkout original.

Evidencia reproducible y configuración no sensible: [inventarios generados](../knowledge/_generated/README.md), [architecture-hybrid](data-foundations/architecture-hybrid.md) y [runbook de despliegue](DEPLOY_GUIDE.md). Las URLs, credenciales y valores privados de proveedor no quedan confirmados por esta baseline.

## 6. Backlog maestro ejecutable

### TECH-0000 — Auditoría y matriz de estado actual

Status: `VERIFIED`
Priority: `P0`

**Goal:** producir la autoridad canónica antes de cambiar código.

**Required:**

- inventario de Auth, RBAC, invitaciones, audit, subscriptions, analytics y master;
- detectar modelos/servicios/versiones duplicados;
- mapa vigente vs objetivo;
- threat model y decisiones abiertas;
- matriz `VERIFIED/VERIFY/TODO/BLOCKED` para todos los bloques;
- plan de migraciones y rollout sin reescritura innecesaria.

**Acceptance:** informe enlazado, evidencia por área y cero afirmaciones basadas sólo en documentación histórica.

**Auditoría cerrada 2026-08-21:** `VERIFIED` contra `6fd71f08de84b5c891b9ea9e47d8f802831f964f` (`origin/main`). Se auditaron Auth, sesiones, RBAC, memberships, invitaciones, auditoría hotel/security/master, suscripciones/entitlements, analytics/facts/warehouse, Master Admin, PWA, backups, seguridad cloud, CI/CD, migraciones y tests versionados. El informe canónico con evidencia, duplicaciones, threat model y rollout está en [docs/audits/tech-0000-system-audit.md](audits/tech-0000-system-audit.md). No se modificó código de aplicación.

---

### TECH-0010 — Aislamiento multi-hotel exhaustivo

Status: `VERIFY`
Priority: `P0`  
Depends on: `TECH-0000`

**Goal:** impedir acceso cruzado incluso manipulando IDs, rutas o requests.

**Acceptance:**

- [ ] todos los endpoints sensibles resuelven hotel/membership server-side;
- [ ] recursos hijos validan pertenencia real al tenant;
- [ ] tests Hotel A contra recursos de Hotel B en lectura/escritura/exportación;
- [ ] jobs, audit, analytics, invitaciones, archivos e integraciones scoped;
- [ ] política fail-closed y 403/404 coherente;
- [ ] estrategia RLS decidida y documentada.

**Auditoría de cierre local 2026-08-21:** se inventariaron 418 registros de ruta en `app/api/` (375 handlers únicos). La resolución normal deriva `hotel_id` de la membership activa en `app/dependencies/auth.py:105-150`; los recursos hijos se filtran server-side por `(id, hotel_id)`. Se encontró y corrigió un gap en los dos endpoints financieros (`app/services/payment_service.py` y `app/api/payments.py`): antes cargaban una reserva por ID global y devolvían 400 con información del tenant ajeno; ahora el lookup es tenant-scoped y responde 404 genérico. La regresión está en `tests/test_cross_hotel_id_collision_api.py` e incluye reservas, huéspedes, habitaciones, caja/pagos, invitaciones, permisos/RBAC y audit log, incluyendo path y query-param.

**Evidencia 2.2:** estado `VERIFY`, fecha 2026-08-21; SHA de commit pendiente porque Git no pudo escribir el lock de índice fuera del workspace writable; archivos/fix y matriz en `app/services/payment_service.py`, `app/api/payments.py`, `tests/test_cross_hotel_id_collision_api.py` y `docs/audits/tech-0010-tenant-isolation-audit.md`; migraciones: ninguna; validación: sintaxis Python 3.12 de archivos modificados; `.venv/bin/python -m pytest -q` bloqueado por `No module named pytest` después de fallar la instalación desde PyPI por DNS/red; ambiente: worktree local `codex/tech0010-isolation-audit-closure`, base `origin/main`/`6fd71f0`; E2E cloud/RLS real no ejecutados ni modificados. Faltan pruebas negativas dedicadas para las familias marcadas `VERIFY` en la matriz, por lo que TECH-0010 no se declara `VERIFIED`.

---

### TECH-0020 — Contraseñas Argon2id y política segura

Status: `VERIFY`
Priority: `P0`  
Depends on: `TECH-0000`

**Required:** rehash bcrypt→Argon2id durante login exitoso; nuevos hashes Argon2id; parámetros benchmarkeados/versionados; `needs_rehash`; frases largas y filtro de comprometidas; sin reglas arbitrarias ni rotación periódica sin compromiso.

**Acceptance:** hash nuevo, login bcrypt+upgrade, incorrect password, concurrencia y no truncamiento cubiertos por tests.

---

### TECH-0021 — Sesiones revocables y dispositivos

Status: `VERIFY`
Priority: `P0`  
Depends on: `TECH-0020`

**Goal:** reemplazar progresivamente JWT largo/localStorage por sesiones controlables sin romper clientes.

**Required:** cookie web HttpOnly/Secure/SameSite; session ID opaco con hash en DB; CSRF; expiración absoluta/inactividad; rotación; revocación individual/global; dispositivos conectados; sesiones móviles/API compatibles; inventario previo de consumidores.

**Acceptance:** logout real, cerrar todos, reset revoca según política, sesión robada/revocada falla y ningún token aparece en logs.

---

### TECH-0022 — Registro, verificación y recuperación

Status: `VERIFY`
Priority: `P0`  
Depends on: `TECH-0021`

**Required:** email verification; password reset single-use/expirable/hasheado; respuestas anti-enumeración; rate limits por señales; revocación de sesiones; email transaccional seguro; login/security events minimizados.

---

### TECH-0023 — MFA TOTP, recovery codes y step-up

Status: `VERIFY`
Priority: `P0`  
Depends on: `TECH-0021`

**Required:** alta TOTP con reauth y confirmación; secreto cifrado; replay protection; recovery codes hasheados single-use; desactivación segura; step-up corto ligado a usuario/sesión/hotel/propósito; MFA obligatorio para Master Admin y política gradual para Owners/permisos críticos.

**Cierre del gap MFA obligatorio Master Admin (2026-08-21):** el gap de obligatoriedad quedó cerrado en el código de trabajo. El login Master Admin con password+PIN sin TOTP sólo emite un estado `requires_mfa_setup` de setup-only; `auth/me` y toda operación del panel quedan bloqueadas server-side hasta confirmar TOTP. Con TOTP activo, el login entrega un challenge corto y no crea sesión hasta validar el segundo factor. La sesión queda bloqueada para operar inmediatamente después de desactivar MFA. Owners/hoteles/staff normales no fueron modificados.

**Evidencia:** `code_sha` base `7775b7b665948d72bf9adebe00de61255d528571` (cambios aún sin commit por bloqueo de escritura en el metadata Git compartido del worktree); archivos `app/master_admin/router.py`, `app/master_admin/security.py`, `app/master_admin/schemas.py`, `frontend/src/master_admin/{api.ts,layout.tsx,pages/LoginPage.tsx,session.tsx}` y `tests/test_master_admin_panel.py`; Graphify actualizado, `portable-check` OK y `py_compile` de los módulos tocados OK. El comando requerido `.venv/bin/python -m pytest -q` no pudo iniciar porque el venv no tiene `pytest`; la instalación desde `requirements.txt` quedó bloqueada por DNS sin acceso a PyPI. Por eso el estado permanece `VERIFY` y no `VERIFIED` hasta repetir la suite completa en un entorno con dependencias.

---

### TECH-0024 — Google OIDC y Sign in with Apple

Status: `VERIFY`
Priority: `P1`  
Depends on: `TECH-0021`, `TECH-0022`

**Goal:** agregar proveedores sin delegar la cuenta de negocio.

**Required:** identidad interna estable; provider `sub`; linking/unlinking con reauth; evitar account takeover por email coincidente; email relay/nombre de Apple; redirects por ambiente; invitaciones compatibles.

**Entrega y validación 2026-08-21 (PR #77, mergeado a main):** agregado el flujo Apple OIDC sobre el patrón existente de Google: `app/services/apple_auth_service.py` valida firma RS256 mediante JWKS de Apple, issuer, audience, expiración, `sub`, email verificado y nonce; `app/api/auth.py` agrega `POST /api/auth/apple`, `GET /api/auth/apple/start`, `POST /api/auth/apple/callback` y `POST /api/auth/apple/unlink`; `app/models/user.py` extiende la identidad interna con `apple_sub` y guarda el nombre inicial en `display_name`; la migración es `alembic/versions/20260821_apple_sign_in.py` (chain corregido sobre el head real, doble-head detectado y arreglado). La recuperación por email coincide con Google: sólo vincula el `sub` estable, invalida la contraseña previa y sube `token_version`; un `sub` distinto no puede reclamar el email. `frontend/src/components/AppleSignInButton.tsx`, `frontend/src/api/auth.ts` y `frontend/src/views/public/LoginPage.tsx` agregan el botón Apple JS SDK con nonce y captura del nombre de primera autorización. Configuración agregada en `app/config.py`, `.env.example` y `render.yaml`, siempre sin valores reales y con `sync:false` para secretos de Render. No se agregó dependencia: se reutilizan `PyJWT`, `cryptography` y `httpx` existentes.

Durante la verificación se encontraron y corrigieron 2 bugs reales del primer borrador: `_apple_full_name` se llamaba con el payload completo del request en vez de `payload.user` (`AttributeError` en creación y en reclamo de cuenta existente), y la migración encadenaba sobre un revision desactualizado (doble head de Alembic). También se detectó que `qa/preview-manifest.example.json` y `qa_bootstrap_contract.py` necesitaban `APPLE_LOGIN_ENABLED` junto a `GOOGLE_LOGIN_ENABLED` — su ausencia rompía 13 tests no relacionados (contratos de preview-manifest/release-evidence/trusted-release-gate).

**Evidencia:** `.venv/bin/python -m pytest -q` completo → 1665 passed, 0 failed (incluye 5 tests Apple-específicos: validación negativa de token, creación de cuenta, reclamo, rechazo de subject distinto, unlink). `npm run lint` limpio. `npm run typecheck` tiene 1 falla preexistente en `usePushSubscription.ts` no relacionada a este cambio (ya resuelta en el merge de TECH-0090). Alembic single head confirmado. Graphify regenerado, `portable-check` OK. Permanece `VERIFY` (no `VERIFIED`) porque falta E2E real contra credenciales de Apple Developer.

**Pendiente humano:** crear/configurar la app de Apple Developer, Service ID/redirect URI y credenciales reales (`APPLE_CLIENT_ID`, `APPLE_TEAM_ID`, `APPLE_KEY_ID` y el `.p8` montado en `APPLE_PRIVATE_KEY_PATH`), cargar sus valores sólo como secretos del entorno autorizado, y ejecutar la prueba real de autorización. No se desplegó, no se crearon cuentas cloud y no se rotaron secretos.

---

### TECH-0025 — Passkeys/WebAuthn y Face ID ready

Status: `DEFERRED`  
Priority: `P2`  
Depends on: `TECH-0021`, `TECH-0023`

**Required:** challenge single-use; credential ID/public key/counters; múltiples credenciales; RP ID/origins; revocación y recovery; login/step-up. Para iOS: Associated Domains, `apple-app-site-association`, Keychain/AuthenticationServices, capabilities y pruebas reales. El backend nunca recibe biometría.

---

### TECH-0030 — Memberships multi-hotel y Primary Owner

Status: `VERIFY`
Priority: `P0`  
Depends on: `TECH-0010`

**Required:** identidad global con memberships por hotel; rol nunca global en `users`; estados/alta/baja; Primary Owner separado del rol Owner; transferencia, billing owner, cancelación y cierre reservables; recovery sin puerta trasera; invariantes para no dejar hotel sin propietario.

---

### TECH-0031 — Invitaciones y ciclo de vida del staff

Status: `VERIFY`
Priority: `P1`  
Depends on: `TECH-0030`, `TECH-0040`, `TECH-0060`

**Required:** token hasheado single-use con vencimiento; hotel/rol/invitador; aceptar con cuenta existente o nueva (password/Google/Apple); idempotencia; resend/revoke; límite de staff; baja invalida contexto/sesiones; auditoría completa.

**Auditoría/entrega local 2026-08-20:** confirmados y cerrados en el backend el token persistente hasheado con consumo atómico y vencimiento, metadata hotel/rol/invitador, aceptación password para cuenta existente/nueva, idempotencia por hotel/email, resend/revoke, invalidación de sesiones/JWT al dar de baja y auditoría de invite/accept/resend/revoke/role change. El límite de staff queda `BLOCKED` por el enforcement de entitlements de `TECH-0050`; Google/Apple quedan condicionados a `TECH-0024`. El checkout actual no contiene `app/services/membership_service.py` ni evidencia de la implementación de `TECH-0030`, por lo que su invariante de owner permanece `needs-verification` fuera de este cambio.

---

### TECH-0040 — RBAC granular configurable por hotel

Status: `VERIFY`
Priority: `P0`  
Depends on: `TECH-0010`, `TECH-0030`

**Goal:** matriz UX basada en la captura: filas de permisos y columnas Owner/Co-owner/Manager/Recepción/Housekeeping, badges Base/Override.

**Required:** catálogo de permisos estable; defaults; overrides por rol/hotel; roles personalizados; override por membership sólo si se confirma; precedencia determinista y deny explícito; metadata critical/step-up/delegable; versionado/ETag; restaurar base; historial.

**Acceptance:** backend deniega, cambio afecta sólo hotel correcto, concurrencia no pisa cambios, Owner no se autobloquea y toda modificación queda auditada.

---

### TECH-0041 — Autorización temporal de una sola acción

Status: `VERIFY`
Priority: `P1`  
Depends on: `TECH-0023`, `TECH-0040`, `TECH-0070`

**Goal:** recepcionista solicita una acción no permitida (p. ej. descuento), Owner/Manager aprueba y se emite grant single-use.

**Required:** solicitud ligada a hotel, actor, sesión, permiso, recurso, parámetros/monto, motivo y expiración; aprobador autorizado; TOTP autentica al aprobador y no funciona como PIN maestro; token hasheado; consumo atómico; idempotencia; estados pending/approved/denied/used/expired/revoked.

**Implementación TECH-0041 (2026-08-20):** el núcleo de solicitud, aprobación MFA, token single-use hasheado, consumo atómico, denegación, revocación, expiración best-effort y rutas tenant-scoped está implementado. La integración del grant en acciones de negocio reales (pagos, descuentos u otras operaciones) y el vínculo a sesión/parámetros/monto quedan fuera de este cambio.

---

### TECH-0050 — Catálogo de planes y entitlements

Status: `VERIFY`
Priority: `P1`  
Depends on: `TECH-0000`

**Required:** catálogo/versiones; precio, moneda e impuestos; room/staff/integration/AI/analytics limits; entitlement separado de permiso; snapshot contractual; enforcement backend; usage observable.

---

### TECH-0051 — Suscripciones, descuentos y bonificaciones

Status: `VERIFY`
Priority: `P1`  
Depends on: `TECH-0050`, `TECH-0071`

**Required:** estados/trial/período/grace/comped; descuentos, créditos, extensión gratis y overrides con motivo/autor/vigencia; idempotencia; historial append-only; master step-up; no alterar retroactivamente contratos.

---

### TECH-0060 — Búsqueda rápida de huéspedes

Status: `VERIFY`
Priority: `P1`  
Depends on: `TECH-0010`

**Acceptance:** búsqueda parcial tenant-scoped por nombre/apellido y campos autorizados; ranking; limit/cursor; índices/query plan; debounce/cancelación; no cargar tabla completa; benchmark y objetivo p95 documentados.

---

### TECH-0061 — Cotización, disponibilidad y tarifas rápidas

Status: `VERIFY`
Priority: `P1`

**Acceptance:** fuente autoritativa; hotel/categoría/fechas/huéspedes/rate plan; disponibilidad, breakdown, total y restricciones coherentes; caché nunca devuelve silenciosamente precio viejo; invalidación y edge cases testeados.

---

### TECH-0062 — Optimización de asignación de habitaciones

Status: `VERIFY`
Priority: `P1`

**Required:** auditar OR-Tools/Celery/Redis actuales; separar asignación rápida de reoptimización completa; jobs asíncronos; categoría/capacidad/huecos/reservas/asignaciones fijas; idempotencia, retries, concurrencia, explicabilidad y auditoría; no bloquear API.

---

### TECH-0063 — Performance y eficiencia OLTP

Status: `VERIFY`
Priority: `P1`

**Required:** índices por queries reales comenzando por hotel cuando corresponda; evitar N+1; selects/payloads acotados; cursor pagination; pool; transacciones cortas; locks; `EXPLAIN ANALYZE BUFFERS`; read models/materialized views; cache versionada e invalidación; p95/p99, locks y crecimiento observables.

---

### TECH-0070 — Audit log del hotel

Status: `VERIFY`
Priority: `P0`  
Depends on: `TECH-0010`

**Required:** append-only; hotel, actor/membership, acción, recurso, resultado, timestamp y before/after redactado; permisos, reservas, tarifas, caja, pagos, staff, integraciones, grants e IA; filtros/paginación/exportación; retención; usuarios no alteran logs; Owner sólo ve su hotel.

---

### TECH-0071 — Master SaaS Control Plane

Status: `VERIFY`
Priority: `P1`  
Depends on: `TECH-0023`, `TECH-0050`, `TECH-0070`

**Goal:** plano separado, nunca SUPER_OWNER dentro de memberships.

**Required:** platform admins/sesiones/permisos propios; MFA; sesiones cortas; CSRF/reauth; hoteles, habitaciones, empleados/invitaciones, plan/estado/uso, cobro, descuentos/bonificaciones, health, errores/jobs, MRR/ARR; auditoría master independiente; PII operativa excluida por defecto; soporte excepcional temporal/consentido/auditado.

---

### TECH-0080 — Data Warehouse foundation

Status: `BLOCKED`
Priority: `P2`  
Depends on: `TECH-0063`

**Required:** PostgreSQL autoritativo; CDC/outbox/ELT incremental e idempotente; staging/raw; transformaciones versionadas; BigQuery preferido pero decisión documentada frente a facts actuales/ClickHouse/otras; tenant, lineage, calidad, reconciliación, PII mínima, freshness y alertas por lag.

---

### TECH-0081 — Hotel Analytics Data Marts

Status: `VERIFY`
Priority: `P2`  
Depends on: `TECH-0080`

**Metrics:** nacionalidades, huéspedes recurrentes, ocupación, ADR, RevPAR, estadía media, revenue/margen, categoría, canal, cancelaciones/no-show y comparaciones. Todo tenant-scoped, definiciones y freshness visibles.

---

### TECH-0082 — SaaS Owner Data Mart

Status: `BLOCKED`
Priority: `P2`  
Depends on: `TECH-0080`, `TECH-0071`

**Metrics:** hoteles/active/trial/churn, plan, rooms/staff, reservations, API/storage/AI/integrations/jobs/errors, MRR/ARR. Agregados sin movimientos internos ni PII de huéspedes por defecto.

---

### TECH-0090 — PWA y responsive operacional

Status: `VERIFY`
Priority: `P2`

**Acceptance:** desktop/mobile/tablet; manifest/icons/installability; auth instalada; offline explícito sin datos falsamente actuales; pantallas críticas y UX completa verificadas.

**Auditoría y evidencia — 2026-08-21:**

- `code_sha`: `f85b8286e9cc7a7391e361b1cc18869ecad608bc` (`feat(pwa): consolidate installability and offline UX`).
- Se auditó `frontend/public/manifest.webmanifest`, `frontend/public/sw.js`, `frontend/index.html`, el registro de service worker en `frontend/src/main.tsx` y el shell operativo en `frontend/src/ui/AppShell.tsx`.
- Manifest consolidado: `name`, `short_name`, `lang`, `id`, `start_url`, `scope`, `display=standalone`, `theme_color` y `background_color` consistentes; iconos PNG reales de `192x192` y `512x512`, más variantes `maskable` de ambos tamaños generadas localmente desde el asset de marca existente.
- Service worker auditado: sólo cachea shell estático; `/api` y `/health` quedan fuera de caché, no hay persistencia de respuestas operativas ni cola offline de escrituras. Esto evita mostrar reservas, habitaciones o cobros cacheados como si fueran actuales.
- UX offline consolidada: `AppShell` muestra un banner global cuando `navigator.onLine` es falso y advierte que los datos pueden estar desactualizados, que reservas/check-in/out/cobros requieren conexión y que no se reintentan escrituras automáticamente. El error de backend también dejó de describir el modo offline de forma ambigua.
- Responsive auditado sin rediseño: la cobertura existente de `frontend/e2e/responsive-smoke.spec.ts` contempla viewports de 375/390/430 px, targets táctiles y ausencia de overflow; reservas ya usa cards en mobile y tabla controlada en desktop/tablet. No se encontró un bug concreto adicional que justificara tocar dashboard, reservas o check-in.
- Validación ejecutada en este checkout: `npm run lint` ✅, `npm run typecheck` ✅, `npm run build` ✅ y `npm run test:pwa` ✅ (3 pruebas). `test:pwa` verifica metadata, dimensiones/archivos de iconos, exclusión de API/health del service worker y presencia del mensaje stale/offline.
- No hubo migraciones ni cambios de deploy/hosting/cuentas. La compatibilidad de tipos de `PushSubscriptionOptions` se ajustó en `frontend/src/hooks/usePushSubscription.ts` para que el typecheck actual no quede bloqueado por `Uint8Array<ArrayBufferLike>`.

**`needs-verification` pendiente:** no se ejecutó Lighthouse ni una sesión de navegador real en desktop/mobile/tablet en este entorno. Antes de marcar `VERIFIED`, validar sobre un preview autorizado: Application/Manifest y Service Worker en Chrome, instalación desde `app.hotels-pms.com`, login y navegación autenticada desde la PWA instalada, desconexión con datos previamente cargados (banner visible y sin mutaciones silenciosas), reconexión, y recorridos dashboard/reservas/check-in en viewport desktop, tablet y teléfono. Confirmar además instalación/auth en Safari iOS y Chrome Android si esos dispositivos están en alcance.

---

### TECH-0091 — Capacitor iOS/Android y stores

Status: `DEFERRED`  
Priority: `P3`  
Depends on: `TECH-0090`, `TECH-0024`, `TECH-0025`

**Required:** reutilizar frontend; builds iOS/Android; API/redirect/deep links; secure storage; dispositivos reales; documentación de Apple Developer/Google Play, privacidad y publicación. Las cuentas/pagos de stores son responsabilidad humana.

---

### TECH-0092 — Desktop dedicado

Status: `DEFERRED`  
Priority: `P3`  
Depends on: `TECH-0090`

Sólo evaluar Tauri si aparecen requisitos reales de hardware, archivos, offline avanzado, procesos en background o integración OS. PWA es la opción inicial.

---

### TECH-0100 — IA read-only con tools controladas

Status: `DEFERRED`  
Priority: `P3`  
Depends on: `TECH-0040`, `TECH-0050`, `TECH-0070`, `TECH-0081`

**Required:** sin SQL directo; herramientas tipadas; usuario/hotel/membership/entitlement/permiso en cada llamada; datos operativos desde servicios OLTP y análisis desde marts; PII mínima; cuotas; tool calls auditadas; respuestas con freshness/fuente.

---

### TECH-0101 — IA con escrituras confirmadas

Status: `DEFERRED`  
Priority: `P3`  
Depends on: `TECH-0100`, `TECH-0041`

**Required:** propuesta/diff antes de acciones sensibles; confirmación humana; revalidación al ejecutar; step-up/grant si corresponde; validación; transacción/idempotencia; partial failures; auditoría actor humano + IA + before/after; el LLM nunca decide su propio permiso.

---

### TECH-0110 — Backups, recuperación y continuidad

Status: `IN_PROGRESS`
Priority: `P1`

**Required:** backups automáticos, PITR, retención, copia/backup inmutable cuando corresponda, archivos versionados/soft delete, RPO/RTO, restore drills, runbooks y alertas. Un backup no cuenta como verificado hasta restaurarlo.

**Evidencia local — 2026-08-21:**

- SHA base auditado: `6fd71f08de84b5c891b9ea9e47d8f802831f964f`.

- `app/models/guest.py` y `app/models/payment.py` incorporan el envelope nullable
  `deleted_at`/`deleted_by_user_id` e índices tenant-scoped; reservas, habitaciones,
  documentos, tarifas y stock ya tenían soft-delete operativo. La migración
  `alembic/versions/20260821_tech0110_operational_soft_delete.py` es aditiva,
  reversible y no cambia el ledger ni agrega endpoints de borrado.
- `scripts/backup/verify_local_backup_restore.py` implementa dump → restore
  descartable para SQLite y PostgreSQL local-only; compara conteos de
  `guests`, `reservations`, `payments` y `audit_logs` y valida integridad SQLite.
- Resultado reproducible local: `status=verified`, `integrity_check=ok`,
  `foreign_key_check=ok`, conteos de tablas fuente/restaurada iguales. El
  resultado ejecutado con fixture sintético fue `audit_logs=1`, `guests=1`,
  `payments=0`, `reservations=0`; el comando y la limitación del entorno quedan en
  `docs/runbooks/backups-and-continuity.md`.
- `render.yaml` permite confirmar sólo que Render ejecuta Alembic pre-deploy y
  que su Key Value declara `journal-snapshot`; el repo no declara backup/PITR de
  PostgreSQL. Disponibilidad, retención, inmutabilidad, alertas y plan Supabase
  quedan `needs-verification` en la consola del proveedor.

**Pendiente de acción humana:** confirmar RPO/RTO/retención contratados, activar o
ajustar PITR si corresponde, definir copia inmutable, configurar alertas, y
ejecutar/firma un restore drill real sobre un destino aislado de
Render/Supabase. No se restauró producción ni se modificaron cuentas, secretos,
billing o cutovers.

**Runbook:** `docs/runbooks/backups-and-continuity.md`.

**Cierre de entrega:** commit convencional, push y PR quedan pendientes porque
el sandbox no permite escribir el índice/git común del worktree
(`/Users/maximopaulos/AI-Workspace/projects/Hotel-Chipre-PMS/.git`).

---

### TECH-0111 — Secretos, red y protección cloud

Status: `VERIFY`
Priority: `P0`

**Required:** secretos fuera de Git/frontend/logs; rotación; DB/Redis privados; TLS; WAF/DDoS/rate limits; IAM mínimo; KMS; observabilidad; separación dev/staging/prod; pagos mediante proveedor sin almacenar tarjeta/CVV.

---

### TECH-0112 — CI/CD y ambientes seguros

Status: `BLOCKED`
Priority: `P0`

**Required:** feature branch→PR→tests→preview→staging→verificación→main→producción; DB y secretos separados; migraciones controladas; rollback; releases atadas a SHA; agentes no empujan experimentos directamente a usuarios reales.

**Auditoría/implementación 2026-08-21:** el código versionado de PR/tests,
preview trusted, gates de evidencia y build SHA-only quedó implementado y
documentado en [`docs/ci-cd-runbook.md`](ci-cd-runbook.md). El commit de
implementación es `292d53ca24e5cdcb392ecb75d6eba63c4a9eea15`. Se agregó la
validación reusable `scripts/agent_ops/verify_release_sha.py`, tests negativos,
la comprobación de migraciones sobre DB descartable en PR y el manifest de
artifacts inmutables del build. La evidencia de esta entrega debe asociarse al
SHA completo del commit de implementación en el PR.

El bloque completo permanece `BLOCKED`: este checkout no prueba un ambiente
staging formal, DB/secrets staging separados, branch protection ni aprobación
humana de producción; además `render.yaml` todavía declara `autoDeploy: true`.
Crear/configurar esos recursos o cambiar la cuenta GitHub/proveedores está
fuera de la autorización de esta tarea. No se ejecutaron deploys, migraciones
cloud, cambios de secrets, billing ni cutovers. Rollback de aplicación,
rollback/forward-fix de Alembic y el drill por ambiente quedan documentados,
pero requieren autorización y una infraestructura staging real.

---

### TECH-0120 — Migración progresiva de infraestructura

Status: `DEFERRED`  
Priority: `P2`  
Depends on: `TECH-0110`, `TECH-0111`, `TECH-0112`

**Secuencia objetivo sujeta a aprobación:**

1. crear/proteger proyectos y billing dev/staging/prod;
2. desplegar Cloud Run staging conectado inicialmente a Supabase;
3. validar paridad funcional completa;
4. crear Cloud SQL staging y migrar datos sanitizados;
5. validar Alembic, performance, PITR y restore;
6. migrar backend producción manteniendo DB anterior;
7. sincronizar/cutover DB con rollback;
8. mover Redis/workers;
9. agregar analytics/BigQuery;
10. retirar Render/Supabase sólo con evidencia y autorización.

No cambiar hosting, DB, queues, Auth y analytics simultáneamente. No usar Kubernetes en esta etapa salvo decisión posterior basada en necesidad.

---

### TECH-0130 — Pentest externo y release público

Status: `DEFERRED`  
Priority: `P0` antes de aceptar hoteles reales  
Depends on: `TECH-0010`, `TECH-0023`, `TECH-0041`, `TECH-0071`, `TECH-0111`, `TECH-0112`

**Scope mínimo:** Auth/MFA/recovery/sessions; cross-tenant/IDOR; RBAC/privilege escalation; OAuth/invitaciones/grants; APIs/pagos/webhooks; Master Admin/soporte; PII/secrets.

**Gate:** cero hallazgos críticos/altos abiertos; remediación revalidada; release SHA y evidencia certificada correctos. Tests internos o escáneres no sustituyen revisión independiente.

## 7. Decisiones abiertas

El agente puede investigar y recomendar, pero no decidir silenciosamente:

- sesiones web completas vs esquema híbrido para mobile/API;
- modelo canónico entre implementaciones RBAC/suscripciones existentes;
- múltiples roles y overrides personales en primera versión;
- aprobadores y límites de grants temporales;
- obligatoriedad/calendario MFA Owners;
- claves para TOTP/OAuth y estrategia RLS;
- Primary Owner/recovery y retención de auditoría;
- BigQuery frente a facts actuales/ClickHouse y umbrales de warehouse; ver la [propuesta de opciones y recomendación de TECH-0080](decisions/tech-0080-warehouse-options.md). La decisión sigue abierta hasta elección humana;
- alcance inicial de PWA, Capacitor, passkeys y apps;
- región, HA, RPO/RTO, presupuesto y fecha de migración cloud;
- proveedor/ventana del pentest.

Toda contradicción material se marca `needs-verification` y se presenta al Product/Project Lead.

### TECH-0140 — Fundaciones pre-lanzamiento

Status: `IMPLEMENTED LOCALLY / PROVIDER-VALIDATION PENDING`  
Priority: `P0/P1`  
Depends on: `TECH-0110`, `TECH-0111`, `TECH-0120`

Este bloque consolida recovery realtime, identidad Google segura, outbox
durable, Redis/Valkey efímero, PostgreSQL bounded, object storage, jobs,
readiness, restore local y portabilidad GCP. PostgreSQL permanece como fuente
operacional de verdad. La implementación local no autoriza OAuth externo,
billing, recursos GCP, migración/cutover, carga contra producción ni un restore
provider-bound. Sus gates restantes son QA humana, métricas de proveedor,
restore firmado y pentest/release cuando corresponda.

## 8. Acciones reservadas al responsable humano

- crear cuentas/organizaciones cloud y usuarios break-glass;
- aceptar costos, billing, budgets y contratos;
- introducir/rotar credenciales y secretos reales;
- configurar Apple Developer/Google Play y aceptar términos;
- aprobar migraciones/cutovers productivos;
- autorizar borrado/retiro de infraestructura;
- contratar pentest y aceptar riesgos;
- decidir cambios comerciales de precio/planes.

El agente puede preparar IaC, runbooks, checklists y comandos seguros, pero debe detenerse antes del efecto externo irreversible si falta autorización.

## 9. Trazabilidad de cobertura

| Área | Bloques |
|---|---|
| Auth propio, Argon2id, sesiones, recovery | TECH-0020–0022 |
| MFA, Google, Apple, passkeys/Face ID | TECH-0023–0025 |
| Multi-hotel, Primary Owner, invitaciones | TECH-0030–0031 |
| Matriz RBAC y permiso temporal TOTP | TECH-0040–0041 |
| Planes, límites, descuentos y bonificaciones | TECH-0050–0051 |
| Búsqueda, tarifas, optimizer y performance | TECH-0060–0063 |
| Auditoría y panel Master SaaS | TECH-0070–0071 |
| Data Warehouse, Data Marts y BigQuery | TECH-0080–0082 |
| PWA, iOS/Android/Face ID y desktop | TECH-0090–0092 |
| IA read/write con permisos | TECH-0100–0101 |
| Backups, cloud security y CI/CD | TECH-0110–0112 |
| Migración Render/Supabase→GCP | TECH-0120 |
| Pentest/release | TECH-0130 |

## 10. Changelog

### 2026-08-20

- Se consolidaron el backlog técnico del 19 de agosto y la arquitectura Auth/RBAC/datos del 20 de agosto.
- Se incorporó el contexto ampliado de producto, analytics, infraestructura, PWA/Capacitor, optimización e IA.
- Todos los objetivos se convirtieron en bloques ejecutables con prioridad, dependencias y criterios.
- Este archivo se designó como única entrada recomendada para el agente de desarrollo.

### 2026-08-21

- TECH-0000 cerrado como `VERIFIED` con evidencia del checkout `6fd71f0`; matriz completa y plan publicados en `docs/audits/tech-0000-system-audit.md`.
- Se actualizaron los estados de los bloques auditados: `VERIFY`, `TODO`, `BLOCKED` y `DEFERRED` según evidencia de código/tests/migraciones. No se resolvieron decisiones abiertas de sección 7.

## 11. Product Lead Inbox

Nuevas ideas técnicas deben convertirse en `TECH-XXXX` antes de iniciar desarrollo.

Pending: none.
