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

---

## 10. Resultado de implementación posterior al SHA auditado

Esta sección registra un cambio posterior al análisis. Las observaciones de las secciones 2–5 siguen describiendo el snapshot `f895899`; no deben leerse como el estado final después del trabajo de implementación.

### Entregado en `main` y desplegado

- **Step-up P0:** el backend exige un ticket MFA corto para capacidades sensibles. El ticket queda ligado a usuario, hotel, versión de sesión, permiso, método y ruta, expira a los 120 segundos y no sustituye la autorización normal. El cliente maneja el `428` solo mientras la misma sesión continúa activa; logout o cambio de cuenta/hotel/token cancela el prompt y evita repetir la acción con un ticket viejo.
- **Grant de cancelación:** el permiso temporal solo cubre `reservation:cancel` sobre la reserva exacta del mismo hotel. Lo solicita el empleado, lo aprueba owner/co-owner con MFA, dura 15 minutos y se consume de forma atómica en la misma transacción que la cancelación. El antiguo endpoint aislado de consumo se retiró con respuesta `410`.
- **Roles custom P1:** tabla tenant-scoped, códigos `cr_…`, presets base manager/receptionist/housekeeping, cambios optimistas versionados, y bloqueo de archivado mientras queden memberships activas o invitaciones pendientes. Owner/co-owner y capacidades `owner_only` siguen protegidos. La UI permite administrar permisos y ventanas por hotel y conserva los roles protegidos en solo lectura.
- **Cobertura de rutas:** se migraron las guardas estáticas de disponibilidad, listado/consulta/creación de reservas y check-in/check-out del router legacy de bookings a permisos canónicos. Esto reduce una inconsistencia real, pero **no significa que todas las guardas por rol del repositorio estén retiradas**; las restantes deben clasificarse como capacidad configurable, límite de negocio o invariante y conservar pruebas acordes.
- **Tareas operativas:** el acceso se limita por asignación para roles sin permiso de administración; historial y cambios vuelven a verificar el alcance con bloqueo, los datos de reserva se redactan si falta `reservation:read`, y respuestas de tareas inexistentes/fuera de alcance no revelan si el ID existe.
- **Concurrencia:** las lecturas de matriz/perfiles y overrides por empleado exponen la versión actual de cada override; la UI la envía al mutar y al restaurar. Una lectura obsoleta continúa produciendo `409`, no una sobrescritura silenciosa.
- **Migraciones adicionales:** `hotel_roles` nace con RLS habilitado/forzado y su política tenant; una migración separada normaliza cinco enums PostgreSQL restantes. El downgrade de roles custom cancela antes de modificar esquema si no puede comprobar que no haya datos que perder.

### Evidencia de implementación y despliegue

La ejecución local completa terminó con **2.122 passed, 26 skipped, 12 xfailed, 1 xpassed y 37 warnings**, excluyendo deliberadamente `tests/integration/test_postgres_migrations.py`. La prueba focal de tareas operativas terminó con **8 passed**. En frontend, **39 tests**, TypeScript, lint y build pasaron; la build reporta un chunk mayor a 500 kB. El E2E de roles custom enumeró cinco casos, pero no se ejecutó: Playwright fuerza el reset del archivo fijo `_e2e.db` en la raíz del repositorio, que ya existía como estado local no versionado y fue preservado.

El commit `558d7ec` se publicó mediante push normal a `main`; Vercel quedó `READY` y Render `live`, ambos con ese SHA. El endpoint público `/health` respondió 200 y devolvió el SHA esperado. El comando efectivo de arranque de Render ejecuta `alembic upgrade head` antes de Uvicorn; Supabase confirmó la cabeza `20260924_action_stepup_single_use`, las tablas `hotel_roles` y `action_step_up_ticket_uses` con RLS habilitado y forzado, sus políticas tenant y las cinco familias de enum con etiquetas normalizadas. Esto prueba que la migración de PostgreSQL corrió en el deploy activo; no sustituye una prueba de restauración del backup.

Antes del deploy se generó en almacenamiento local con FileVault activo un respaldo lógico de la base activa, con modo `0600`, SHA-256 registrado y lectura completa verificada por `pg_restore --list`; el archivo no se agregó al repositorio. Supabase está en plan Free, por lo que no se presupone backup diario administrado. El respaldo debe conservarse durante la ventana de rollback acordada y eliminarse después de forma controlada.

La corrida `qa/operational/runs/rbac-prod-main-smoke-20260924-f895899` es explícitamente **no certificante** y describe el SHA anterior: salud, login anónimo y formulario público sin enviarlo. No se probó la matriz autenticada con owner/empleados; no se creó usuario, no se envió correo y no se ejecutaron pagos, webhooks ni sincronización OTA. Las identidades sintéticas quedan como gate pendiente. Las pruebas de navegador con API simulada prueban el cliente/UI, no integración backend autenticada en producción.

### Hallazgo posterior: step-up repetido al leer la administración RBAC

En la prueba autenticada de solo lectura con el owner, la vista de permisos quedó en una secuencia de diálogos TOTP; el usuario confirmó que el código fue aceptado y luego rechazado como ya usado. La ruta de código explica el síntoma: `SettingsPermissionsPage.tsx` dispara varias lecturas paralelas —catálogo, matriz, perfiles, ventanas y overrides del empleado seleccionado— y `require_permission_administrator` exigía un ticket ligado a método y ruta para cada una. El ticket se consume una sola vez; un mismo TOTP no puede autorizar todos esos requests. No se conservaron códigos ni tokens ni se atribuye el síntoma a un TOTP inválido.

La primera corrección candidata quitaba el step-up en `GET`/`HEAD`. La revisión adversarial la rechazó antes de publicarla: una sesión owner robada habría podido leer la matriz y los overrides RBAC sin volver a presentar MFA. Esa variante no se despliega.

La corrección implementada localmente conserva MFA en todas las lecturas y escrituras sensibles. Un TOTP fresco puede emitir un grant separado de solo lectura, limitado a una lista cerrada de rutas RBAC, mismo usuario/hotel/versión de sesión y 120 segundos. El grant puede reutilizarse durante esa ventana solo para `GET`/`HEAD`; no sirve para cambios, otros permisos ni otros tenants. El cliente lo mantiene únicamente en memoria y, dentro de la cola de challenges, comparte el primer grant entre las lecturas paralelas de la pantalla. Las escrituras conservan tickets de acción ligados a método/ruta, de un solo uso. La protección anti-replay del TOTP no se debilita y no se requiere migración de base.

El checkout local sigue en `main` sobre `558d7ec`, sin publicar esta corrección todavía. La suite focal de backend pasó **80 pruebas** y la suite completa terminó con **2.124 passed, 27 skipped, 12 xfailed, 1 xpassed y 37 warnings**. Frontend: **44 tests**, typecheck, lint y build pasaron; Vite conserva el warning preexistente de un chunk principal >500 kB. El smoke autenticado posterior al deploy sigue pendiente. La evidencia local previa a este cambio no se presenta como validación del arreglo; `558d7ec` sigue siendo el SHA desplegado hasta completar publicación y verificación.

El análisis encontró además que los roles custom heredan los permisos efectivos del preset base hasta que se agrega un override explícito; un rol basado en manager conserva `reservation:read` salvo que se revoque. El permiso genérico de vista de tareas no tiene todavía una dimensión de tipo de tarea, por lo que un rol report-only manager puede ver tareas no asignadas de distintos tipos. No se amplió el catálogo para resolver esta decisión de producto sin evidencia de negocio. El arranque de Render migra el esquema antes de servir y hoy opera con una instancia; antes de escalar conviene aislar la migración en un único paso serializado para evitar ejecuciones concurrentes.

El escáner automatizado de seguridad no pudo inicializar porque cambió el HEAD después de seleccionar el diff; no se generaron ni inventaron artefactos de escaneo. Hubo revisión independiente read-only de la implementación y los hallazgos encontrados se corrigieron y se cubrieron con pruebas; el último ajuste quedó validado por tests, sin una segunda revisión independiente.

No se agregó dependencia de Casbin, OpenFGA, SpiceDB u OPA; se conserva la recomendación del ADR: no migrar el runtime hasta validar casos ReBAC de producto y completar la evidencia operativa/tenant. El merge de PR #91 no se recomienda sin corregir primero la regresión de CI y el aumento de instancias; la rama de consultas públicas se preserva hasta acordar acceso/retención de PII y correo. La selección de motor sigue sin requerir decisión de compra.
