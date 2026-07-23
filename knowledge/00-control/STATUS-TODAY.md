# Estado exhaustivo del sistema — Hotel Chipre PMS

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
