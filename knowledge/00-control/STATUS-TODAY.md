# Estado exhaustivo del sistema — Hotel Chipre PMS

Auditoría base: commit `bc938cf` (`confirmed` para inventarios estáticos revisados el 2026-07-18); el setup de esta rama se valida sobre el worktree posterior. La configuración live de Vercel/Render se volvió a comprobar el 2026-07-18 y se documenta abajo como evidencia de proveedor, separada del código versionado.
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

En QA cloud se permite crear un payment link real si el sistema lo requiere, pero está prohibido completarlo. No se envían correos, no se disparan webhooks y no se ejecutan operaciones OTA reales. Esas ramas se verifican mediante test de contrato, adapter o entorno local controlado, con exclusión explícita en evidencia QA.

## 7. IA Gemma y analítica

**Estado: `confirmed` para presencia; `needs-verification` para ejecución habilitada.**

`app/main.py` registra `gemma_chat` y `analytics`. El blueprint actual declara `GEMMA_ENABLED=false` y `AI_ENABLED=false`, por lo que no se presume inferencia cloud habilitada. La IA se diseña como capa de recomendación: debe ser configurable, auditable, con trazabilidad de fuente/hipótesis, captura de aceptación/rechazo y separación de datos transaccionales confirmados.

Analítica debe validar permisos, rango temporal, filtros, zona horaria, definición de métricas, vacíos y errores. Un gráfico no está validado por renderizar: debe reconciliarse con su fuente y tener evidencia de la persona habilitada.

## 8. Despliegue y URLs

**Estado: `confirmed` para los tres dominios y configuración pública comprobados el 2026-07-18; no es sustituto de prueba de negocio.**

- `https://app.hotels-pms.com` respondió HTTP 200 y se identifica como frontend Vercel.
- `https://hotels-pms.com` respondió HTTP 200 y se identifica como frontend Vercel.
- `https://api.hotels-pms.com/health` agotó un primer intento de 20 s, pero un reintento con 60 s devolvió HTTP 200 y `{"status":"ok","system":"Hotel PMS v1.0.0"}`. Render confirma que el plan actual es Free y puede dormir tras inactividad; vigilar ese cold start antes del preview QA.

Vercel tiene `VITE_API_URL=https://api.hotels-pms.com/api` **sólo para Production** y se redeployó la versión de `main` `50abb05`; la deployment quedó `Ready` y el asset publicado contiene la URL canónica. Antes apuntaba a un proveedor histórico y aplicaba a todos los entornos; no volver a propagar Production a Preview. CORS preflight de la API confirmó explícitamente `https://app.hotels-pms.com`.

Render tiene ahora healthcheck `/health` y su deploy live pasó esa comprobación. `needs-verification`: el servicio real fue creado/configurado fuera del Blueprint y su start command observado ejecuta Uvicorn sin `alembic upgrade head`; por lo tanto `render.yaml` es diseño declarativo, no prueba de que migraciones se ejecuten en producción. Los logs revelaron labels de enum PostgreSQL incompatibles con los valores de los modelos en los dominios OTA/allocation. La corrección está en el PR draft [#24](https://github.com/Maximo-Paulos/Hotel-Chipre-PMS/pull/24); requiere PostgreSQL aislado antes de merge/deploy. Se rotó el hook de deploy de Render; su valor nunca se registra aquí.

El repositorio ya alinea `.env.example`, `.env.render`, defaults frontend, SEO/sitemap y `render.yaml` con `hotels-pms.com`. Sus `DATABASE_URL`, URLs de CORS/frontend/base, email y secretos de integración son `sync:false`, por lo que se deben confirmar manualmente en los proveedores sin exponer valores. `vercel.json` declara build Vite, output frontend y rewrite SPA. Hay documentación histórica que puede citar nombres de dominio/hosts distintos; se marca `historical` y no debe emplearse para configuración.

## 9. Previews y QA cloud requeridos

**Estado: `needs-verification` — diseño documentado, aprovisionamiento externo pendiente.**

Vercel genera previews Git por rama, pero el `VITE_API_URL` de Production se dejó deliberadamente fuera de Preview: una preview sin backend aislado no es una preview QA válida ni debe tocar la API compartida. Render PR Previews permanece `Off`; cuando se habilite debe ser `Manual`, nunca automático, y sólo después de comprobar una Supabase Branch (o segunda DB QA aislada).

El gate permanente exige: Vercel preview por rama, Render preview backend con `/health`, Supabase Branch por PR sin datos reales y un manifiesto que demuestre qué frontend apunta a qué backend. El frontend debe compilar con `VITE_API_URL` de ese backend; Render debe recibir `DATABASE_URL`, secretos QA, CORS y `FRONTEND_URL` propios. Si no hay Supabase Branches, el diseño se detiene hasta disponer de una segunda DB QA aislada; usar una DB compartida queda prohibido.

El bootstrap de owner/hotel sintéticos y personas manager/recepción/housekeeping requiere verificación única manual por correo dedicado. Master-admin QA debe ser identidad distinta configurada en Render. Credenciales/sesiones locales permanecen en `.env.qa.local`/directorios ignorados.

Cada fila de la regresión registra persona, URL de preview, precondición, acción humana, esperado, observado, artefacto/hash y `code_sha`. La suite completa incluye marketing, auth, onboarding, operaciones, analytics, settings, caja, master-admin y rutas públicas por API key. Fallo, superficie inaccesible o evidencia incompleta bloquea el cierre.

## 10. Tests y validación local

**Estado: `confirmed` para la ejecución local del setup el 2026-07-18; la QA cloud sigue `needs-verification`.**

El repositorio contiene tests backend y frontend/e2e; los comandos concretos dependen del área. Para modificaciones de producto la puerta requiere tests focales, pytest backend, lint/typecheck/build frontend, migración sobre DB limpia y Playwright local antes del preview. En esta rama: `pytest` terminó con **758 passed, 16 skipped, 12 xfailed y 1 xpassed**; lint, typecheck y build frontend pasaron; Playwright pasó **18/18** contra SQLite aislado. Este setup añade validadores propios para paridad de agentes/skills, enlaces del vault, Graphify y esquema de evidencia.

No se debe confundir “configuración creada” con “preview probado”: mientras falten las credenciales/URLs aisladas, la validación cloud es un bloqueo documentado, no un éxito parcial.

## 11. Graphify: estado técnico e impacto

**Estado: `confirmed` para extracción AST actual; descripciones/labels semánticos se mantienen deliberadamente pendientes.**

La actualización final AST produjo **5.528 nodos, 17.098 aristas y 289 comunidades**, más **478 flujos ejecutables**. Sus god nodes continúan orientando sobre `ReservationStatusEnum`, `Reservation`, `HotelConfiguration`, `Base` y `Room`; revisar el resumen generado antes de inferir impacto concreto. `graphify portable-check .graphify` pasó. `graphify check-update .` anuncia descripciones/labels pendientes porque esta política ejecuta explícitamente `--no-description --no-label`; no indica que la extracción AST esté vieja.

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

1. Validar en PostgreSQL aislado el PR #24 de normalización de enums y, si pasa, hacer merge/promotion sin saltar la revisión de seguridad.
2. Aprovisionar Supabase Branches o una segunda DB QA aislada; recién entonces habilitar Render Preview manual y conectar el Vercel Preview a su backend exacto.
3. Realizar bootstrap manual de las cinco identidades QA y guardar sólo metadatos no sensibles.
4. Ejecutar baseline cloud completo y registrar evidencia por persona antes de activar el gate de merge funcional.
5. Corregir cada discrepancia que revele la baseline, empezando por auth/tenancy, reservas/pagos y UX operativa.
