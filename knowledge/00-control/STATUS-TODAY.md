# Estado exhaustivo del sistema — Hotel Chipre PMS

## -5. Pendientes cerrados: e2e en CI, specs rescatados y tres bugs reales — 2026-09-18

`confirmed`: verificado sobre el árbol final, rebaseado encima del merge del feature de Codex (`9af1f73`):
- tipos, lint, 17 tests de nodo y build;
- suite backend: 2055 passed, 0 failed;
- **e2e completo: 99 passed, 0 failed**, con 2 skipped que dependen de variables de entorno (`REALTIME_E2E` y `E2E_GOOGLE_CLIENT_ID`), en Chromium, Chromium móvil y ruteo de previews;
- capturas y pantallas tocadas revisadas a 1440 y 390 px, sin desborde horizontal.

- **Playwright en CI.** Nuevo job `e2e` en `pr-validation.yml`: journeys en Chromium, smoke responsive en Chromium móvil y ruteo de previews, con el reporte como artefacto si falla. Corre en PRs y en pushes a ramas que no son `main`, igual que el resto de `pr-validation`. Un push directo a `main` no lo dispara: `main` sigue sin protección, que es la brecha de fondo.
- **Seis specs rotos, arreglados sin debilitar lo que verifican:**
  - `guest-pagination` y `role-journey` hacían el login por API con `page.request`, que comparte cookies con el navegador. Ese login pisaba la sesión de la UI, y el siguiente `goto` fallaba el refresh por CSRF. Ahora usan el fixture `request`, que está aislado. En `role-journey` el cambio de usuario cierra antes la sesión del dueño; el test sólo pasaba porque esa sesión estaba rota.
  - `reservation-drawer-global` creaba la reserva con fecha de hace unos 14 años, pero el dashboard muestra llegadas reales: desde hoy, las cinco más próximas. Ahora la llegada es mañana, con habitación auto-asignada, y el test la cancela al final.
  - `master_admin`: el panel exige TOTP (TECH-0023) y el test nunca lo contemplaba. El seed E2E enrola al master con un secreto de prueba fijo, sólo sobre `_e2e.db`, y el test calcula el código RFC 6238 (verificado contra `pyotp`) respetando el anti-replay. El enrolamiento en sí lo cubre `tests/test_master_admin_panel.py`.
  - `promotions-builder` mockea todo el backend pero no mockeaba `/api/auth/session/refresh`. El token vive en memoria, así que el `goto` volvía al login.
  - `integrations-status` y `reception-checkin-checkout` destaparon bugs reales (1 y 2).
- **Bugs reales:**
  1. **Conexiones.** Con las conexiones deshabilitadas en el entorno, la página decía "Verifica la sesión" (la sesión nunca era la causa), borraba el título y reintentaba el 403 tres veces (unos 7 s de "Cargando"). Ahora el título se muestra siempre, hay un aviso claro "deshabilitadas en este entorno", "Reintentar" para errores reales y no se reintentan los 4xx. El mensaje de Gmail ya no muestra nombres de variables de entorno al personal.
  2. **Check-in.** Después del check-in parcial, el drawer seguía pidiendo los datos del huésped que se acababan de guardar. Las mutaciones de check-in y de acompañantes no invalidaban el dominio `guests`, donde vive `guest-checkin-validation`. Se corrige con `refreshReservationGuestState`.
  3. **Formulario de reserva.** "Cancelar" y "Cerrar" no hacían nada, sin ningún aviso, mientras había un cobro, un comprobante o una solicitud de pago en curso. Ahora se deshabilitan durante la operación. El e2e sólo lo veía con la base cargada, cuando el refresco tardaba más.
- **La primera corrida del job en GitHub Actions (runner más lento) destapó dos bugs más, de sesión:**
  4. **Fin del onboarding.** Al terminar el onboarding, la app va al dashboard apenas el estado dice "completo". La mutación además repetía `navigate("/dashboard")` cuando terminaban sus refetch lentos. Un `navigate` de React Router sigue funcionando desde un componente desmontado, así que un usuario que ya se había ido (en CI: deslogueado y pidiendo recuperar la contraseña) era llevado al dashboard y rebotado a `/login`. Ese fallback ahora sólo actúa si el usuario sigue en `/onboarding`.
  5. **Logout con requests en vuelo.** Una request enviada antes de un logout voluntario que volvía 401 intentaba refrescar la sesión y, al fallar, redirigía a `/login?expired=1` ("sesión expirada") desde cualquier página. Si el refresh llegaba antes de que el servidor procesara el logout, que es best-effort, podía volver a loguear al usuario. Ahora sólo se refresca, o se trata el 401 como vencimiento, si esa sesión sigue siendo la actual.

  `auth-onboarding-journey` retiene 3 s un refetch del cierre del onboarding, así que la carrera ocurre en cada corrida. Sin el primer fix falla con `/login` (el síntoma de CI) y sin el segundo con `/login?expired=1`.
  El mismo runner mostró otras dos cosas:
  - `payment-journey` avanzaba a la devolución antes de que terminara la aprobación del comprobante, y el aviso tardío de la aprobación tapaba el de la devolución. Ahora espera la confirmación, como un operador.
  - `reservation-charge-journey` tenía su propia copia del helper de navegación con la misma carrera de permisos. Ahora `navigateFromShell` es uno solo, en `e2e/support/sidebar.ts`, y decide escritorio o móvil por el ancho del viewport.
- **Carreras de test.** El helper que abre los grupos colapsados del sidebar decidía antes de que cargaran los permisos; estaba duplicado en cinco specs. Queda uno solo en `e2e/support/sidebar.ts`, que primero espera el link. En `role-journey` además evita que "no ve rutas prohibidas" pase sobre un menú todavía vacío.
- Usuarios: el eyebrow "Settings" pasa a "Configuración". Resuelve la excepción de la sección -4 y puede dar un conflicto de una línea al mergear la rama de Codex.
- Capturas de la landing regeneradas sobre el demo de Bariloche, con fechas de hoy. `marketing-shots.mjs` tenía por defecto un usuario que el seed demo no crea.
- **Lo que las capturas mostraban y no iba a la landing así:**
  - Reservas y la ficha mostraban códigos internos al personal: "Estado: checked_out · Origen: direct · Cobro: hotel_collect · Settlement: not_applicable", además de "Próxima acción sugerida: collect_from_guest". Ahora dicen "Estado: Check-out · Origen: Directo · Cobro: Cobra el hotel · Liquidación: No aplica". Hay mapas en `page.enums` (es/en) con todos los valores que emite el backend, y un valor nuevo cae en el código en vez de quedar vacío.
  - El dashboard mostraba "critical" y "direct" crudos.
  - En "Próximas reservas", los códigos se partían ("CHP-" / "2602"), igual que las fechas y la pastilla "Pago completo".
  - Faltaban plurales: decía "1 salidas hoy", "1 llegadas" y "1 críticas".
  - Usuarios tenía su propio mapa de roles en inglés ("Manager", "Housekeeping", "Co-owner"). Ahora reutiliza el del header ("Gerencia", "Limpieza", "Copropietario").
  - Analítica renderiza los payloads de forma genérica y mostraba las claves tal cual:
    - columnas en inglés ("CHANNEL CODE", "RESERVATIONS COUNT");
    - códigos ("walk_in", "website_direct", "leisure");
    - montos sin formato ("678000.00");
    - "5.56%" y "1 filas".
    Ahora hay un diccionario de claves y de códigos de canal, segmento y resultado; las claves `*_ars`/`*_usd` se formatean como moneda y los porcentajes en es-AR. Lo que no está mapeado se sigue mostrando humanizado. En el backend, dos etiquetas de tarjeta estaban en inglés: "Physical room nights" pasa a "Noches-habitación disponibles" y "Pickup 30d" a "Pickup 30 días".
- Código muerto detectado y no tocado: `CompaniesSettingsPage` en `AnalyticsPages.tsx` no se importa en ningún lado; la ruta usa `CompaniesPage`.

---

## -4. Sistema visual homogéneo en todas las páginas — 2026-09-18

`confirmed`: tipos, lint, 17 tests de nodo, build, suite backend y la suite e2e completa de Playwright sobre el árbol final (ver el commit). La pasada anterior (-3) cubrió el marco; esta cubre las ~80 pantallas restantes.

- **Radios y sombras desde la config, no página por página.** Las páginas usaban la escala estándar de Tailwind y repartían dos funciones en seis radios (`rounded-lg` ×703, `-xl` ×145, `-2xl` ×90, `-3xl` ×19, `-md` ×18, `rounded` ×45) y sombras negras genéricas (`shadow-sm` ×196). `tailwind.config.cjs` remapea esa escala sobre los tres radios del sistema (chip/control/panel) y las tres elevaciones (raise/float/deep, teñidas con el tono `ink`). Cada clase existente, incluida la del marketing, cae en un valor del sistema, y también el código futuro.
- **Un solo acento.** El azul funcionaba como segundo acento (celda "hoy", selección de la grilla de tarifas, paneles de cotización) y los botones rellenos `emerald-600` eran un verde casi idéntico al teal de marca; ambos pasan a `brand`. Los segmentos seleccionados usaban azul y `slate-900` *en la misma página*; ahora todos son `brand-600`. `sky`/`amber`/`rose`/`emerald` claros siguen como semántica de estado (info/atención/error/éxito).
- **Títulos**: 30 `h1` con 8 variantes pasan a un único estilo de título de página. Analítica abría con el único bloque oscuro de la app (gradiente `slate-950 → emerald-950`) y el Asistente con un gradiente ámbar, un orbe `blur-3xl` y pastillas que repetían el id interno del hotel; los dos usan ahora la cabecera estándar.
- **Números y titulares**: todas las tablas con cifras tabulares y los `h1–h3` con `text-wrap: balance`, como regla base.
- **Violeta, el tercer acento**: botones ("Cargar reserva de OTA", el primario del modal de OTA), paneles de tarifa manual y chips decorativos pasan a `brand`. Queda sólo el chip de estado "reembolsado" de Pruebas, que es parte de una paleta semántica de estados.
- **Analítica en español y con tarjetas legibles**: filtros, título y eyebrow estaban en inglés ("Date from", "Currency", "Compare YoY"). Las tarjetas titulaban con el código interno (`HOME_REVENUE_GROSS`) y **todas salían en rosa de alerta por un bug**: la API manda `value_pct: null` en las tarjetas de dinero, `Number(null)` es 0 y 0 < 50. Ahora se titulan con el nombre, `null` no cuenta como número y sólo un porcentaje real bajo 50 se marca.
- **Grillas**: las filas de grupo de Planilla y del calendario de tarifas eran bandas `slate-900`; pasan a encabezado de sección claro (con `InfoTip` en su variante para fondo claro).
- **Excepción deliberada**: el eyebrow "Settings" de Usuarios queda en inglés porque esa página la reescribe la rama de Codex; cambiarlo acá sólo le generaría un conflicto de merge.
- **Ortografía**: más de 100 cadenas visibles sin tilde corregidas con un diccionario de palabras sin ambigüedad (las que dependen de la oración —más/mas, está/esta, pagó/pago, validá/valida— quedaron fuera a propósito; un "se válida" que el reemplazo automático introdujo se revirtió a mano). Las aserciones e2e que buscaban el texto viejo se actualizaron sólo donde la app cambió, verificándolo contra el elemento exacto.

### Incidente: dos sesiones en el mismo directorio

A las 23:38 del 17-sep otra sesión (Codex) creó `feature/google-onboarding-staff-aliases` **en este mismo working tree** y a las 01:26 commiteó ahí `f45e8eb`: su feature (onboarding con Google, alias de staff, migración `20260918_member_alias_auth`) **mezclado con todo el trabajo sin commitear de esta pasada y la anterior**. Por pedido del dueño se desplegó sólo este trabajo: se armó en un worktree aislado desde `main`, excluyendo los 52 archivos del feature, reaplicando a mano los dos archivos mixtos (`SettingsUsersPage`, `SettingsSecurityPage`: sólo la línea del título) y verificando que el diff no contiene ningún rastro del feature. Cuando esa rama se mergee, sus hunks de UI son idénticos a los de `main` y no deberían conflictuar. **Regla**: una sesión por working tree; los agentes paralelos trabajan en `git worktree` propios.

---

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
