# Estado exhaustivo del sistema — Hotel Chipre PMS

## -3. Pasada de UI "estilo Apple" sobre el shell + e2e rescatados — 2026-09-17

`confirmed`: tipos, lint, 17 tests de nodo, build, suite backend (2012 passed, 0 failed) y **41 tests e2e de Playwright** (32 de journeys en Chromium + 24 del smoke responsive en 4 perfiles de iPhone, sin desborde horizontal), más verificación visual en navegador a 1440 y 375.

### Diagnóstico de partida

El producto tiene un design system deliberado en `tailwind.config.cjs` (radios `chip/control/panel`, elevación `raise/float/deep`, curva `ease-rack`, `brass` reservado a dinero, tipografía display) y **la app no lo usaba**: 0 usos de `rounded-panel/control/chip`, `shadow-raise/float`, `ease-rack` o `font-display` en `views/protected` + `ui`, contra 2199 `slate-`, 604 `rounded-lg`, 167 `shadow-sm`. Ya había existido un pedido del dueño de "sensación Apple HIG" (comentarios en `tailwind.css`), aplicado sólo al marketing.

### Qué cambió (el marco de todas las pantallas)

- Fuera la barra negra de identidad (repetía marca, hotel y email que el shell ya mostraba) y el banner verde permanente "Conectado: cambios en tiempo real activos". El estado sano es un punto en el header; los estados que requieren atención (conectando, reconectando, degradado, offline) siguen siendo banner. ~78px recuperados en cada pantalla, casi el 10% de un iPhone.
- `UserBadge` en una sola fila tipo cápsula. Antes, para el dueño, apilaba un select y un párrafo de ayuda dentro de un `rounded-full`: una "pastilla" deforme que dejaba el header en ~180px. La ayuda pasa a descripción accesible + tooltip; todos los controles siguen visibles (los e2e los usan directo). Bajo `md` se convierte en tarjeta dentro del panel móvil.
- `HotelSelector` no se renderiza con un solo hotel (un selector de una opción no es una elección) y perdió el "ID N" redundante. El hotel activo pasa a encabezar la sidebar y el panel móvil.
- Sidebar: grupos en minúscula con chevron que rota (antes MAYÚSCULAS + triángulo nativo), radios del sistema.
- Dashboard: título con presencia, cifras KPI con números tabulares, acción primaria rellena y secundaria discreta, paneles con `rounded-panel` + `shadow-raise` + anillo fino.
- Ortografía del menú y banners: Huéspedes, Analítica, Más operación, Configuración, Lavandería, Suscripción, Límite; "Room events" traducido. El banner de suscripción mostraba literalmente `(can_write=false)` al personal del hotel.
- Keys duplicadas de React en las 4 listas de acciones pendientes (`action_key` es el *tipo* de acción y se repite entre reservas; React avisa que puede duplicar u omitir filas al reconciliar). Ahora `reservation_id:action_key`.

### Bugs reales que destaparon los e2e

- **`POST /api/rooms/` → 500** para un hotel con la suscripción v2 pero sin la proyección legacy: `ensure_subscription_seed()` salía temprano sin reconstruirla y `ensure_subscription()` lanzaba "No se pudo inicializar la suscripción del hotel". Ahora la reconstruye desde v2, sólo si falta. Test de regresión en `test_subscription_tiers.py`.
- **Cerrar la caja fallaba en toda base SQLite migrada** (dev local y e2e): `20260725_repair_cash_handoff_schema` hace `return` fuera de PostgreSQL, así que `UNIQUE (hotel_id, id)` en `cash_close_reports` nunca existía, pero `shift_handoffs` (10-sep) crea en todos los dialectos una FK compuesta hacia esas columnas → `foreign key mismatch` en cualquier escritura. Nueva migración `20260917_sqlite_cash_close_parent_key`: en SQLite crea un `UNIQUE INDEX` (suficiente como clave padre, sin reconstruir la tabla; en Postgres es no-op). Un escaneo de **todas** las FKs de una base migrada encontró que era el único caso. `tests/test_sqlite_foreign_key_parent_keys.py` protege toda la clase de bug.

### e2e: de 13 rojos a 0

La línea base de `main` (mis cambios en stash) daba **13 failed / 16 passed** en los mismos specs. Los e2e no corren en CI, así que se pudrieron igual que el test del PWA: roles traducidos (Manager→Gerencia, Housekeeping→Limpieza), tildes ya corregidas en la UI ("Código", "Verificar código"), el motivo de cambio de habitación ahora es un `<select>` de códigos, la tabla de reservas ganó la columna "hora de llegada", y housekeeping ve "Pendientes" a propósito desde el feature de tareas. Todos actualizados sin debilitar la intención de cada assertion.

### Pendiente / fuera de alcance

- La deriva de tokens sigue en el resto de las páginas (2199 `slate-`): esta pasada cubrió el shell y el dashboard, que enmarcan todo. Seguir página por página.
- **Agregar Playwright a CI** (`pr-validation.yml`): es la causa de los 13 rojos.
- `.env.local` fija `VITE_API_URL=http://127.0.0.1:8040/api` mientras se navega en `localhost:5173`: son hosts distintos para cookies, así que en local recargar la página pierde la sesión. Con `VITE_API_URL` sin definir el proxy de Vite resuelve same-origin.

---

## -2. Campaña de auditoría y corrección con ECC — 2026-09-17

`confirmed` para todo lo listado abajo: cada hallazgo se reprodujo y cada corrección se verificó con la suite completa, tipos/lint del frontend, dry-run de migraciones y navegador real (desktop 1280 y móvil 375). No re-verifica las secciones cloud/QA de más abajo.

Punto de partida: `main` en `7c5f229`, árbol limpio. `pytest -q` de base: **2001 passed, 1 failed**. Cierre: **2007 passed, 0 failed** (5 tests nuevos del webhook de Meta).

### Defectos reales encontrados y corregidos

- **`PATCH /api/bookings/{id}` lanzaba `NameError` (500)** en el camino de edición sólo-metadatos: `update_reservation_fields` se usaba sin importarse (`app/api/bookings.py`). Detectado por `ruff --select=F821`; ningún test cubría ese camino.
- **Un mensaje inservible descartaba toda la entrega de Meta.** `POST /api/webhooks/meta/whatsapp` convertía cualquier `WhatsAppCRMError` (un teléfono impar, un id ausente) en 400: el `db.commit()` nunca corría, los mensajes buenos del mismo lote se perdían y Meta reintentaba el mismo lote para siempre. Ahora se registra y se saltea el mensaje (`skipped` en la respuesta) y el resto persiste.
- **`text`/`profile` no-dict en el payload de Meta daban 500** (`AttributeError` sobre `.get`). El resto del handler ya validaba con `isinstance`; faltaba en esos dos puntos.
- **Test bomba de tiempo**: `test_pending_actions_list_is_hotel_scoped_and_sorted_by_priority` usaba fechas literales de 2026-09 y empezó a fallar solo cuando la fecha real pasó la ventana activa (`_ACTIVE_WINDOW_DAYS = 1`). Las fechas quedaron ancladas a `date.today()`.
- **El test del manifest PWA llevaba meses roto**: esperaba `"Hotel Chipre PMS"` / `"Chipre PMS"` cuando el manifest ya dice `Hotels-PMS`. El manifest es el correcto; el test estaba viejo. **Nadie lo veía porque `npm test` no estaba ni en `validate-all` ni en CI** — ahora sí, junto con `npm run typecheck`.
- **401 garantizado en la consola de owner**: `SessionProvider` (inquilino) envuelve toda la app y disparaba `POST /api/auth/session/refresh` al montar también en `/adminpmsmaster`, que se autentica con `MasterAdminSessionProvider` y nunca tiene cookie de inquilino. Verificado en navegador: 2 cargas de la consola = 0 refreshes; `/login` sigue haciendo 1.
- **La consola heredaba el `<title>` del login de inquilino** ("Acceso al sistema"). Ahora declara el suyo, manteniendo `noindex`.
- **Bandeja de WhatsApp**: el cuadro de texto se vaciaba antes de saber si el envío había salido (se perdía lo escrito ante un fallo); un id de responsable no numérico llegaba como `NaN`, que serializa a `null` y **desasignaba la conversación en silencio**; los tres campos no tenían nombre accesible y ningún error de mutación era visible.

### Seguridad

- **Las 13 vulnerabilidades de dependencia cerradas** — `pip-audit -r requirements.txt` termina en `No known vulnerabilities found`: `cryptography` 46.0.7 → 50.0.1 (escape de restricción de nombres en verificación de certificados, blowup exponencial en cadenas, oráculo de descifrado PKCS#7, OpenSSL estático), `protobuf` 5.26.1 → 5.29.6 (dos DoS por recursión) y `pytest` 8.3.3 → 9.0.3 (`/tmp/pytest-of-{user}` en UNIX). Arrastraron `ortools` 9.11.4210 → 9.12.4544 (es quien acotaba protobuf), `pyOpenSSL` 26.4.0, `pytest-asyncio` 0.24.0 → 1.4.0 y `pytest-cov` 5.0.0 → 7.1.0. El salto mayor de `pytest-asyncio` resultó barato: sólo 2 archivos de test usan async y no hay configuración `asyncio_mode` en el repo. `protobuf` y `pyOpenSSL` quedaron pinneados explícitamente para que una resolución nueva no vuelva a una versión vulnerable.
- **La clave de Stripe viajaba en `argv`** (`--api-key=...` en `.mcp.json`), donde cualquier proceso local la lee con `ps`. Movida a `env`; `@stripe/mcp` ya la toma de `STRIPE_SECRET_KEY` (`dist/cli.js`).
- **Servidores MCP sin versión fija** (`@supabase/mcp-server-supabase@latest`, `@stripe/mcp`): una publicación comprometida se ejecutaba sola. Ambos pinneados.
- **Riesgo de escritura cruzada entre hoteles en el ORM**: `Reservation.category/sellable_product/rate_plan/tax_policy` tenían FK compuestas con `hotel_id` sin `viewonly`, así que SQLAlchemy las trataba como escritoras de `reservations.hotel_id` (17 `SAWarning` por test). Nada las asigna; ahora son `viewonly=True`, lo que además impide que una asignación futura reescriba el `hotel_id` de la reserva en silencio.

### Verificado y sin hallazgos

Aislamiento multi-tenant en rutas (sólo auth y demo consultan sin `hotel_id`, correcto), firma y replay de webhooks de pago, rate limiting en auth, headers de seguridad, guardas de `JWT_SECRET` en producción, ausencia de `eval`/`exec`/SQL por concatenación en `app/`, `npm audit --omit=dev` limpio, un solo head de Alembic.

### Higiene

BOM de Windows en `app/api/daily_rates.py` (resto de la migración desde `C:\PROJECTO`), 68 imports muertos, y `.graphify` regenerado (13496 nodos, 77155 aristas, 911 flujos, `portable-check` OK).

### Tamaño del repositorio — `.graphify/graph.json` (2026-09-17)

El push del commit de auditoría disparó `File .graphify/graph.json is 50.49 MB; larger than GitHub's recommended maximum`. Medido antes de tocar nada:

- `.git` pesaba 543 MB, de los cuales 462 MB eran objetos sueltos sin empaquetar. `git gc` lo bajó a **81 MB** sin perder nada.
- Las 189 revisiones de `graph.json` ocupan **26 MB** en el packfile: git deltea ese JSON indentado extraordinariamente bien.
- El archivo crudo pasó de **31 MB (2026-08-20) a 52.9 MB (2026-09-17)**, con los archivos incluidos subiendo sólo 1069 → 1254. El crecimiento es superlineal (aristas, no archivos) y el corte **duro** de GitHub son 100 MB por archivo: faltaban semanas, no años.

Se descartaron con medición, no por intuición:

- **Git LFS**: guarda cada versión entera y sin delta. El historial actual costaría ~9.5 GB de LFS contra los 26 MB del packfile, y el tier gratis son 1 GB.
- **Minificar el JSON**: 52.9 → 45.4 MB. No alcanza y genera diff de archivo completo en cada commit.
- **Comprometerlo comprimido**: un `.gz` no deltea, así que el pack saltaría de 26 MB a ~800 MB.
- **Podar campos redundantes**: `link._src`/`_tgt` duplican `source`/`target` byte a byte en las 77155 aristas (9 MB) y `topology_signature` es una cadena de 10.3 MB derivable de nodos+aristas. Probado: sin `_src`/`_tgt`, `graphify flows build` empieza a reportar `Skipped N CALLS edge(s) without preserved direction` — en un grafo `directed: false` esos campos preservan la dirección. Y `topology_signature` lo lee `readSnapshotMeta()` para decidir si el push a Neo4j/Postgres está al día. Ambos se quedan.

**Solución aplicada**: `graph.json` sale del índice (`git rm --cached` + `.gitignore`). No se reescribió historial, así que las 189 revisiones siguen accesibles con `git show <sha>:.graphify/graph.json`. Se regenera local con el `graphify update` que ya prescribe CLAUDE.md. Siguen versionados `GRAPH_REPORT.md`, `flows.json`, `manifest.json` y `knowledge/_generated/graphify-summary.md` — 1.4 MB en total, y es lo que las reglas de navegación mandan leer. Dos tests en `tests/test_agent_ops_setup.py` fallan si el grafo crudo vuelve al índice o si algún artefacto versionado pasa de 20 MB.

### Deuda conocida que queda

10 `SAWarning` de relaciones `back_populates` en stock/linen/WhatsApp (el arreglo correcto ahí es `overlaps=`, invasivo y sin bug demostrado); `.claude/settings.json` sin bloque `permissions` (decisión de política, no la tomé por el usuario); vulnerabilidades de `esbuild`/`vite` sólo de desarrollo (`npm audit fix --force` instalaría vite 8, breaking); 98 archivos de test siguen con fechas literales — sólo se ancló el que ya fallaba, no hay red que detecte la próxima bomba de tiempo antes de que explote.

---

## -1. Infraestructura cloud (no código) — 2026-08-23

`confirmed` por verificación directa (DNS-over-HTTPS, consolas de Google/Render, bundle desplegado). Detalle completo: `docs/audits/infra-2026-08-23.md`.

Correo corporativo y OAuth de Google quedaron operativos en producción (Workspace, SPF/DKIM/DMARC en raíz y en `auth.`, app OAuth publicada sin revisión humana, login Google end-to-end probado sin duplicados). Riesgos abiertos que sí importan para roadmap/negocio: **Render en plan Free (cold start ~32s)**, **toda la infra colgando de una sola cuenta Gmail personal**, **`RESEND_API_KEY` expuesta pendiente de rotar**, **trial de Workspace vence 2026-09-05** (pago antes o se corta `support@`/`security@`/`billing@`/`privacy@`). Apple Sign In sigue sin auditar (código ya arreglado en `48d46c8`, cuenta developer no auditada).

## 0. Actualización de campaña — 2026-08-21/22 (`confirmed` para código/tests locales; no re-verifica secciones 8-9 de este documento)

Entre el 2026-08-21 y 2026-08-22 se cerraron 16 PRs contra `main` (squash merge, cada uno con suite completa verde antes de mergear). HEAD resultante en esta actualización: `6460092` (más `e130dd5` del fix de test flaky posterior). `pytest -q` completo: **1709 passed, 0 failed, 22 skipped, 12 xfailed, 1 xpassed**. `alembic heads`: un solo head (`20260821_apple_sign_in`). Frontend `lint`/`typecheck`/`build`: limpios.

**Cerrado esta campaña (ver `docs/HOTEL_PMS_MASTER_DEVELOPMENT_SPEC.md` sección 6 para el detalle por ítem y evidencia):**

- TECH-0040 (restore-defaults RBAC), TECH-0070 (export CSV audit), TECH-0071 (TTL sesión master admin) — arrastrados de la campaña anterior, mergeados ahora (#69-#71).
- TECH-0010 — fix de seguridad real: fuga cross-tenant en lookup de pagos (#75). Queda `VERIFY` parcial, no `VERIFIED` — ver matriz de auditoría.
- TECH-0000 — matriz de auditoría formal VERIFIED/VERIFY/TODO/BLOCKED/DEFERRED para los 33 TECH-XXXX, con threat model P0 (#79, `docs/audits/tech-0000-system-audit.md`).
- TECH-0023 — MFA TOTP obligatorio para Master Admin, cerraba un gap real (antes era opcional) (#74).
- TECH-0024 — Sign in with Apple implementado simétrico a Google OIDC (#77). Pendiente humano: credenciales reales de Apple Developer.
- TECH-0090 — gaps de PWA cerrados: manifest/iconos maskable, banner offline explícito (#72).
- TECH-0110 — soft-delete + script de restore drill local (#76). Pendiente humano: restore drill real contra Render/Supabase.
- TECH-0112 — artifacts Docker atados a SHA, validador de release manifest (#73). Queda `BLOCKED`: falta ambiente staging real y branch protection (acción humana).
- TECH-0080/81/82 — NO se resolvió la decisión (sigue en sección 7); se produjo `docs/decisions/tech-0080-warehouse-options.md` con 4 opciones evaluadas y recomendación, para que el Product Lead decida (#78).

**Deuda arquitectónica encontrada por la auditoría TECH-0000 y consolidada donde fue seguro (sin decisión unilateral de arquitectura):**

- JWT bearer + cookie de sesión coexistían como dos mecanismos de auth válidos — **se encontró y cerró un bug de seguridad real**: logout/revoke no invalidaba el JWT bearer emitido en el mismo login (#83). El corte final (retirar JWT vs. mantener híbrido) sigue abierto — `docs/decisions/jwt-cookie-consolidation-plan.md`.
- RBAC por rol (`require_roles`) y por permiso (`require_permission`) coexistían — se migraron 21 rutas sin ambigüedad al mecanismo canónico, con test de regresión que fija el mismo conjunto de roles que antes; 51 rutas quedaron sin tocar por falta de permiso equivalente exacto en el catálogo (#81, `docs/audits/tech-0000-rbac-consolidation.md`).
- Suscripciones legacy y v2 no tenían una única autoridad de escritura — se corrigieron 3 caminos de código que escribían sólo legacy sin sincronizar v2; NO se migraron datos productivos (#82, `docs/decisions/subscription-model-consolidation-plan.md`).
- Audit log fragmentado en 3 tablas (`AuditLog`/`SecurityAuditLog`/`MasterAdminAuditEvent`) — confirmado que es separación deliberada de trust boundary, no duplicado accidental; se formalizó el contrato canónico (#80, `docs/architecture/audit-log-contract.md`).

**No tocado deliberadamente:** TECH-0025, 0091, 0092, 0100, 0101, 0120, 0130 permanecen `DEFERRED` — el spec mismo lo exige (sección 2, regla 5: no crear sistema paralelo; regla 10: nada de despliegue/cuentas cloud/secretos/cutover sin autorización humana explícita). Las decisiones de sección 7 (BigQuery vs. alternativas, sesiones mobile, MFA obligatorio para owners, etc.) siguen esperando al Product Lead; donde fue posible se dejó un documento de propuesta, nunca una decisión tomada por el agente.

**No verificado en esta actualización** (las secciones 8 y 9 de abajo describen el estado cloud/QA del 2026-07-18/23 y NO fueron re-comprobadas ahora — antes de confiar en ellas para un despliegue, re-verificar Vercel/Render/Supabase en vivo): URLs públicas, estado del servicio Render, proyecto Supabase QA, previews aislados. El hallazgo de login lento reportado durante esta sesión fue diagnosticado en vivo (logs de Render) como cold-start del plan Free tras inactividad — no una regresión de código.

---

Auditoría base: commit `bf14bf5` revisado el 2026-07-23 (`confirmed` para inventarios, Graphify portátil, agentes/skills y validaciones del setup). La configuración live de Vercel/Render y las superficies públicas fueron comprobadas de forma read-only; la sesión Supabase está activa, pero el proyecto QA todavía no fue creado. La evidencia de proveedor permanece separada del código versionado.
Fuentes principales: `app/main.py`, `app/config.py`, `app/models/`, `app/api/`, `app/services/`, `frontend/src/router.tsx`, `render.yaml`, `vercel.json`, Alembic y `.graphify/`.
Artefactos reproducibles: [OpenAPI](../_generated/api-surface.md), [rutas frontend](../_generated/frontend-routes.md), [migración head](../_generated/migration-head.md), [superficies cloud](../_generated/cloud-surfaces.md), [resumen Graphify](../_generated/graphify-summary.md).

> Regla de lectura: runtime/configuración y código > tests > Graphify > documentación histórica. Cada frase que no proviene directamente de una fuente canónica se marca abajo.

## 1. Producto y personas

**Estado: `confirmed` para superficie declarada; `needs-verification` para experiencia cloud por rol.**

El producto es un sistema de gestión hotelera multi-hotel: gestiona huéspedes, reservas, asignación y estados de habitaciones, check-in/check-out, caja/movimientos, pagos y links, reportes, inventario/lavandería, configuración, integraciones, analítica e interfaces administrativas. La dirección futura incluye IA asistiva y explicable, sin aplicación silenciosa de acciones críticas.

Las personas de operación son owner, manager, recepción y housekeeping. Owner configura y gobierna el hotel; manager supervisa operación; recepción trabaja con huéspedes/reservas/caja según permisos; housekeeping opera el estado de habitaciones/tareas permitidas. Master-admin es una identidad de plataforma distinta, con superficie `/adminpmsmaster`; no debe confundirse con owner de un hotel.

La cobertura real por persona aún depende de ejecutar el catálogo QA sobre previews aislados. Ninguna de estas personas debe validarse sólo por respuesta API o por inspección de código.

## 2. Arquitectura backend FastAPI

**Estado: `confirmed`.**

`app/main.py` crea una aplicación FastAPI `Hotel PMS — Property Management System` con lifespan que ejecuta `validate_runtime_security()` e `init_db()`. Actualmente registra routers para onboarding, referencia, habitaciones, huéspedes, reservas, waitlist, booking, pagos, check-in, OTA webhooks, configuración, reportes, suscripciones, usuarios, auth, invitaciones, integraciones, payment link tests/links/surcharges, API keys, booking público, WhatsApp, permisos, lavandería, stock, comercial, allocation policy, Gemma, analytics, empresas/documentos, eventos de estado, tarifas, blocks, FX, room blocks, caja, grupos de movimiento y master-admin. Hay además healthcheck y rutas legacy que responden `410` para `/api/connections` y `/api/email`.

El inventario de árbol en este commit contiene **46 archivos en `app/api/`**, **71 en `app/services/`** y **42 módulos en `app/models/`**. El contrato de FastAPI importado declara **278 paths**; el número exacto de operaciones/rutas se regenera en `_generated/api-surface.md`. Por tanto, cualquier nota que enumere rutas manualmente es auxiliar, no contrato.

La separación pretendida es routers/transport → schemas/validación → servicios de dominio → modelos/persistencia → adaptadores de integración. `inferred`: el grado de cumplimiento debe revisarse por módulo antes de un refactor, porque algunas rutas contienen trabajo operativo/contextual y no se hizo auditoría línea por línea aquí.

## 3. Frontend React/Vite y rutas web

**Estado: `confirmed` para declaración de router.**

`frontend/src/App.tsx` entrega el control a `RouterProvider`; `frontend/src/router.tsx` decide la superficie según `isAppHostname()`. En host de aplicación, `/` redirige a dashboard y se exponen analytics, dashboard, huéspedes, reservas, habitaciones, caja, reportes, operaciones (lista de espera, lavandería, stock, tarifas), onboarding y settings. Master-admin queda bajo `/adminpmsmaster` con login, dashboard, billing, email, stripe y audit. En host marketing, las rutas públicas incluyen `/`, `/precios`, `/funciones`, `/pms-hotelero`, `/software-para-hoteles` y `/faq`.

Los flujos auth/públicos incluyen `/login`, `/register-owner`, `/forgot-password`, `/reset-password`, `/verify-email`, `/invitations/accept` y alias `/accept-invitation`. Rutas de app visitadas desde host marketing se redirigen al host de aplicación. Consultar el inventario generado, no esta síntesis, antes de añadir o retirar una ruta.

La superficie UI tiene **114 archivos TypeScript/TSX** en `frontend/src/` en el inventario base. `needs-verification`: estados visuales, responsive, a11y y autorización observable de cada ruta deben pasar por navegador con la persona correcta en cada cambio.

## 4. Datos, modelos, multi-tenancy y migraciones

**Estado: `confirmed` para presencia de modelos/alcance; `needs-verification` para auditoría exhaustiva de cada query.**

Los módulos incluyen usuarios, hotel configuration/membership, guests, reservations, room/room blocks, payments/transactions/refunds, cash register, rate/daily rate, companies/documentos, integrations/connections, OTAs, stock/laundry, subscriptions, audit/security logs, analítica, vouchers, waitlist, AI assistant y acciones pendientes. El modelo usa `hotel_id` repetidamente, con foreign keys, índices y constraints en áreas críticas; reservas consultan servicios usando `context.hotel_id`.

Esto apunta a un aislamiento tenant por hotel (`confirmed` para los flujos inspeccionados). El requisito para cambios nuevos es no confiar en el cliente: cargar el contexto autenticado, filtrar/validar `hotel_id` y probar denegación cross-hotel. La migración vigente debe verse en `alembic heads` mediante [migration-head.md](../_generated/migration-head.md); nunca asumir que una migración histórica es el head.

## 5. Auth, autorización y master-admin

**Estado: `confirmed` para rutas y configuración revisadas.**

`app/api/auth.py` declara registro, login, verificación de email y recuperación/reset de contraseña. Las contraseñas se hashean y verifican desde `app.services.security`; el acceso se entrega mediante JWT. `app/config.py` define algoritmo HS256, expiración configurada y validación en producción de un `JWT_SECRET` no trivial.

Master-admin se autentica con email, password y PIN y mantiene seguridad separada en `app/master_admin/`: cookie de sesión, TTL, límite de intentos y lockout. Las variables para bootstrap son `MASTER_ADMIN_EMAIL`, `MASTER_ADMIN_PASSWORD` y `MASTER_ADMIN_PIN`; los valores reales sólo van en Render/entorno QA, nunca Git. La configuración puede tener valores de desarrollo que runtime rechaza en producción; no se debe tratar una default de código como configuración deployable segura.

`needs-verification`: matriz completa de autorización por endpoint y rol. Se debe ejecutar como prueba de denegación cuando se cambie permisos, pertenencias, API keys o superficies master-admin.

## 6. Pagos, caja e integraciones

**Estado: `confirmed` para superficies registradas; `needs-verification` para proveedores reales.**

El backend registra pagos, payment links, surcharges, tests de link, transactions/refunds, cash register y grupos/movimientos. Los modelos de transacción incluyen una estrategia de idempotencia por hotel/reserva/clave. Existen adaptadores/superficies para integraciones, OTAs, OTA webhooks, WhatsApp y email.

El runtime preview ahora falla al iniciar salvo que correo use provider `null`, conexiones estén deshabilitadas, PayPal esté en sandbox e IA/Gemma estén explícitamente apagadas. El verificador rechaza credenciales Resend/Gmail/Mercado Pago/PayPal/OTA/IA/Gemma y cualquier worker/cron hermano en el entorno Render QA; Stripe también se bloquea antes de llamar a red cuando `CONNECTIONS_ENABLED=false`. En esta baseline no se crean ni completan pagos reales, no se envían correos, no se disparan webhooks ni se ejecutan operaciones OTA. Esas ramas se verifican por contrato/local adapter y se excluyen explícitamente de la evidencia cloud.

## 7. IA Gemma y analítica

**Estado: `confirmed` para presencia; `needs-verification` para ejecución habilitada.**

`app/main.py` registra `gemma_chat` y `analytics`. El blueprint actual declara `GEMMA_ENABLED=false` y `AI_ENABLED=false`, por lo que no se presume inferencia cloud habilitada. La IA se diseña como capa de recomendación: debe ser configurable, auditable, con trazabilidad de fuente/hipótesis, captura de aceptación/rechazo y separación de datos transaccionales confirmados.

Analítica debe validar permisos, rango temporal, filtros, zona horaria, definición de métricas, vacíos y errores. Un gráfico no está validado por renderizar: debe reconciliarse con su fuente y tener evidencia de la persona habilitada.

## 8. Despliegue y URLs

**Estado: `confirmed` para los tres dominios y configuración pública comprobados el 2026-07-18; no es sustituto de prueba de negocio.**

- `https://app.hotels-pms.com` respondió HTTP 200 y se identifica como frontend Vercel.
- `https://hotels-pms.com` respondió HTTP 200 y se identifica como frontend Vercel.
- `https://api.hotels-pms.com/health` respondió HTTP 200 con `{"status":"ok","system":"Hotel PMS v1.0.0"}` en la comprobación más reciente. Render confirma que el plan actual es Free y puede dormir tras inactividad; vigilar ese cold start antes del preview QA.

Vercel tiene una integración autenticada para el proyecto `hotel-chipre-pms` y la producción pública responde. `VITE_API_URL=https://api.hotels-pms.com/api` queda deliberadamente sólo en Production: un Preview sin backend aislado no es QA válido. La integración histórica de checks y el proyecto consultado no se deben dar por reconciliados hasta generar un manifiesto de preview que pruebe el par frontend/backend exacto. CORS preflight de la API confirmó explícitamente `https://app.hotels-pms.com`.

Render tiene ahora healthcheck `/health` y su deploy live pasó esa comprobación. `needs-verification`: el servicio real fue creado/configurado fuera del Blueprint y su start command observado ejecuta Uvicorn sin `alembic upgrade head`; por lo tanto `render.yaml` es diseño declarativo, no prueba de que migraciones se ejecuten en producción. El plan Free también deja deshabilitado el campo Pre-Deploy en la UI observada, por lo que el servicio QA necesita una estrategia compatible (o un plan que permita el bootstrap) antes de activar el gate. Los logs revelaron labels de enum PostgreSQL incompatibles con los valores de los modelos en los dominios OTA/allocation; la corrección está en el PR draft [#24] y requiere PostgreSQL aislado antes de merge/deploy. Se rotó el hook de deploy observado; su valor nunca se registra aquí.

El repositorio ya alinea `.env.example`, `.env.render`, defaults frontend, SEO/sitemap y `render.yaml` con `hotels-pms.com`. Sus `DATABASE_URL`, URLs de CORS/frontend/base, email y secretos de integración son `sync:false`, por lo que se deben confirmar manualmente en los proveedores sin exponer valores. `vercel.json` declara build Vite, output frontend y rewrite SPA. Hay documentación histórica que puede citar nombres de dominio/hosts distintos; se marca `historical` y no debe emplearse para configuración.

## 9. Previews y QA cloud requeridos

**Estado: `needs-verification` — setup local y workflow confiable están preparados; el primer ciclo cloud aislado todavía no existe.**

En la ejecución más reciente del PR #25 (`code_sha` `34ae6e9`), frontend y el contrato estático pasaron; `Supabase Preview` quedó omitido por diseño. `trusted-base-evidence` y `release-gate` bloquearon con el mensaje correcto **“exactly one QA summary candidate is required; found 0”**: el gate ya corre contra la base actual y está esperando evidencia cloud real, no un fixture. Se corrigió además el runtime del `release-gate` para instalar `requirements-qa-trusted.txt` antes de importar la validación criptográfica.

Vercel genera previews Git por rama, pero el `VITE_API_URL` de Production se dejó deliberadamente fuera de Preview: una preview sin backend aislado no es una preview QA válida ni debe tocar la API compartida. Render PR Previews permanece `Off`; cuando se habilite debe ser `Manual`, nunca automático, y sólo después de comprobar una Supabase Branch (o segunda DB QA aislada).

`needs-verification`: los checks de PR actuales reportan Vercel bajo el espacio `maximo-paulos-projects`, mientras la configuración Production verificada vive en `maximopaulos1-4687s-projects`. Hasta reconciliar esa integración/proyecto, ninguna URL de preview Vercel se acepta como par válido del frontend de producción.

Supabase mostró que las branches persistentes requieren upgrade. La sesión actual está en la pantalla de creación del proyecto `hotel-chipre-pms-qa`, con organización `HPMS`, región São Paulo y Data API desactivada; todavía falta enviar la creación y registrar sólo su referencia no sensible. El fallback aprobado es un segundo proyecto gratuito QA sin datos productivos y lease serializado; usar la base principal queda prohibido. El workflow confiable adquiere un lease aleatorio, verifica proveedores, hace bootstrap con capacidad Ed25519 efímera, elimina esa capacidad, vuelve a verificar deployment/URLs, comprueba health/CORS/bundle y libera el lease aun ante fallos. Cuando Supabase Branches esté disponible se migra a una base por target.

El gate permanente exige: Vercel preview por rama, Render backend QA con `/health`, base QA independiente y un manifiesto que demuestre qué frontend apunta a qué backend. `VITE_API_URL`, CORS, `FRONTEND_URL`, cinco personas y política de migración quedan ligados por proveedor/fingerprint. El token nunca se publica como artefacto ni cruza workflows. La clave pública de atestación humana ya existe en `qa/trust/`; las dos claves privadas distintas permanecen sólo bajo `artifacts/qa/keys/` ignorado y con permisos `0600`.

El bootstrap de owner/hotel sintéticos y personas manager/recepción/housekeeping requiere verificación única manual por correo dedicado. Master-admin QA debe ser identidad distinta configurada en Render. Credenciales/sesiones locales permanecen en `.env.qa.local`/directorios ignorados.

Cada fila de la regresión registra persona, URL de preview, precondición, acción humana, esperado, observado, artefacto/hash y `code_sha`. La suite completa incluye marketing, auth, onboarding, operaciones, analytics, settings, caja, master-admin y rutas públicas por API key. Fallo, superficie inaccesible o evidencia incompleta bloquea el cierre.

## 10. Tests y validación local

**Estado: `confirmed` para la ejecución local registrada hasta el 2026-07-23; la QA cloud sigue `needs-verification`.**

El repositorio contiene tests backend y frontend/e2e; los comandos concretos dependen del área. En esta auditoría actual: `pytest` terminó con **1155 passed, 17 skipped, 12 xfailed y 1 xpassed**; lint, typecheck y build frontend pasaron; `alembic upgrade head` llegó al head en una SQLite virgen; setup de vault/agentes y enlaces pasaron. Playwright local tiene baseline previa verde y debe repetirse si cambia la UI. El build conserva una advertencia no bloqueante por chunk JS de aproximadamente 755 kB.

No se debe confundir “configuración creada” con “preview probado”: mientras falten las credenciales/URLs aisladas, la validación cloud es un bloqueo documentado, no un éxito parcial.

## 11. Graphify: estado técnico e impacto

**Estado: `confirmed` para extracción AST actual; descripciones/labels semánticos se mantienen deliberadamente pendientes.**

La actualización final AST, construida desde `bf14bf5`, produjo **6.251 nodos, 19.636 aristas y 503 flujos ejecutables**. El reporte estructural y el resumen CLI muestran conteos de comunidades distintos (275 frente a 290); por eso la comunidad se usa sólo como orientación, no como KPI. Sus god nodes continúan orientando sobre `ReservationStatusEnum`, `Reservation`, `HotelConfiguration`, `Room` y `Guest`; revisar el resumen generado antes de inferir impacto concreto. `graphify portable-check` pasó después de normalizar cuatro labels de rutas y un artefacto de flujo. La única extracción omitida es el script PowerShell de smoke porque este runtime no tiene `tree-sitter-powershell`. `graphify check-update` anuncia sólo descripciones/labels semánticos pendientes porque esta política ejecuta explícitamente `--no-description --no-label`; la extracción AST está fresca respecto de `bf14bf5`.

Cuando cambie código, se ejecuta `graphify update . --scope all --no-description --no-label`, `graphify flows build`, `.venv/bin/python scripts/agent_ops/normalize_graphify_portability.py`, `graphify portable-check` y `graphify check-update`. Usar `minimal-context`, `affected-flows` y `query`; no exportar el grafo completo como notas Obsidian.

## 12. Brechas entre código, documentación y operación

**Estado: `confirmed` para las brechas observadas.**

1. Existían referencias heredadas a un layout Graphify previo y a un vault Windows, mientras el grafo actual vive en `.graphify/` y el vault aprobado es `knowledge/`.
2. Se corrigieron los defaults versionados que aún usaban `hoteles-pms.com`; las variables privadas de Render/Vercel deben verificarse contra el dominio canónico antes de QA.
3. El blueprint Render existente configura servicio compartido, no evidencia de preview aislado ni Supabase Branch por PR.
4. La disponibilidad HTTP actual no prueba login, permisos, formularios, botones ni recorridos de las cinco personas.
5. Los E2E locales usan ahora el Python del `.venv`, backend `127.0.0.1:8040`, SQLite aislado y master-admin sintético; los previews deben declarar de forma equivalente `VITE_API_URL`/`E2E_API_URL` sin reutilizar esos datos locales.
6. El servicio Render live no ejecuta todavía las migraciones declaradas por el Blueprint y reportó incompatibilidad de labels enum OTA/allocation. El PR #24 lo corrige de modo reversible, pero no debe promoverse sin una base PostgreSQL aislada para validar upgrade/downgrade.

## 13. Prioridades inmediatas

1. Crear y registrar el segundo proyecto Supabase QA aislado; no usar la base principal.
2. Crear/configurar el servicio Render QA y resolver la limitación Pre-Deploy del plan Free sin degradar el aislamiento; dejar los secrets del GitHub Environment `preview-qa` completos.
3. Reconciliar Vercel Preview con el backend QA exacto y producir el manifiesto de paridad frontend/backend.
4. Ejecutar el ciclo confiable contra PostgreSQL real, validar el PR #24 de enums y completar el bootstrap de owner, manager, recepción, housekeeping y master-admin sintéticos.
5. Ejecutar la regresión cloud humana completa, firmar evidencia posterior al último `code_sha`, revisar seguridad y recién entonces cerrar el PR #25 y activar protección permanente de `main`.
