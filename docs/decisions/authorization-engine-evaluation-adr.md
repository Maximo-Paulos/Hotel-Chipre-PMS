# ADR — Evaluación de motores de autorización externos (Casbin/PyCasbin, OpenFGA, SpiceDB, OPA)

**Fecha:** 2026-09-24
**Estado:** Propuesta — no se recomienda migrar runtime ahora
**Código base auditado:** `f895899` (`security/authorization-engine-pilot-claude`, worktree `hotel-chipre-rbac-claude-20260924`)
**Alcance:** documentación únicamente (`docs/`). No se tocó `app/`, `frontend/`, migraciones, dependencias, runtime, Docker ni CI.
**Autores:** Claude Code (consolidación), con revisión de agentes read-only `engine-evaluator` y `pilot-threat-reviewer`.

---

## Cómo leer este documento

Cada afirmación está etiquetada:

- **Confirmado (código):** verificado leyendo el código de este repo en el SHA indicado.
- **Confirmado (fuente oficial):** contrastado con documentación oficial consultada el 2026-09-24. Los precios y planes comerciales pueden cambiar; volver a verificarlos antes de presupuestar o contratar.
- **Inferencia:** conclusión razonada a partir de lo confirmado, no un hecho medido directamente.
- **Supuesto:** premisa explícita usada para estimar (equipo, alcance, SLA), no un hecho.

---

## 1. Resumen ejecutivo

**Recomendación: no migrar el runtime de autorización ahora.** El PMS ya tiene un modelo RBAC hotel-scoped con matriz de permisos configurable, más aislamiento multi-tenant reforzado con Row-Level Security real de PostgreSQL como segunda capa (defensa en profundidad). No existe hoy un caso de producto validado que requiera relaciones tipo grafo (ReBAC) que el modelo actual no pueda expresar. Migrar introduciría un servicio/dependencia nueva, un pipeline de sincronización con consistencia eventual, y un nuevo plano de fallo — sin un beneficio de producto confirmado que lo justifique.

Este ADR compara Casbin/PyCasbin, OpenFGA, SpiceDB y OPA como referencia para el día en que exista un caso ReBAC real, y documenta el piloto sintético (`docs/authorization-engine-pilot/`) que prueba el patrón de modelado sin tocar datos reales.

---

## 2. Estado actual del sistema (confirmado por código)

- El modelo vigente es **RBAC por hotel, sin entidad `Role` configurable**: cada `HotelMembership` guarda un código de rol; los cinco roles built-in son `owner`, `co_owner`, `manager`, `receptionist` y `housekeeping`. No hay una tabla `user_roles` ni herencia jerárquica de roles. — **Confirmado (código):** `app/models/hotel_membership.py`, `app/services/permission_service.py:36-41`.
- Los permisos se definen en un catálogo y se resuelven con esta precedencia: **invariante de seguridad > override de usuario > override de rol dentro del hotel > default global del rol > deny**. Los roles desconocidos se deniegan por defecto. — **Confirmado (código):** `app/models/permission.py`, `app/services/permission_service.py:736-787`.
- Los valores base de los cinco roles son globales (`role_permission_defaults`); las personalizaciones de cada hotel viven en `hotel_permission_overrides`, y las excepciones de empleado en `user_permission_overrides`. La ventana de visibilidad de reservas se configura por hotel y rol, pero su tabla enumera los cinco roles built-in. — **Confirmado (código):** `app/models/permission.py`, `app/models/hotel_role_visibility_window.py`, `app/services/permission_service.py:804-848`.
- La resolución de tenant es server-side y centralizada: `get_auth_context` en `app/dependencies/auth.py:134-161` autentica el JWT, aplica `set_tenant_user_context` (para que la resolución de membership ya esté protegida por RLS), resuelve la membership activa contra `X-Hotel-Id`/claim del token (nunca confía en `hotel_id` del cuerpo del request), y recién ahí aplica `set_tenant_hotel_context`. — **Confirmado (código):** `app/dependencies/auth.py:105-161`.
- La evaluación de permisos por request sigue una cadena de resolución explícita: **invariant > user > hotel role > role default > deny**, implementada en `app/services/permission_service.py:779-787` (`resolve` → `get_effective_permission_details`), con overrides por usuario y por rol-hotel, ventanas de visibilidad configurables (`HotelRoleVisibilityWindow`, líneas 804-848), y denegaciones auditadas (`audit_permission_denied`).
- El aislamiento multi-tenant tiene **dos capas independientes**, no solo el filtro `hotel_id` en cada query:
  1. Aplicación: casi todas las rutas (~380 de 418 registros) reciben `AuthContext` y filtran por `context.hotel_id` server-side. — **Confirmado (código, auditoría previa):** `docs/audits/tech-0010-tenant-isolation-audit.md:9-17`.
  2. Base de datos: PostgreSQL RLS real (no simulado), con políticas que leen `app.user_id`/`app.hotel_id` fijados por `set_config(..., is_local=true)` en cada transacción, reaplicados automáticamente tras cada commit vía un listener `after_begin`, y con un bypass explícito y auditado para master-admin (`alembic/versions/f3bdaadd3d15_master_admin_rls_bypass.py`). — **Confirmado (código):** `app/services/tenant_context.py:1-80`, `tests/test_tenant_rls_contract.py`, `tests/test_rls_live_verification.py`, `tests/test_master_admin_rls_bypass_pg.py`.
- El estado de esa auditoría de aislamiento es **`VERIFY` parcial, no `VERIFIED`**: no quedó ningún gap `TODO` abierto, pero faltan pruebas negativas cross-tenant dedicadas para varias familias de rutas (laundry, notifications, analytics exports, OAuth de integraciones, webhooks OTA, rutas públicas por API-key, WhatsApp, waitlist, room blocks, rates, y mutaciones de reservas/bookings). — **Confirmado (código/docs):** `docs/audits/tech-0010-tenant-isolation-audit.md:104-108`.
- No existe en este repo un motor de políticas externo (Casbin, OpenFGA, SpiceDB, OPA) ni una dependencia de grafo de relaciones. Todo el modelo es relacional en PostgreSQL con `hotel_id` como columna de partición discriminante en cada tabla de dominio. — **Confirmado (código):** `docs/data-foundations/architecture-hybrid.md:1-40`, ausencia de dependencias de esos motores en `requirements.txt`/`frontend/package.json` (no se modificó ni se agregó ninguna).
- **Riesgos del SHA base que sí justifican trabajo:** algunas rutas protegidas con guardas de rol estáticas pueden ignorar overrides de permisos configurables; además `step_up_required` existe en el catálogo, pero en el SHA base no se aplica como reautenticación MFA genérica antes de ejecutar la acción. Son brechas de enforcement del modelo actual, no evidencia de que haga falta otro motor. — **Confirmado (código, SHA base):** `app/dependencies/auth.py`, `app/services/permission_service.py:614-668` y routers de la API.

**Inferencia:** el sistema actual ya resuelve el problema que estos motores externos resuelven (autorización tenant-scoped, revocación, auditoría) con herramientas nativas del stack (Postgres + FastAPI), y agrega una segunda capa de defensa (RLS) que ningún motor externo reemplazaría automáticamente — seguiría siendo necesaria en paralelo si Postgres sigue siendo la fuente de verdad de los datos.

---

## 3. Qué problema resolvería migrar (y por qué no es hoy)

Los motores comparados brillan cuando el modelo de permisos deja de ser "rol dentro de un tenant" y pasa a ser un **grafo de relaciones** (ReBAC): ej. "puedo ver esta reserva si soy miembro del hotel dueño de la reserva, **o** si me la asignaron directamente, **o** si soy manager de un grupo de hoteles que incluye ese hotel". Hoy el PMS no tiene ese caso confirmado — el modelo hotel→rol→permiso con overrides cubre lo auditado en `docs/design/RBAC_DESIGN.md` y `docs/audits/tech-0010-tenant-isolation-audit.md`.

**Inferencia:** si en el futuro aparece un caso de producto genuinamente relacional (ej. cadenas hoteleras con managers cross-hotel, delegación temporal de reservas a un agente externo, permisos heredados por grupo/franquicia), ahí es donde ReBAC empieza a pagar su complejidad. No hay evidencia en este repo de que ese caso exista hoy — y hay evidencia de producto en sentido contrario: `docs/product-definition.md:47-56` excluye explícitamente del alcance de lanzamiento "businesses requiring full multi-property chain management" y marca "small chains (multi-property under one account)" como "considered for later, not launch". — **Confirmado (código/docs):** `docs/product-definition.md:47-56`.

---

## 4. Comparación de motores

### 4.1 Modelo de datos y expresividad

| Motor | Modelo | Expresividad | Fuente |
|---|---|---|---|
| **Casbin / PyCasbin** | Modelo declarativo `.conf` (`request_definition`, `policy_definition`, `role_definition`, `policy_effect`, `matchers`) y políticas en archivos/adapters. Soporta RBAC con dominio/tenant y ABAC. Es una **librería embebida** en Python, no un servicio separado. | Alta para RBAC/ABAC clásico; ReBAC posible, pero no es un motor de grafo dedicado. | **Fuentes oficiales:** [RBAC con dominios](https://v1.casbin.org/docs/en/rbac-with-domains), [PyCasbin y licencia](https://github.com/casbin/pycasbin). |
| **OpenFGA** | Modelo DSL (`type`/`relations`/`define`) + tuplas de relaciones. ReBAC nativo (Zanzibar-style), para expresar quién puede hacer qué sobre qué objeto mediante relaciones y composición. | Muy alta para ReBAC. Es un **servicio separado** con su propio datastore. | **Fuentes oficiales:** [modelado](https://openfga.dev/docs/modeling/getting-started), [tests de modelos](https://openfga.dev/docs/modeling/testing), [consistencia](https://openfga.dev/docs/interacting/consistency) y [operación en producción](https://openfga.dev/docs/best-practices/running-in-production). |
| **SpiceDB (AuthZed)** | Esquema de relaciones y permisos, con consistencia configurable por solicitud (`minimize_latency`, `at_least_as_fresh` y `fully_consistent`) y ZedTokens para read-after-write. | Muy alta para ReBAC. Es un **servicio separado** con datastore propio. | **Fuentes oficiales:** [consistencia](https://authzed.com/docs/spicedb/concepts/consistency), [read-after-write](https://authzed.com/docs/spicedb/concepts/read-after-write) y [precios/despliegues](https://authzed.com/pricing). |
| **OPA (Open Policy Agent)** | Motor general de políticas en Rego; decide sobre políticas y datos de entrada/bundles que se le suministran. No es un datastore de relaciones por sí mismo. | Flexible para ABAC y reglas generales. Puede correr como **sidecar/agente** o servicio centralizado, con trade-offs de latencia, recursos y tolerancia a fallos. | **Fuentes oficiales:** [modelos de despliegue](https://www.openpolicyagent.org/docs/deploy), [gestión/distribución](https://www.openpolicyagent.org/docs/management-introduction) y [decision logs](https://www.openpolicyagent.org/docs/management-decision-logs). |

### 4.2 Encaje con FastAPI / PostgreSQL / RLS (este stack)

- **Casbin/PyCasbin:** el único de los cuatro que corre **in-process** con FastAPI (no agrega un servicio de red nuevo). Podría leer/escribir políticas desde el mismo Postgres (adapter SQLAlchemy disponible). No reemplaza RLS — seguiría siendo una capa de aplicación, igual que `permission_service.resolve` hoy. **Inferencia:** de los cuatro, es el que menos cambia la topología operativa actual.
- **OpenFGA / SpiceDB:** ambos exigen un **servicio externo con su propio store de tuplas**, separado del Postgres transaccional del PMS. Esto crea el problema central de cualquier migración ReBAC en este stack: **dos fuentes de verdad** (Postgres para reservas/membresías reales, el motor de grafo para tuplas de autorización) que deben mantenerse sincronizadas. RLS seguiría siendo necesaria en Postgres como defensa en profundidad — un motor externo no filtra filas de SQL, solo responde "sí/no" o listas de IDs que la app debe volver a cruzar contra Postgres.
- **OPA:** encaja como gate adicional de reglas (ej. validar una transición de estado antes de comprometerla), no como reemplazo del filtro `hotel_id`/RLS. No resuelve el problema de "quién tiene qué relación con qué reserva" sin que alguien le arme y mantenga ese grafo aparte.

### 4.3 Consistencia y revocación

- **Casbin/PyCasbin:** consistencia = la de la conexión Postgres que uses (mismo Read Committed/transaccional que ya tiene el PMS). Revocación es inmediata en el mismo commit que borra el rol/permiso, igual que hoy.
- **OpenFGA:** ofrece opciones de consistencia por solicitud; el modo de menor latencia y las decisiones de caché deben evaluarse frente al objetivo de frescura/revocación. — **Fuente oficial:** `https://openfga.dev/docs/interacting/consistency`.
- **SpiceDB:** distingue `minimize_latency`, `at_least_as_fresh` con ZedToken y `fully_consistent`; usar frescura fuerte puede aumentar la latencia y reducir el uso de caché. — **Fuentes oficiales:** `https://authzed.com/docs/spicedb/concepts/consistency`, `https://authzed.com/docs/spicedb/concepts/read-after-write`.
- **OPA:** consistencia depende de cómo se recargan los "bundles" de datos/políticas (polling periódico o push); no es transaccional con Postgres por diseño — hay una ventana de staleness igual o peor que un cache de aplicación mal invalidado.

**Inferencia:** cualquier motor externo (OpenFGA/SpiceDB/OPA) introduce una ventana de revocación no-instantánea salvo que se pague el costo de consistencia fuerte en cada check — algo que hoy el PMS no tiene (RLS + filtro por `hotel_id` en la misma transacción son consistentes por construcción). Esto es exactamente el tipo de brecha que el criterio de reapertura de este ADR exige cerrar (ver §7) antes de considerar producción.

### 4.4 Latencia

- **Casbin/PyCasbin:** sin salto de red — evaluación en memoria del proceso Python; latencia agregada ≈ 0 vs. hoy.
- **OpenFGA/SpiceDB:** salto de red adicional por check (típicamente HTTP/gRPC a un servicio co-localizado); orden de magnitud de un dígito de milisegundos en el caso favorable (mismo datacenter/región), pero es **latencia nueva en el hot path de cada request autorizado**, sin medición propia en este stack.
- **OPA:** si corre como sidecar local, latencia baja (misma máquina); si es servicio remoto, análogo a OpenFGA/SpiceDB.

**Inferencia:** no hay benchmark propio de este PMS contra ningún motor — cualquier cifra de latencia citada por los proveedores es de sus propios entornos, no de esta carga de trabajo. Falta un SLO p95 propio definido para saber si esa latencia adicional importa (ver §7).

### 4.5 Disponibilidad

- **Casbin/PyCasbin:** disponibilidad = disponibilidad del propio backend (Postgres actual). No agrega un punto de falla nuevo.
- **OpenFGA/SpiceDB:** agregan un **servicio con estado nuevo** al blast radius de disponibilidad: si ese servicio cae o queda particionado, hay que decidir explícitamente fail-open (riesgo de seguridad) o fail-closed (outage funcional) — ninguna decisión de ese tipo existe hoy en este repo.
- **OPA:** igual que arriba si es remoto; si es sidecar embebido, el fallo está acoplado al proceso de la app (mismo blast radius que hoy).

### 4.6 Observabilidad

- **Casbin/PyCasbin:** se audita con la infraestructura de logging/auditoría que ya existe (`SecurityAuditLog`, igual que `permission_service._audit` hoy).
- **OpenFGA/SpiceDB:** cada uno expone sus propias métricas/tracing (Prometheus, OpenTelemetry documentados por ambos proyectos), pero es **observabilidad nueva a operar** — dashboards, alertas de latencia de check, alertas de lag de sincronización de tuplas — nada de eso existe en este repo hoy.
- **OPA:** decision logs nativos (útiles para debug de reglas), también nuevos de operar.

### 4.7 Mantenimiento y madurez operativa

- **Casbin/PyCasbin:** proyecto maduro, sin infraestructura propia que operar; el costo es de disciplina de modelado (matchers pueden volverse difíciles de leer si se abusa del ABAC).
- **OpenFGA / SpiceDB:** requieren operar o contratar el servicio y su datastore, más backups, upgrades, modelos versionados y observabilidad.
- **OPA:** requiere distribuir versiones de políticas/datos y elegir el despliegue; no provee por sí solo un plano de control central completo para la aplicación.

### 4.8 Licencias

Los componentes open source comparados publican licencias permisivas; PyCasbin declara Apache-2.0 y la oferta Open Source de SpiceDB declara Apache-2.0. Verificar la licencia de la versión exacta y de cada adapter/SDK antes de adoptar. La diferencia de costo real está sobre todo en el **modelo de despliegue**:

- Casbin/PyCasbin, OpenFGA, SpiceDB (self-hosted), OPA: software gratis, costo = tu propia infraestructura y tiempo de operación.
- SpiceDB gestionado por **AuthZed Cloud**: la página oficial consultada el 2026-09-24 anuncia despliegue desde **USD 2/hora** con cobro por recursos/uso. Es un precio de entrada publicado, **no una cotización ni TCO**. Confirmar directamente antes de presupuestar.
- OpenFGA no tiene oferta "cloud gestionada" propia del proyecto (es CNCF); alternativas gestionadas de terceros existirían pero no se investigaron aquí (fuera de alcance).

### 4.9 TCO (orden de magnitud, no un cálculo financiero)

**Supuesto explícito:** "TCO" acá es cualitativo — no hay presupuesto de infraestructura de este proyecto disponible para calcular cifras en USD/mes reales.

| Motor | Costo de licencia | Costo operativo nuevo | Costo de integración (este stack) |
|---|---|---|---|
| Casbin/PyCasbin | Ninguno | Ninguno (in-process) | Bajo — reemplaza/complementa `permission_service.resolve` sin nuevo servicio |
| OpenFGA (self-hosted) | Ninguno | Medio-alto — nuevo servicio + datastore + observabilidad + HA | Alto — pipeline de sincronización Postgres→tuplas, dual-write o CDC, reconciliación |
| SpiceDB (self-hosted) | Ninguno | Medio-alto — igual que OpenFGA | Alto — igual que OpenFGA |
| SpiceDB (AuthZed Cloud) | Página consultada: desde USD 2/h; precio de entrada sujeto a uso | Menor operación del motor, más dependencia/proveedor | Alto igual — el pipeline de sincronización lo seguís operando vos, solo el motor es gestionado |
| OPA | Ninguno | Medio — sidecar/servicio + bundles + decision logs | Medio — útil como gate de reglas, no resuelve el grafo de relaciones por sí solo |

**Inferencia:** el costo dominante de migrar a OpenFGA/SpiceDB en este stack no es la licencia ni el compute del motor — es construir y operar de forma **durable** el pipeline que mantiene las tuplas de autorización sincronizadas con la verdad relacional en Postgres (altas, bajas, y reconciliación tras fallos), sin el cual el motor externo puede autorizar contra datos obsoletos. Eso es exactamente el ítem "outbox/reconciliación durable" del criterio de reapertura (§7).

---

## 5. Estimaciones de esfuerzo (días-persona, supuestos explícitos)

**Supuestos base** (si cambian, las cifras cambian):
- 1 ingeniero backend senior, ya familiarizado con este repo, sin experiencia previa con el motor elegido.
- Alcance: un único motor evaluado a la vez, no los cuatro en paralelo.
- No incluye tiempo de aprobación/legal/compras (ej. negociar contrato con AuthZed).
- "Integración" es parcial (1-2 endpoints reales detrás de feature flag, modo sombra), no el sistema completo.
- "Cutover" asume que la fase de integración ya cerró sin hallazgos bloqueantes.

| Fase | Rango (días-persona) | Qué incluye |
|---|---|---|
| Evaluación (spike, un motor, sin integración) | 3–5 | Instalar/correr local, modelar 2-3 casos de este dominio, probar CLI/SDK, escribir hallazgos |
| Piloto sintético local (como el de este ADR, por motor) | 5–10 | Modelo + tuplas sintéticas + tests allow/deny, sin tocar Postgres real ni producción |
| Integración real parcial (1-2 endpoints, shadow mode, pipeline de sync) | 20–35 | Outbox/CDC desde Postgres, servicio del motor en staging, observabilidad, tests cross-tenant, modo sombra comparando contra RBAC actual sin reemplazarlo |
| Cutover completo (reemplazar decisión de autorización, decommission legacy, regresión completa, rollback probado) | 30–50 | Migrar todas las rutas auditadas en `tech-0010`, plan de rollback ensayado, runbook de incidente, SLO en producción |

**Total orden de magnitud si se migra todo el sistema:** ~60–100 días-persona, más costo operativo recurrente no capturado en esta tabla (on-call, backups del nuevo datastore, upgrades del motor). **Esto es una estimación, no un compromiso de sprint.**

---

## 6. Recomendación

**No migrar el runtime de autorización ahora.** Razones (todas confirmadas por código, no por preferencia):

1. El modelo RBAC hotel-scoped actual cubre lo auditado (`docs/design/RBAC_DESIGN.md`), con overrides por usuario/rol y ventanas de visibilidad — no hay un caso ReBAC de producto sin resolver.
2. El aislamiento multi-tenant ya tiene dos capas independientes (aplicación + RLS real de Postgres); ningún motor externo reemplaza RLS, así que migrar sumaría un tercer sistema sin restar ninguno de los dos actuales.
3. La auditoría de aislamiento (`tech-0010`) sigue en `VERIFY` parcial — hay trabajo de cierre pendiente en el sistema **actual** antes de justificar invertir esfuerzo en uno nuevo.
4. Migrar introduce un problema de consistencia (sincronización Postgres↔tuplas) que hoy no existe, con revocación potencialmente no-instantánea salvo pagar latencia de consistencia fuerte.

Este piloto y este ADR quedan como referencia lista para usar el día que aparezca un caso ReBAC de producto real.

---

## 7. Criterio de reapertura

Reabrir esta decisión **solo si se cumplen todos** los siguientes puntos:

1. Al menos **2 casos ReBAC de producto validados** (no hipotéticos) que el RBAC hotel-scoped actual no pueda expresar razonablemente.
2. **Paridad crítica 100%** entre el modelo actual y el motor candidato para las rutas ya auditadas en `tech-0010-tenant-isolation-audit.md`.
3. **Cero fugas cross-tenant** demostradas en pruebas negativas dedicadas (las mismas familias que hoy están en `VERIFY`, no solo las `VERIFIED`).
4. **SLO p95 de latencia de autorización y de revocación** definidos explícitamente y cumplidos bajo carga representativa del PMS (no benchmarks del proveedor).
5. **Outbox/reconciliación durable** entre Postgres y el store de tuplas del motor, con prueba de recuperación tras fallo parcial (no solo el camino feliz).
6. **Fail-closed** ante indisponibilidad o partición del motor externo (nunca fail-open por defecto).
7. **Plan de rollback** probado en al menos un ensayo, no solo documentado.

---

## 8. Fuentes

Fuentes externas consultadas el **2026-09-24**. La documentación técnica respalda las capacidades descritas; precios y planes comerciales son una fotografía de esa fecha y deben reconfirmarse al preparar un presupuesto.

- OpenFGA — modelado: `https://openfga.dev/docs/modeling/getting-started`
- OpenFGA — testing de modelos: `https://openfga.dev/docs/modeling/testing`
- OpenFGA — producción: `https://openfga.dev/docs/best-practices/running-in-production`
- OpenFGA — consistencia: `https://openfga.dev/docs/interacting/consistency`
- Casbin — RBAC con dominios: `https://casbin.org/docs/rbac-with-domains/`
- Casbin — repositorio y licencia: `https://github.com/casbin/casbin`
- PyCasbin — repositorio: `https://github.com/casbin/pycasbin`
- SpiceDB — consistencia: `https://authzed.com/docs/spicedb/concepts/consistency`
- SpiceDB — read-after-write: `https://authzed.com/docs/spicedb/concepts/read-after-write`
- AuthZed — precios: `https://authzed.com/pricing`
- OPA — despliegue: `https://www.openpolicyagent.org/docs/deploy`
- OPA — gestión: `https://www.openpolicyagent.org/docs/management-introduction`
- OPA — decision logs: `https://www.openpolicyagent.org/docs/management-decision-logs`

Fuentes internas (confirmadas por código en este SHA):

- `docs/design/RBAC_DESIGN.md`
- `docs/audits/tech-0010-tenant-isolation-audit.md`
- `docs/data-foundations/architecture-hybrid.md`
- `docs/security-baseline.md`
- `docs/product-definition.md`
- `app/dependencies/auth.py`
- `app/services/permission_service.py`
- `app/services/tenant_context.py`
- `tests/test_tenant_rls_contract.py`, `tests/test_rls_live_verification.py`, `tests/test_master_admin_rls_bypass_pg.py`

---

## 9. Revisión de agentes read-only

Este ADR fue revisado por los agentes read-only `engine-evaluator` (comparación independiente de motores/riesgos operativos) y `pilot-threat-reviewer` (revisión de amenazas del piloto). Sus hallazgos consolidados están incorporados en las secciones anteriores; ninguno de los dos tiene permiso de escritura y no modificaron código ni documentación por sí mismos.
