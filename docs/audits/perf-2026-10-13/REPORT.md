# Auditoría de arquitectura, eficiencia y costo — Hotel Chipre PMS

- **code_sha auditado:** `ef0aa41f0efd7cfdebf42918700add640adbcbf6` (rama `claude/modest-goldberg-5dd5am`, sin cambios de código de producto)
- **Fecha:** 2026-10-13
- **Estado de certeza:** cada cifra de este documento fue **medida** en esta sesión (`confirmed`) salvo donde dice `inferred` o `needs-verification`. Los scripts para repetir todo están en [`scripts/`](scripts/); el inventario archivo por archivo, en [`INVENTARIO.md`](INVENTARIO.md); las notas de la lectura completa, en [`LECTURA-COMPLETA.md`](LECTURA-COMPLETA.md); el cambio concreto para cada hallazgo (con código probado), en [`SOLUCIONES.md`](SOLUCIONES.md).
- **Alcance leído:** **todo**: 375 archivos Python de `app/` (101.418 LOC, 2.866 funciones analizadas por AST; notas por archivo en [`LECTURA-COMPLETA.md`](LECTURA-COMPLETA.md)), los 239 archivos de `frontend/src` (~57.000 líneas, siete partes en [`frontend-notes/`](frontend-notes/)), las 173 migraciones Alembic (dos mitades: [A](migration-notes-a.md), [B](migration-notes-b.md)), y los 119 archivos de CI/CD, despliegue, scripts, QA y agent-ops ([`ops-notes.md`](ops-notes.md)): `render.yaml`, `vercel.json`, Dockerfiles, `docker-compose.yml`, 6 workflows y la documentación de decisiones. Además de la lectura, se **ejecutó** la app (los 171 `GET` sin parámetros, carga mixta de 5–20 usuarios, PostgreSQL 16 con 195.000 reservas) y se reprodujeron los hallazgos marcados ✔. Las notas de lectura de frontend, migraciones y ops las escribió un lector por parte y **un segundo lector comprobó contra el código 262 de sus afirmaciones principales: 198 se confirmaron tal cual y 64 se corrigieron** (casi todas, de línea, de cifra o de alcance; ninguna cambió una conclusión de fondo salvo las indicadas en § 0.3). Además comprobé yo los puntos de mayor impacto (`frontend-notes/verificacion-manual.md`). Las correcciones están incorporadas; lo que no se pudo verificar está marcado ◐/○.

---

## 0. Resumen ejecutivo

**La conclusión principal: el lenguaje no es el problema. Python/FastAPI alcanza para el piloto.** Lo que hoy consume recursos es de *diseño*, no de velocidad del lenguaje:

| # | Hallazgo | Evidencia medida | Gravedad para el piloto |
|---|---|---|---|
| 1 | **Cada request autenticado paga ~8 viajes a la base antes de ejecutar su lógica** (pre-ping, `set_config`×2, usuario, membresías, permisos×3, step-up). Mediana: **9 consultas por GET**; el login hace **37** | `pg_stat_statements` sobre 294 requests: 562 `set_config`, 296 `users`, 276 `memberships`, 237×3 permisos | Alta: con RTT de nube domina la latencia |
| 2 | **El ORM carga todo por defecto**: 138 relaciones `joined/selectin`. `Reservation` hace JOIN a 6 tablas + 2 consultas extra en *cualquier* lectura; `Room.reservations` trae todo el historial | `analytics/rooms` 84 consultas/2,7 s; `housekeeping` 50/1,4 s; cambiar a carga perezosa: **2.370 → 17 ms** y **1.589 → 21 ms** | Alta |
| 3 | **Reportes suman en Python**: cargan transacciones y reservas como objetos y agregan en diccionarios en vez de `GROUP BY`. `reports/revenue`: **110 consultas, 2,9 s** | `financial_report_service.py:215-330` | Alta |
| 4 | **Memoria: el proceso supera 512 MB con pocos usuarios pidiendo reportes.** Reposo 229 MB → 499 MB tras 4 rondas de 3 reportes → **1.233 MB** bajo carga mixta | RSS medido; el plan `starter` de Render tiene 512 MB | **Crítica** (OOM-kill) |
| 5 | **Capacidad real de un worker**: ~25 req/s en endpoints livianos; con reportes en la mezcla cae a **~2 req/s, p95 6–15 s y errores 503** (pool de 6 conexiones agotado) | prueba de carga, 5–20 usuarios | **Crítica** |
| 6 | **Bug: 4 tablas del ORM no tienen migración Alembic.** En una base creada solo con Alembic, `POST /api/rooms/`, `/subscription/plans` y `/subscription/entitlements` dan **500** | reproducido en vivo (`relation "subscription_plans" does not exist`) | **Crítica** para cualquier entorno nuevo (QA, previews, la base del piloto si es nueva) |
| 7 | **Bug: tras un corte de conexión, el primer request da 500** en lugar de reconectar. El hook `handle_error` de `database.py:158` hace `connection.info` con `connection=None` y rompe el `pool_pre_ping` | reproducido reiniciando Postgres | Alta (Supabase/pooler/plan gratis reinician conexiones) |
| 8 | **`GET /api/bookings/` devuelve todas las reservas del hotel (3,5 MB) y el frontend no lo usa.** De 85 endpoints que devuelven listas, **65 no están paginados** | `bookings.py:274`, `grep` en `frontend/src` | Alta |
| 9 | **Egreso de datos DB→API: 68 KB por request liviano y 2,1 MB por request pesado.** Supabase Free permite 5 GB/mes | proxy TCP contador | Alta para el plan gratis |
| 10 | **Tres sistemas de tareas programadas hacen lo mismo** (Celery beat, cron Render cada 5 min, cron Render horario) y **cuatro motores NoSQL/analíticos están instalados pero apagados** (Mongo, Cassandra, Neo4j, ClickHouse) | `render.yaml`, `render-no-show-cron.yaml`, `celery_app.py`, `requirements.txt` | Media (costo y ruido) |
| 11 | **Vercel Hobby prohíbe uso comercial.** Un PMS con un hotel piloto lo es | doc oficial de Vercel (§ 7) | Alta (cumplimiento) |
| 12 | **Índices: están bien para el piloto, sobran para escribir.** Con 30 hoteles/195.000 reservas todas las consultas calientes tardan **< 4 ms**. Pero los índices ocupan el **63 %** del almacenamiento (126 MB vs 74 MB de datos) | `EXPLAIN ANALYZE` en PG16 real | Baja ahora / Media a escala |
| 13 | **El frontend paga hasta 9 requests antes de la primera consulta de cada página** (refresh bloqueante, 6 lecturas del shell con permisos e idioma repetidos, recovery + stream) y casi toda escritura refetchea los reportes (**90 de 118 modelos** emiten `analytics`) | `session.tsx:368-379`, `usePermissions.ts`, `domain_events.py:276-…`; § 0.3 F2/F3 | Alta |
| 14 | **Operación sin red de seguridad:** ninguna copia de seguridad programada ni restauración probada, ≈ 29–35 min de CI por push (sin `concurrency` ni `paths-ignore`), imágenes Docker que nadie usa, `autoDeploy` sin `buildFilter` y un `requests` sin declarar | `grep`, workflows, `render.yaml`; § 0.3 O3–O8 | Alta (backup) / Media (resto) |

**Qué *no* hace falta:** reescribir el backend en otro lenguaje, agregar más índices (sí crear los pocos que faltan, § 4.3), ni ninguna base NoSQL. Qué *sí* produce el mayor efecto: los puntos 1–5 (≈ 3–6× de capacidad y la mitad de la memoria, medido con dos prototipos de pocas líneas), y arreglar 6–8 antes de abrir el piloto.

### 0.1 Presupuesto de consumo: hoy vs. objetivo

Pregunta de fondo del encargo: *"necesito que consuma mucho menos de lo que consume ahora"*. Esta tabla junta, por recurso, lo medido hoy, lo que ya demostró un prototipo y la meta que propone el plan (§ 11). **Medido** = reproducido con los scripts de [`scripts/`](scripts/); **Prototipo** = medido en una copia descartable; **Meta** = objetivo de diseño, aún no medido.

| Recurso | Hoy (medido) | Qué lo baja | Después | Estado de la cifra "después" |
|---|---|---|---|---|
| Sentencias SQL por `GET` autenticado (mediana) | **9** | colapsar `set_config`, quitar `pool_pre_ping`, caché de permisos invalidada por `NOTIFY` | **≤ 4** | Prototipo: +36 % req/s en endpoints livianos |
| Login | **37 sentencias / 5 transacciones** | un solo `commit`, limitador en memoria | **≤ 12 / 2** | Meta |
| `GET /api/reports/revenue` | **110 sentencias, 2,9 s** | `GROUP BY` en SQL | **≤ 6 sentencias, ≤ 150 ms** | Meta (carga perezosa sola: 26 sentencias, 724 ms, medido) |
| `GET /api/analytics/rooms` | 90 sentencias, 2.370 ms | carga perezosa por defecto | 13 sentencias, **17 ms** | Prototipo |
| Memoria del proceso bajo carga mixta | **1.233 MB** (límite del plan Starter: 512 MB) | carga perezosa + SQL agregado | **611 MB** → meta < 400 MB | Prototipo (611) / Meta (< 400) |
| Capacidad con reportes en la mezcla | **2,3–2,7 req/s**, p95 6–12 s, errores 503 | carga perezosa, semáforo para endpoints pesados | **7–11 req/s, sin errores** → meta ≥ 15 | Prototipo / Meta |
| Egreso DB→API por request liviano / pesado | **68 KB / 2,1 MB** | carga perezosa, listas paginadas, columnas mínimas | **46 KB / 334 KB** → meta ≤ 25 KB liviano | Prototipo / Meta |
| Un intento de login contra el limitador | **4 sentencias + `commit`** (80 por 20 intentos) | limitador en memoria con respaldo en BD solo al bloquear | **0 sentencias** | Medido (variante en memoria) |
| Una llamada de la API pública (clave de API) | **10 sentencias + `commit`** (escribe `last_used_at` siempre) | verificar con caché corto y escribir `last_used_at` como máximo cada N minutos | ~2 sentencias, 0 `commit` | Meta |
| Política de facturación del panel master | **21 sentencias por hotel** (50 hoteles: 1.050 sentencias, 1,4 s) | no reflejar la tabla en cada llamada; una consulta agregada | 1–2 sentencias en total | Meta |
| Códigos de un solo uso (6 dígitos de correo/recuperación, códigos de recuperación MFA) | **59 ms de CPU** con Argon2id | HMAC-SHA256 con *pepper* + comparación en tiempo constante | **< 0,1 ms** | Medido (HMAC) |
| Tareas programadas | **288 contenedores/día** (cron Render cada 5 min; ≈ 5,5 s de *import* + conexión TLS cada vez) + posible segundo cron | `POST /internal/jobs` con secreto + Cloudflare Cron (5 gratuitos) | **0 contenedores**; costo del cron Render −USD 1–2/mes | Meta |
| Costo fijo mensual | **≈ USD 8–9** (Starter + cron; Vercel Hobby no es válido para uso comercial) | topología A o B (§ 7) | **≈ USD 0 (A) / ≈ USD 7 (B)** | Estimado por listas de precios |
| Dependencias instaladas | **291 MB** (178 MB `ortools`/pandas/numpy; 33 MB Mongo/Cassandra/Neo4j/Celery/pytest) | núcleo + extras opcionales | **≈ 80 MB** de núcleo (291 − 178 − 33) | Cuenta directa del desglose |
| Chunk de entrada del frontend | **571 kB / 179 kB gzip** (44 % `react-router` v7) | router más liviano, locales bajo demanda | meta ≤ 350 kB | Meta |
| Imágenes servidas | **2,7 MB** (logo de 992 kB) | WebP/SVG | ≈ 0,3 MB (−90 %) | Estimado |
| Almacenamiento | **63 % índices** (126 MB de 200 MB con 30 hoteles) y sin purga de outbox, sesiones, límite de tasa, exportaciones | quitar redundantes (decidir con `pg_stat_user_indexes`) + tareas de retención (`pg_cron`, ya usado en las migraciones `20260925`/`20260926`) | sin crecimiento no acotado | Meta (sin cifra hasta medir) |

**Lectura de la tabla:** los tres cambios con mayor efecto por esfuerzo son (1) carga perezosa por defecto, (2) costo fijo por request y (3) `GROUP BY` en reportes; solo con la carga perezosa el proceso baja del 240 % al ~120 % del límite de memoria del plan Starter (1.233 → 611 MB sobre 512 MB), y con el SQL agregado de los reportes debería quedar por debajo del 100 % (meta < 400 MB). El cambio de lenguaje no aparece en la tabla porque **ninguna de estas cifras depende de él** (§ 10).

### 0.2 Hallazgos de la lectura completa que no estaban en la primera pasada

La segunda pasada leyó **cada archivo** de `app/` (71 modelos, 137 servicios, 67 routers, 50 esquemas, tareas, adaptadores, panel master) y está en [`LECTURA-COMPLETA.md`](LECTURA-COMPLETA.md). Lo siguiente **cambia el orden del plan**: hay problemas de integridad y seguridad que pesan más que el consumo. Los marcados ✔ se **reprodujeron** con un script (tabla final de `LECTURA-COMPLETA.md`).

**Bloquean el piloto (P0)**

| # | Hallazgo | Evidencia | Arreglo |
|---|---|---|---|
| N1 | **La auditoría escrita después de `db.commit()` se pierde en PostgreSQL** (15 sitios; en SQLite persiste por una rareza del SAVEPOINT, por eso los tests no lo ven) ✔ | `scripts/audit_loss_repro.py`, `scripts/scan_post_commit_audit.py` | Escribir la auditoría **antes** del `commit` en la misma transacción; test contra PostgreSQL |
| N2 | **Los archivos (comprobantes de pago, vouchers de empresa, exportaciones) se guardan en disco local de Render, que es efímero**: se pierden en cada despliegue o reinicio mientras la fila sigue "aprobada". El valor por defecto es `OBJECT_STORAGE_BACKEND=local`, el validador de producción **no lo prohíbe** y `render.yaml` no declara disco. El backend S3 es un esqueleto (solo GCS está implementado) | `config.py`, `object_storage.py`, `render.yaml` | Bucket compatible con S3 (Cloudflare R2 tiene capa gratuita) o Supabase Storage; prohibir `local` en producción; quitar los blobs de la tabla `payment_proof_blobs` |
| N3 | **Credenciales de proveedores (Mercado Pago, OTAs) en texto plano** dentro de `onboarding_state.payment_methods_json` / `ota_channels_json` ✔ | `scripts/verify_misc_findings.py` | Cifrar con `INTEGRATIONS_ENCRYPTION_KEY` (ya existe para Stripe) o no persistir el secreto en el asistente |
| N4 | **La API pública de reservas devuelve `document_type` y `document_number` del huésped** y acepta un `guest_id` cualquiera: con la clave de API de un hotel se leen documentos de otros huéspedes ✔ | `scripts/verify_public_booking_pii.py` | Crear/resolver el huésped dentro del endpoint, esquema público sin documento |

**Capacidad, costo y datos (P1)**

| # | Hallazgo | Evidencia |
|---|---|---|
| N5 | Limitador de intentos persistido en BD: **4 sentencias + `commit` por intento** y sin purga global de `rate_limit_events` ✔ | `measure_hot_paths.py` |
| N6 | Autenticación de la API pública: **10 sentencias + `commit` por llamada** (escribe `last_used_at` siempre) ✔ | `measure_hot_paths.py` |
| N7 | `billing_policy` refleja la tabla en cada llamada: **21 sentencias**; el panel master lo repite por hotel (50 hoteles = 1.050 sentencias, 1,4 s) ✔ | `measure_hot_paths.py` |
| N8 | **Argon2id en secretos de corta vida**: códigos de 6 dígitos de verificación de correo y recuperación (`adapters/memory_tokens.py`), tokens de aprobación temporal (`temporary_action_grant_service.py:240`) y códigos de recuperación MFA, que se verifican **uno por uno contra los 10 códigos sin usar** (`mfa_service.py:99-102`: hasta 10 × 59 ms ≈ 0,6 s de CPU por intento fallido). Cada verificación cuesta 59 ms de CPU ✔; HMAC cuesta < 0,1 ms | `measure_hot_paths.py`, lectura de `services/` |
| N9 | **Endpoints `async def` que hacen trabajo síncrono de base** (webhooks de OTA y de WhatsApp, snapshot de FX): bloquean el bucle de eventos del único worker y congelan los SSE | verificado: `api/ota_webhooks.py:48-80` (`async def` + `validate_webhook_secret`/`process_*_webhook`/`commit` síncronos) |
| N10 | **I/O externo síncrono dentro de la transacción del request** (correo, enlaces de Mercado Pago, validación de Stripe): retiene una conexión del pool (de 6) mientras espera a un tercero | lectura de `services/` y `master_admin/` |
| N11 | **Sin tareas de retención programadas** para `rate_limit_events`, `security_tokens` (existe `app/tasks/cleanup_tokens.py`, pero **nadie lo ejecuta**: ni `render.yaml`, ni cron, ni Celery), `domain_event_outbox` (hay un modelo de *watermark* que nadie usa), exportaciones y sesiones. Solo existe `pg_cron` para *leads*/consultas públicas (migraciones `20260925`/`20260926`): **ese es el patrón a extender** | `grep` + migraciones |
| N12 | **Semántica de permisos cruzada**: `POST`/`PATCH`/`DELETE` de `payment_surcharges` exigen `reports.financial.view` (un permiso de *ver*); igual `room_state_events` | verificado: `api/payment_surcharges.py:140,198,250` |
| N13 | **Sin límite global de tamaño de cuerpo**: solo topes por endpoint (webhooks 2 MB vía `read_bounded_body`; imágenes base64 de 5–7 MB por campo). Un cuerpo grande a cualquier otra ruta se lee entero en memoria | verificado: no hay middleware ni `413` global en `main.py`/`config.py`/`render.yaml` |
| N14 | **Dinero en `float` en la API y en las tarifas** ✔: 125 anotaciones `float` en `app/schemas/` (`transaction.py:22`, `reservation_operations.py`, `hotel_api_key.py`) y 61 columnas `Float` en el ORM (`price_periods`, `daily_rates`, `rate_plan_prices`, `ota_price_rules`, FX…). *Corregido tras verificar:* el libro (`reservations`, `transactions`, `billing_adjustments`) **ya es `Numeric(12,2)`**, así que el riesgo es el redondeo en el contrato y en el cálculo de tarifas, no en lo ya asentado | `schemas/`, `models/commercial.py`, `daily_rate.py`; § 0.3 M5 |
| N15 | `/health/datastores` **sin autenticación** revela qué almacenes existen ✔ | `verify_misc_findings.py` |
| N16 | `guest.digital_signature` (`Text` sin tope) viaja en **todas** las lecturas de huésped y `ReservationRead` serializa 55 campos también en listados | `schemas/guest.py`, `schemas/reservation.py` |
| N17 | **Integraciones que no hacen lo que aparentan**: el webhook de Stripe se guarda y **nunca se procesa**; la salida a OTAs usa credenciales globales, traga `ConnectError` y es un esqueleto; los adaptadores de Mercado Pago/PayPal no se usan | lectura de `adapters/`, `services/ota/` |
| N18 | **Perfil "sandbox"** (`EXTERNAL_EFFECTS_ENABLED=false` ⇒ proveedor de correo `null`): con la configuración actual **no sale ningún correo** (confirmaciones, invitaciones, recuperación). Hay que decidirlo antes del piloto | `config.py`, `render.yaml` |
| N19 | **Tests con `date.today()` (UTC) frente a la zona del hotel (Buenos Aires)**: entre 00:00 y 03:00 UTC fallan pruebas de backend y recorridos E2E sin que cambie el código (observado en el PR #126) | CI del PR |

**Superposiciones y código muerto** (reducen costo de mantenimiento y de arranque): tres implementaciones de *no-show*; tres caminos públicos de creación de reserva; `api/connections.py` y `api/email.py` sin montar (✔ el primero responde 410 por el *catch-all*); `job_dispatcher`; `SubscriptionEnforcementMiddleware` sin registrar; árbol Celery inactivo; proyecciones NoSQL que solo escriben; `bookings`/`daily_rates` heredados; `demo.router` solo fuera de producción.

### 0.3 Frontend, migraciones y operación (lectura completa de las capas restantes)

La tercera pasada leyó los 239 archivos de `frontend/src` (siete partes: [`frontend-notes/`](frontend-notes/)), las 173 migraciones ([`migration-notes-a.md`](migration-notes-a.md), [`migration-notes-b.md`](migration-notes-b.md)) y los 119 archivos de CI/despliegue/scripts/QA ([`ops-notes.md`](ops-notes.md)). Lo que no se pudo confirmar se marca. **Leyenda:** ✔ confirmado contra el código o reproducido (por mí o por un segundo lector; ver [`verificacion-manual.md`](frontend-notes/verificacion-manual.md)) · ◐ leído con evidencia de `archivo:línea`; el segundo lector comprobó una muestra de los hallazgos principales de su parte y este no fue refutado, pero no se comprobó de forma individual · ○ inferido o dependiente de datos de producción. Las partes de frontend 5–7 y ops tuvieron la tasa de corrección más alta (32–38 % de las afirmaciones comprobadas, frente a 13–29 % en las demás partes), así que sus ◐ merecen más cautela. Donde una nota decía algo que la verificación desmintió, está corregido aquí. Cambios concretos para los hallazgos nuevos: [`SOLUCIONES.md`](SOLUCIONES.md) S19–S24 (S19 y S20 con código probado).

**Frontend (F)**

| # | Hallazgo | Estado | Arreglo |
|---|---|---|---|
| F1 | **`/reservas` pide `limit=200` ordenado por `check_in` ascendente y sin fechas**; KPIs, calendario e historial salen de esa lista truncada: con más de 200 reservas deja de mostrar lo vigente (`ReservationsPage.tsx:403-415`, `reservation_service.py:2093`). Mismo patrón en Dashboard (200 reservas completas para pintar 6 líneas) y Stock (200 con huésped para un selector colapsado) | ✔ `/reservas`; ◐ Dashboard y Stock | Ventana de fechas + paginación en servidor; endpoint de resumen para los KPIs |
| F2 | **El arranque de una sesión existente bloquea el render hasta que `POST /api/auth/session/refresh` responde** (`session.tsx:175-177,368-379`: cascada refresh → chunk de `AppShell` → chunk de página → datos) y luego dispara 6 lecturas propias del shell (permisos efectivos, `notifications?limit=1`, `config/`, `interface-language`, y `onboarding/status` y `subscription/status` según el rol) + recovery + stream: **hasta 9 requests antes de la primera consulta de la página**. Los permisos se piden de nuevo aunque ya vienen en el refresh (`usePermissions.ts:16-22`, sin `initialData`) y el idioma repite `hotel-config`. Peor caso del refresh: 62 s (3 × 20 s + 0,5 + 1,5; reintentos del cliente); el cold start de Render Free solo aplica si el servicio real es Free (`render.yaml:8-12` declara Starter, siempre encendido; O1) | ✔ (verificado por un segundo lector) | Sembrar permisos e idioma desde la respuesta del refresh; un único `GET` de arranque; no bloquear el render del shell |
| F3 | **Tormenta de invalidación:** 90 de 118 modelos emiten el dominio `analytics` (`domain_events.py:276-…`), así que casi toda escritura refetchea los reportes **activos de todos los clientes del hotel** (hoy 110 consultas/2,9 s). Helpers que invalidan de más: `refreshSettingsState` (24 prefijos), `refreshStockState` (19), `applyDraft` del asistente (69 de 86 claves) | ✔ 90/118; ◐ helpers | Invalidar por clave concreta; reportes con `refetchType: "none"` + marcar obsoletos |
| F4 | **SSE por pestaña, sin líder:** cada pestaña visible abre su stream y su `recovery`; el cursor vive en `sessionStorage`, una pestaña nueva arranca en 0 y, si el outbox del hotel supera 500 filas (nadie lo purga, N11), `has_more` fuerza refetch de **todas** las queries activas. *Corregido:* el hilo del threadpool fijo por stream existe **solo con transporte Redis** (`iter_event_stream`); con `LISTEN/NOTIFY`, el perfil de `render.yaml`, el stream es asíncrono (`domain_events.py:2160`) | ◐ (corrección ✔) | Purgar el outbox; cursor en `localStorage`; un solo stream por navegador (`BroadcastChannel`/`SharedWorker`) |
| F5 | **Sin `queryClient.clear()` al cerrar sesión** y claves de caché sin `userId` (`["notification-inbox", hotelId, …]`, `["reservations", hotelId, filters]`): en un puesto de recepción compartido el usuario siguiente ve primero lo cacheado por el anterior durante `staleTime`. El logout tampoco se propaga a otras pestañas | ✔ hecho; ○ impacto (depende de que compartan navegador) | `queryClient.clear()` en logout/401; `userId` en las claves |
| F6 | **`PricingPage` (panel master) puede vaciar el sitio:** si el `GET` falla, "Publicar precios" envía `plans: []` y el servidor borra todo plan no mencionado (`PricingPage.tsx:57-93`, `marketing_service.py:140-142`, `schemas/marketing.py:84-85` sin `min_length`) | ✔ | `min_length=1`; deshabilitar el botón hasta que cargue el `GET` |
| F7 | **Onboarding:** las credenciales de 6 proveedores van en un `<input>` de texto y se guardan en claro (= N3); al **volver a montar** el wizard (recarga o salir y volver a `/onboarding`) y guardar el paso se borran las ya cargadas (dentro de la misma sesión se reenvían); cada paso dispara un `GET /onboarding/status` redundante (~10 por wizard, estimado) | ✔ credenciales; ◐ resto | N3; no invalidar el dominio completo en cada paso |
| F8 | **Búsquedas sin debounce:** buscador global del header (una request por tecla con `ILIKE '%…%'` y 3 joins), Huéspedes (hasta 5 HTTP + 1 WebSocket por tecla, destruye la selección), Auditoría operativa, selector de fechas de Reportes | ✔ buscador global; ◐ resto | Debounce 250–300 ms + `placeholderData: keepPreviousData` |
| F9 | **Pantallas que cargan sin cota:** `GET /laundry/remitos` y `GET /cash-register/sessions` (ambos terminan en `.all()` ✔), bandeja de WhatsApp (50 conversaciones con todos sus mensajes por `selectin` ✔), Auditoría operativa (12 consultas incondicionales × hasta 20.000 filas ORM, o sea hasta 240.000 objetos por request, con filtros/orden/paginación en Python; corregido por el verificador: eran "9"), calendario de tarifas (dos payloads por cambio de categoría/año, de hasta 366 columnas: ≈ 3.660 celdas y 2.196 inputs sin memo en un año completo; 78 columnas el año en curso a mediados de octubre), Analytics (`.all()` sobre los hechos del rango) | ✔ las marcadas; ◐ resto | Paginación por cursor + agregación en SQL |
| F10 | **Reportes duplica trabajo.** Medido en producción por QA (2026-10-06): una carga de Reportes envía dos requests (`/api/reports/operational/daily` y `/operational/alerts`) que **cada una reconstruye el mismo informe operativo con 39 consultas** (78 en total, 2.330 + 2.242 ms de app, ≈ 44–50 ms por consulta; `qa/operational/runs/production-latency-20261006-73398218/report.md:12-17`). Por lectura del código, `ReportsPage` además pide `reports/revenue` (110 consultas/2,9 s en mi medición) para día y semana y otra vez por cada exportación | ✔ la medición de producción (es de QA, no mía); ◐ día/semana | Un solo informe para ambas vistas (o caché por fecha con la misma clave de eventos) + `GROUP BY` (§ 3.2) |
| F11 | **i18n y bundle:** `es`+`en` van estáticos en el chunk de entrada incluso para marketing (16 JSON, 196.713 B crudos; `reservations` = 129.193 B / 33.378 B gzip, medidos ✔). Un lector estimó que dejar `en` perezoso saca −48 % de la entrada y que los namespaces por ruta dejan 167.839 → 7.853 B min (cálculo sobre los JSON, **sin `vite build`**). Prerrequisitos: `ReservationDetailDrawer` (1.949 líneas) se importa estático en `AppShell.tsx:7` (el chunk lazy de `AppShell`, no el de entrada) y se monta aunque no haya `?reserva=`; además `DashboardPage.tsx:490,506` usa el namespace `reservations`, así que diferirlo exige que Dashboard, Drawer y planilla lo carguen por su cuenta. Además `largeTotalAdjustmentWarning` usa `{current}`/`{proposed}` de llave simple (`reservations.json:822`) y `i18n.ts:39` no cambia el prefijo de interpolación (`{{ }}`): el aviso de ajuste ≥ 50 % muestra los marcadores literales en vez de los importes (`ReservationsPage.tsx:4396`) | ✔ tamaños y el bug de interpolación; ◐ ahorros | `en` y namespaces por ruta con `import.meta.glob`; `React.lazy` para el Drawer |
| F12 | **Activos y caché:** `index.html:97-101` pide Inter a Google Fonts (CSS bloqueante + 2 `preconnect`) aunque Inter está autoalojado; el `service worker` es cache-first de todo GET same-origin que no sea navegación ni `/api` (las navegaciones sí van network-first, `sw.js:77-82`; el cache-first es `:84-98`), con nombre de caché fijo `chipre-shell-v1`: el `activate` borra las cachés con otro nombre, pero como el nombre nunca cambia no se borra nada (bundles con hash viejos se acumulan; `/manifest.webmanifest`, `/brand/*` y `/fonts/*`, sin hash, quedan congelados en la primera versión cacheada); `/fonts`, `/brand`, `/marketing` sin `Cache-Control` largo (`vercel.json:44-52`, estimado) | ✔ SW y `index.html`; ○ cabeceras | Quitar la hoja de Google; versionar la caché del SW; `immutable` para activos con hash |
| F13 | **Permisos mostrados ≠ exigidos** en ≥ 10 pantallas: peticiones que fallan por diseño en cada montaje (`companies/options` → 402 en plan `starter` ✔; `room-movement-groups` → 403 solo con roles personalizados sin `reservation:move`, *corregido*) y menús que se ocultan si el plan es `undefined` | ✔ `companies/options`; ◐ resto | Un solo mapa permiso↔endpoint, probado en CI |
| F14 | **POST sin `Idempotency-Key`** frente a timeouts de 60 s (crear reserva/grupo, cargos, extensión con cobro, `createPaymentLink`); `StockPage` regenera la clave en cada clic | ◐ | Generar la clave una vez por intento de formulario |
| F15 | **Archivos en base64 dentro de JSON** sin validar tamaño en el cliente (comprobantes de pago, gastos de caja, documentos de empresa, fotos de tareas): hasta ≈ 7 MB por request y 3 copias en memoria; el servidor rechaza recién después de recibirlo todo. Se suma a N2 y N13 | ◐ | Reescalar a ≤ 1.600 px en el navegador; subida multipart o URL firmada al bucket |
| F16 | **Monolitos y re-renders:** `ReservationsPage` 6.120 líneas (55 `useState`, 6 `useEffect`, 0 memo, lista duplicada tabla+tarjetas); 8 páginas más superan las 1.000 líneas; `useEffectivePermissions()` se llama en 28 sitios (27 archivos) y cada montaje crea una sesión nueva que re-renderiza a los consumidores de `useSession()` ✔. Defectos visibles: "Check-outs hoy" cuenta todas las históricas, `GuestsPage.formatDate` muestra un día menos en Argentina, `SettingsUsersPage` revoca sin confirmar | ✔ 28 sitios; ◐ resto | Dividir por pantalla; memoizar el contexto de sesión |

**Migraciones y datos (M)**

| # | Hallazgo | Estado | Arreglo |
|---|---|---|---|
| M1 | **Tablas que crecen sin purga** (lista completa en las secciones (c) de las notas de migraciones): `rate_limit_events`, `security_tokens` (`TokenStore.issue()` borra los no consumidos del mismo sujeto, pero `cleanup_tokens.py` no está programado: quedan las consumidas), `user_sessions`, `notifications`/`notification_outbox`, `payment_webhook_events` (payload completo, hasta 3 copias), 5 tablas de auditoría, `ai_assistant_*` (texto crudo con PII), `fx_rate_snapshots`, `analytics_export_jobs` (la fila queda `expired`), `domain_event_outbox`, `whatsapp_messages.text`, BYTEA heredado `payment_proof_blobs`. El único `pg_cron` es `hotel-chipre-public-form-retention` (`0 4 * * *`, migración `20260925`) | ✔ | [`solutions/retention_pg_cron.sql`](solutions/retention_pg_cron.sql) (probado) |
| M2 | **≈ 70 índices candidatos a baja** (37 en la mitad A de las migraciones y 36 en la B; hay solapes entre ambas): 13 duplicados exactos de un `UNIQUE` (p. ej. `ix_transactions_hotel_status_created` = `…_created_at`, tres `ix_master_*` sobre columnas `unique=True`) y ≈ 25 prefijos `hotel_id` simples. `guests` llega a 15 estructuras de índice por fila; se suman ≤ 27 `UNIQUE (hotel_id, id)` y 100 FKs compuestas que duplican la verificación referencial en cada `INSERT`. *Corregido:* "+17 índices" eran ≤ 14 nuevos y "30 UNIQUE" ≤ 27 (3 ya existían) | ✔ por lectura de las 173 migraciones; el uso real exige `pg_stat_user_indexes` | Decidir con 2 semanas de estadísticas y `DROP INDEX CONCURRENTLY` (solo 1 de 88 migraciones de la parte B usa `CONCURRENTLY`) |
| M3 | **Índices que faltan o deberían ser parciales:** `room_state_events` y `analytics_export_jobs` **sin ningún índice** (y con RLS por `hotel_id`); `hotel_api_keys.key_hash` sin índice (la API pública busca por hash); `(hotel_id, item_id)` en `stock_movements`/`linen_movements`; `guests.retention_until`. No parciales sobre columnas casi siempre NULL: `ix_reservations_hotel_group`, `ix_transactions_hotel_prior_receipt_date`, `ix_transactions_refund_source_status`, `ix_user_sessions_previous_token`, `ix_domain_event_outbox_pending`, `ix_whatsapp_outbox_pending`. Los 5 B-tree `(hotel_id, nombre\|apellido\|email\|…)` de `guests` no sirven el `ILIKE '%…%'` que ejecuta `guest_service.py:200-206`; ya hay 5 GIN trigram que sí | ✔ por lectura | Crear los que faltan; parcializar; quitar hasta 4 B-tree de `guests` tras medir |
| M4 | **RLS ↔ API pública:** `hotel_api_keys` tiene RLS `FORCE` con política por `app.hotel_id`, pero `verify_key` busca la clave por hash antes de conocer el hotel. **Reproducido en PostgreSQL 16** con un rol `NOBYPASSRLS`: 0 filas sin contexto, 1 con él. O la `DATABASE_URL` de producción conecta con un rol `BYPASSRLS` (entonces la RLS no protege nada) o toda clave pública responde 401. Los dos casos son un problema; cuál rige es `needs-verification` (§ 12). Aparte, las políticas usan `current_setting` sin `(SELECT …)`; **medido**: con 30 hoteles no costó nada apreciable (§ 4.3), así que no es prioridad | ✔ reproducido | Función `SECURITY DEFINER` de búsqueda por hash, o política permisiva para la lectura por `key_hash`; rol de aplicación `NOBYPASSRLS` |
| M5 | **Dinero y tipos (corregido):** el libro (`reservations`, `transactions`, `billing_adjustments`, `reservation_adjustments`) **ya es `Numeric(12,2)`** desde `20260612_v72_gaps_phase1/3`. Siguen `Float` **61 columnas del ORM** (56 de monto/tasa/precio: `price_periods` 9, `ota_price_rules` 9, `category_pricing_legacy` 8, `daily_rates` 6, `rate_plans`, FX…) y **125 anotaciones `float`** en `app/schemas/` (`transaction.py:22`, `reservation_operations.py:126-204`, `hotel_api_key.py:72-142`). `price_periods` **no** se retira: absorbe `category_pricing` | ✔ (metadatos del ORM y `grep`) | Migrar tarifas y contratos de API a `Numeric`/`Decimal` (N14) |
| M6 | **Esquema muerto o dormido:** 34 tablas del "fundamento OTA/allocation/pricing" (`dee1bd0660f6`, 56 índices, 15 `hotel_id` redundantes); `OTAPropertyMapping`, `OTACancellationRule` y `domain_event_outbox_retention_watermarks` sin uso fuera de `app/models`; `category_pricing_legacy` sigue mapeada. Pagan RLS, planificador y backup | ◐ | Decidir con el producto; retirar con migración |
| M7 | **Riesgos de la cadena de migraciones:** backfills fila por fila (`tech0140` trae todo el outbox a memoria; `20260927_ota_credit_backfill` ≈ 3 sentencias por reserva); `DROP COLUMN` por reflexión en `audit_logs` (`ebd2db08c7d0`); `20260925` falla cerrado sin `pg_cron`; el `LISTEN` exige conexión directa (excluye el pooler 6543: `postgres_event_listener.py:40-41` ✔) y consume una conexión permanente; `fact_reservation_daily_channel_code_enum` no tiene el valor `company` (una reserva corporativa rompería la proyección: inferido, no ejecutado); 7 migraciones de reparación y 0 `CONCURRENTLY` fuera de una | ◐ | Test "Alembic → app → smoke" en PostgreSQL (§ 11, Fase 0) |

**Operación, CI y costo (O)**

| # | Hallazgo | Estado | Arreglo |
|---|---|---|---|
| O1 | **`render.yaml` no describe necesariamente lo que corre:** define `hotel-chipre-pms-api` en plan `starter` con `preDeployCommand`, pero los reportes de `qa/` observan `hotel-backend` en plan **Free**, sin pre-deploy, con `EMAIL_PROVIDER=resend` y `READ_MODEL_CACHE_ENABLED=true` efectivo. Los reportes de `qa/` son anteriores a la reescritura del 2026-10-12 (el yaml previo declaraba plan standard, Redis y pool de 15 s), pero la divergencia Free / `hotel-backend` / sin pre-deploy se sostiene; las latencias de 3–10 s de `qa/` pueden ser de otra configuración | ◐ (`qa/operational/runs/…/report.md`; un segundo lector confirmó la divergencia) | Alinear el blueprint con el servicio real antes de optimizar |
| O2 | **Región API↔DB probablemente cruzada:** `render.yaml` no fija `region`; `.env.render` (archivo de ejemplo con marcadores, no prueba de la región real) menciona Supabase `aws-0-us-east-1`; producción midió 38–50 ms por consulta (`/operational/daily`: 1.966 ms / 39 = 50 ms; `/alerts`: ≈ 38 ms; promedio ≈ 44 ms). Con 9–60 consultas por pantalla domina la red | ○ (la medición ✔; la región real, no) | Confirmar regiones; misma región; § 11 punto 4 |
| O3 | **Cada push a un PR cuesta ≈ 29–35 min de CI** (e2e ≈ 16,1 min medido en un reporte de QA; el resto, estimado) sin `concurrency`, sin `paths-ignore`, sin caché de Playwright y con `npm ci` duplicado; 63 de 111 commits no-merge del clon (57 %; clon superficial, el más antiguo es del 2026-09-26) no tocan código de ejecución | ✔ ausencia de `concurrency`/`paths-ignore`; ○ minutos | `concurrency: cancel-in-progress`, `paths-ignore`, caché de `~/.cache/ms-playwright` |
| O4 | **`build-and-push.yml` construye y sube 2 imágenes por merge a `main` que nadie consume** (solo ese workflow y un test mencionan `ghcr.io`; Render despliega con runtime nativo), sin caché de capas ni retención | ✔ el hecho; ○ 7–11 min | Quitarlo o pasarlo a manual |
| O5 | **`autoDeploy: true` sin `buildFilter`** (`render.yaml:134`): cada commit reinstala dependencias (con `ortools`+pandas+numpy), migra y reinicia, también los de documentación | ✔ configuración; ○ efecto (depende del servicio real, O1) | `buildFilter` con `app/`, `alembic/`, `requirements.txt` |
| O6 | **Dependencias:** `requests` se importa en 8 módulos y **no está en `requirements.txt`** (llega por transitiva); 11 de 33 pins directos son prescindibles (≈ 61–62 MB de wheels); `pytest*` viaja a producción; Python 3.11 (backend CI, `runtime.txt`, Dockerfile) frente a 3.12 (e2e, local) | ✔ `requests`; ◐ resto | Declarar `requests`; `requirements-dev.txt`; unificar la versión |
| O7 | **No hay backup/restore programado en el repo** (0 coincidencias de `pg_dump\|backup` en `.github`, `render*.yaml`, `docker-compose.yml`); el único drill es local (`scripts/backup/verify_local_backup_restore.py`). Los planes gratuitos no incluyen PITR (§ 7); si incluyen copias diarias es `needs-verification`. Pasa a P0 el día que el piloto cargue datos reales | ✔ ausencia en el repo; ○ proveedor | Job semanal de `pg_dump` cifrado a R2/B2 + restauración probada |
| O8 | **Higiene de configuración:** `.mcp.json`, `.claude/settings.json` y 36 agentes generados fijan rutas de macOS (`.mcp.json` es la causa del `ENOENT` de `stripe`/`supabase` en esta sesión ✔); `vercel.json` raíz tiene 1 rewrite frente a 9 en `frontend/vercel.json` (cuál usa Vercel: `needs-verification`; el impacto es de SEO y de vista previa de enlaces, porque los `.html` de marketing son copias de `index.html` con meta tags por ruta y el mismo bundle JS: no es ancho de banda); `docker-compose.yml` levanta 5 almacenes + Celery y publica puertos en todas las interfaces; `staged_http_load.py` no rechaza hosts de producción. **0 secretos reales** en el alcance leído (solo credenciales de prueba E2E/demo) | ✔ `.mcp.json` y `vercel.json`; ◐ resto | Rutas relativas/`$HOME`; unificar `vercel.json` |
| O9 | **Polling no explicado:** un reporte de QA registra 182 llamadas a `/api/notifications` en 49 min (≈ 3,7/min por pestaña) pero `frontend/src` **no tiene** `refetchInterval` ni `setInterval`; puede ser el *recovery* en modo degradado o refetch por eventos | ○ | Medir con los logs de Render antes de cambiar nada |


---

## 1. Cómo se midió (y límites)

- **Entorno:** PostgreSQL 16 real (con `pg_stat_statements`), Python 3.12, uvicorn con **1 worker y pool 4+2**, `APP_ENV=production` con las variables de `render.yaml` (realtime por Postgres, sin Redis, `READ_MODEL_CACHE_ENABLED=false`, sin ClickHouse).
- **Datos sintéticos realistas:** 1 hotel × 30 habitaciones × 1.800 huéspedes × 6.500 reservas × 5.700 transacciones (2 años de historia). Para escala: **30 hoteles / 195.000 reservas / 54.000 huéspedes / 170.000 transacciones (214 MB)**.
- **Dos roles de base:** superusuario (RLS no aplica) y un rol `NOBYPASSRLS` (RLS activa, como debería correr producción).
- **Límites honestos de la evidencia:**
  1. Medí en `localhost`: **sin latencia de red** entre API y DB. Por eso reporto *consultas por request* (invariante) y proyecto el tiempo con RTT = 1/5/20/60/170 ms (§ 2.1).
  2. La máquina de prueba tiene 4 vCPU; Render Starter tiene 0,5 CPU. Los **req/s absolutos serán menores allá** (orden de 1/4–1/8); las **mejoras relativas se mantienen**.
  3. No tuve acceso a Render/Supabase de producción (los conectores de este entorno no autenticaron). Lo que dependa de la configuración real está marcado `needs-verification` (región, rol de DB, tamaños reales).
  4. Los experimentos de "carga perezosa" y "caché de autenticación" se hicieron sobre **copias descartables**; el repo no se modificó. Son medidas de potencial, no código listo para mergear.

---

## 2. Backend: runtime y costo por request

### 2.1 El costo fijo por request autenticado
Cadena real de `get_auth_context` + `require_permission` (leída en `app/dependencies/auth.py` y `permission_service.py`):

1. `pool_pre_ping` → `SELECT 1`
2. `db.get(User)`
3. `set_config('app.user_id')`
4. `SELECT hotel_memberships`
5. `set_config('app.hotel_id')`
6. `effective_role_code` (consulta solo si el rol es custom)
7. `resolve()` → `get_effective_permission_details`: 3 consultas (defaults de rol, overrides de hotel, overrides de usuario) **y calcula el diccionario de ~150 permisos para validar uno** (≈14 % de la CPU de un listado típico, medido con cProfile)
8. `permissions WHERE step_up_required` (otra consulta)

Resultado medido: **mínimo 5, mediana 9, promedio 12,8 consultas por GET**; 11 de 129 endpoints (los públicos) hacen ≤ 2.

**El login**: 37 consultas, **5 transacciones** (4 `commit`), cada una repitiendo pre-ping + 2 `set_config`; más el limitador de tasa persistido (advisory lock + `DELETE` + `COUNT` + `INSERT` por intento), `user_sessions`, `security_audit_logs` y una fila de outbox con `pg_notify`.

Latencia que esto implica según la distancia API↔DB (consultas × RTT, sin contar CPU):

| Pantalla | consultas | RTT 1 ms | 5 ms | 20 ms | 60 ms | 170 ms |
|---|---:|---:|---:|---:|---:|---:|
| `GET /api/rooms/` | 9 | 0,02 s | 0,05 s | 0,19 s | 0,55 s | 1,54 s |
| `GET /api/reservations/` | 11 | 0,03 s | 0,07 s | 0,24 s | 0,68 s | 1,89 s |
| `GET /api/guests/` | 16 | 0,49 s | 0,56 s | 0,80 s | 1,44 s | 3,20 s |
| `GET /api/reports/revenue` | 110 | 2,5 s | 3,0 s | 4,6 s | 9,0 s | 21 s |

> `needs-verification`: `render.yaml` no fija `region` y `render-no-show-cron.yaml` usa `oregon`, mientras que `.env.render` (archivo de ejemplo) menciona Supabase `aws-0-us-east-1`; la región real no está verificada. Si el API quedó en Oregon y la base en us-east-1, el RTT ronda 60–70 ms y **cada pantalla cuesta ~0,6 s solo en viajes**. Poner API y base en la misma región es el cambio de costo cero con mayor retorno inmediato.

### 2.2 Middleware y telemetría
Tres `@app.middleware("http")` (BaseHTTPMiddleware) + tres ASGI (CORS, GZip y la telemetría de bytes de respuesta) por request. Cada consulta ejecuta además dos listeners que calculan bytes de parámetros (`_estimate_parameter_bytes`). Es costo pequeño (≈1,6 % en el perfil de CPU) pero constante; conviene muestrear en vez de medir siempre. `is_production_mode()` relee entorno en cada respuesta.

### 2.3 Dos bugs del camino de conexión (reproducidos)
- **Esquema ORM ≠ Alembic** (ver § 4.1): 500 en base nueva.
- **`database.py:154-166`**: `_handle_query_error` accede a `exception_context.connection.info` sin comprobar `None`. El pre-ping falla *antes* de tener conexión → `AttributeError` → 500 en lugar de descartar la conexión muerta y reconectar. Una línea (`if exception_context.connection is None: return`).

### 2.4 `init_db` en desarrollo vs producción
Producción solo verifica `alembic_version` (bien). Pero en desarrollo/tests `init_db` hace `create_all` + "self-heal" que agrega columnas y rellena NULLs: **esa es la causa de la deriva de § 4.1**, porque los 2.055 tests corren sobre `create_all` y nunca ven una base solo-Alembic. También ejecuta DDL (`CREATE UNIQUE INDEX`) y por eso no arranca con un rol que no sea dueño.

---

## 3. ORM, consultas y paginación

### 3.1 Carga ansiosa global (el multiplicador)
`grep` sobre `app/models`: **102 relaciones `joined`, 36 `selectin`, 20 `select`**. Solo 11 archivos usan opciones de carga explícitas (`raiseload`, `selectinload`, `load_only`; `list_rooms` ya usa `raiseload("*")` y cuesta 9 consultas — el remedio se conoce pero no es la regla).

Ejemplo: `db.query(Room)` arrastra `Room.reservations` (selectin) → todas las reservas históricas, cada una con JOIN a `guest, room, category, sellable_product, rate_plan, tax_policy` + `transactions` + `additional_guests` por selectin. En `pg_stat_statements`: **78.000 filas de reservas con JOIN y 101.000 filas de transacciones** devueltas en un solo barrido de 129 endpoints.

**Experimento (copia descartable): cambiar las 138 relaciones eager a `lazy="select"`**

| Endpoint | consultas antes→después | tiempo antes→después |
|---|---|---|
| `/api/analytics/rooms` | 90 → 13 | 2.370 → **17 ms** |
| `/api/rooms/housekeeping/summary` | 53 → 10 | 1.672 → **17 ms** |
| `/api/rooms/housekeeping-board` | 52 → 14 | 1.589 → **21 ms** |
| `/api/reports/revenue` | 114 → 26 | 2.990 → 724 ms |
| `/api/reports/daily` | 37 → 17 | 82 → 24 ms |
| **`/api/bookings/`** | 47 → **6.512** | 1.681 → 7.261 ms (**N+1**) |

Capacidad con la mezcla que incluye reportes (misma instancia, pool 4+2):

| | req/s | p95 | errores | RSS final |
|---|---:|---:|---|---:|
| Base (5 → 20 usuarios) | 2,3 → 2,7 | 6,4 → 11,6 s | **503×12, 500×1** | **1.233 MB** |
| `lazy="select"` | 7,2 → 11,4 | 0,8 → 2,8 s | **ninguno** | **611 MB** |

La lección: el cambio de *default* resuelve los reportes pero rompe los serializadores que sí necesitan relaciones (`/bookings`: N+1). La solución correcta es **default perezoso (o `raise`) + `selectinload`/`joinedload` explícito en cada endpoint que serializa relaciones**. Lo hace tratable la suite existente: **el cambio global rompe solo 6 de ~3.040 tests** (§ 9), todos aserciones sobre la *forma* del SQL (bloqueos de fila, lecturas por lotes).

### 3.2 Agregación en Python
`build_financial_report` (`financial_report_service.py:183-330`) hace `db.query(Transaction)….all()`, luego `db.query(Reservation)….all()`, y suma en `defaultdict`. Lo mismo `analytics_service` (11 `.all()` sin límite), `cash_daily_summary_service`, `operational_report_service`, `rate_calendar_service`. Reemplazar por `SELECT currency, method, sum(amount) … GROUP BY` baja de 110 a ~5 consultas y de ~25 MB a ~KB.

### 3.3 Escaneo AST de todas las funciones (`app/`)
2.866 funciones · 774 tocan la DB · 2.958 sitios de acceso · **55 funciones con consultas dentro de bucles** (candidatas N+1; la mayoría son pequeñas — `list_hotel_roles` hace 25 consultas en `/api/roles`) · **231 `.all()` sin `.limit()`** · 18 funciones con ≥3 `commit()` (login, registro, invitaciones: cada commit reabre transacción y reaplica `set_config`). Detalle por archivo en `INVENTARIO.md`.

### 3.4 Paginación y rutas duplicadas
- 85 `GET` devuelven arrays; **20 paginados, 65 no**.
- `GET /api/bookings/`: sin filtros ni paginación, 3,5 MB, **sin uso en el frontend** (el frontend solo usa `price-quote` de ese router). Eliminarlo o paginarlo.
- **28 rutas están publicadas dos veces** (`/cash-register/*`, `/fx/*`, `/payment-links/*`, `/operations/audit` y su gemela `/api/…`): 31 operaciones duplicadas en un OpenAPI de 474 paths / 554 operaciones.

---

## 4. Estructura de datos

### 4.1 Esquema: números y deriva ORM ↔ Alembic
- ORM: **175 tablas, 2.167 columnas, 455 FKs, 306 índices declarados**. Alembic crea **172 tablas / 656 índices** (incluye PK y únicos).
- **RLS**: 145 tablas con RLS, 142 con `FORCE`, 144 policies `hotel_id = NULLIF(current_setting('app.hotel_id',true),'')::int`.
- **Deriva confirmada** (diff de metadatos contra una base recién migrada):
  - **4 tablas solo en el ORM, sin migración:** `subscription_plans`, `hotel_subscriptions`, `subscription_entitlements`, `hotel_entitlement_overrides`. → 500 en base nueva (§ 0 #6). Probablemente producción las tiene de la época `create_all` (`needs-verification`), pero cualquier entorno nuevo no.
  - 1 tabla de backup huérfana en migraciones (`_r2_subscription_price_backup`), 11 columnas muertas en `hotel_configuration` (OTA/revenue legacy), 1 índice del ORM ausente en la base (`ix_domain_event_outbox_retry`), **178 índices que existen solo en migraciones**.
- **Sistemas paralelos** (doble fuente de verdad): suscripción legacy + v2, OTA `ota.py` + `ota_core.py`, `connections` + `integration_connections`, precios por método de pago en columnas (`daily_rates`, `price_periods`, `category_pricing_legacy`: 8 columnas de precio c/u) + modelo `rate_plans/sellable_products`, y tres tablas de auditoría (esta última es separación deliberada según `docs/architecture/audit-log-contract.md`).

### 4.2 Tipos
- **Dinero en `Float`:** 61 columnas en el ORM actual (56 de monto/tasa/precio: `price_periods` 9, `ota_price_rules` 9, `category_pricing_legacy` 8, `daily_rates` 6, `rate_plans` 3, `fx_rate_snapshots` 2, `payment_link_tests.amount`, `tax_policies`…), más 125 anotaciones `float` en `app/schemas/`. **Las reservas, transacciones y ajustes ya usan `Numeric(12,2)`** (verificado en las migraciones `20260612_v72_gaps_phase1/3` y en los modelos). Además `_compute_deposit_amount` calcula `round(float(total) * pct/100, 2)`. Migrar lo que sea *monto* a `Numeric` (la migración `payment_surcharges.amount Float→Numeric` ya sentó el precedente).
- **Fechas:** **238 columnas `DateTime` sin zona vs 65 con zona** (convención "UTC naive"). Mezclado y frágil; normalizar a `timestamptz`.
- **Enums nativos de Postgres: 64 tipos / 76 columnas.** Agregar un valor exige `ALTER TYPE` y ya produjo un incidente (labels incompatibles OTA/allocation, `STATUS-TODAY` § 8). `text + CHECK` evoluciona sin DDL de tipos.
- **JSON en `Text`** (`pricing_snapshot`, `requested_attributes_json`): no consultable; usar `jsonb` solo donde se consulte.
- **Tablas anchas:** `reservations` 75 columnas (financieras, pago externo, cancelación…); `hotel_configuration` 46. Separar es refactor grande: no urge, pero `load_only`/proyecciones en listados sí.

### 4.3 Índices (medido en PG16 con 30 hoteles)
- **Para consultas calientes alcanzan:** listado paginado 0,3–0,6 ms; solape por habitación 0,14–0,16 ms; grilla de ocupación 2,7 ms; typeahead de huéspedes 3,3–4,6 ms; revenue 30 días 1,7–3,1 ms. **La RLS casi no cuesta en el plan** (se resuelve como `One-Time Filter` y usa los mismos índices; el costo de la RLS son los `set_config`).
- **Sobran** (peso de escritura y espacio): `reservations` tiene **18 índices** (59 % del tamaño total de la tabla en bytes de índice):
  - `ix_reservation_dates (check_in, check_out)` **sin `hotel_id`** (global, inútil con multi-tenant);
  - `ix_reservation_hotel_id` solitario (prefijo de otros 9) — el planificador lo elige *en lugar* de uno mejor para la grilla;
  - `ix_reservations_external_id`, `ix_reservations_source_provider_code` (cubiertos por `uq_reservation_ota_external_id`);
  - `ix_reservation_rate_plan_id`, `ix_reservation_sellable_product_id` (columnas casi siempre NULL → parciales);
  - `ix_reservation_hotel_deleted_at` y las compuestas deberían ser **parciales `WHERE deleted_at IS NULL`**.
  - En total **65 índices B-tree son prefijo de otro** (la mayoría el `*_hotel_id` solitario).
- **`guests`: 40 MB de índices para 8 MB de tabla (5×)** — 5 GIN trigram (25 MB) + 8 B-tree. A 1.800 huéspedes/hotel el planificador ni los usa. Consolidar en 1 GIN sobre un campo de búsqueda concatenado y recortar los B-tree.
- **Grilla de ocupación** (`check_in <= X AND check_out > Y`) escanea todo el hotel porque solo hay cota superior de `check_in`. Probado: agregar cota inferior por estadía máxima (+`ix_reservation_hotel_room_dates`) → 2,7 → **1,0 ms**; GiST `daterange` → **0,8 ms**. Relevante recién cuando un hotel supere ~50.000 reservas.
- **Lectura de las 173 migraciones (§ 0.3 M2/M3):** ≈ **70 candidatos a baja** (37 en la mitad A y 36 en la B, con solapes): 13 duplicados exactos de un `UNIQUE`, ≈ 25 prefijos `hotel_id` simples y 6 índices sobre columnas casi siempre NULL que deberían ser parciales. Cada tabla "con RLS" paga además la FK compuesta `(hotel_id, id)`: **≤ 27 `UNIQUE` y 100 FKs compuestas** duplican la verificación referencial en cada `INSERT`.
- **Índices que faltan** (a diferencia de lo anterior, estos *sí* conviene crearlos): `room_state_events` y `analytics_export_jobs` (cero índices, con RLS por `hotel_id`), `hotel_api_keys.key_hash` (la API pública busca por hash), `(hotel_id, item_id)` en `stock_movements`/`linen_movements`, `guests.retention_until`.
- **Advertencia metodológica:** el conteo de `idx_scan` que obtuve refleja solo mi carga de prueba. **No elimine índices con esa lista**; recoja 2 semanas de `pg_stat_user_indexes` en el piloto y borre los que sigan en 0, con `DROP INDEX CONCURRENTLY` (las migraciones del repo casi nunca lo usan: 1 de 88 en la parte B).

### 4.4 Outbox de eventos
Cada escritura ORM de cualquier modelo mapeado inserta **una fila por dominio afectado** en `domain_event_outbox` (una habitación nueva = 3 filas; una reserva = 5), con un trigger que hace `pg_notify`. Pesa ~1,3 KB/fila con índices. Un piloto de 200 escrituras/día genera ~1.000 filas/día ≈ **0,5 GB/año si nunca se purga**. ✔ Verificado por lectura: el modelo de *retention watermark* (`domain_event_outbox_retention_watermarks`) no tiene referencias fuera de `app/models` y no existe `DELETE` sobre el outbox en `app/` ni `app/tasks/`; el único `pg_cron` del repo cubre formularios públicos, no esta tabla. Además la tabla tiene 5 índices (el `pending` no es parcial) y un trigger `pg_notify` por fila.

**Tablas que crecen sin purga** (§ 0.3 M1): `rate_limit_events`, `security_tokens`, `user_sessions`, `notifications`/`notification_outbox`, `payment_webhook_events` (payload completo), 5 tablas de auditoría, `ai_assistant_*`, `fx_rate_snapshots`, `analytics_export_jobs`, `whatsapp_messages`, `payment_proof_blobs`. La excepción es `public_inquiries` (90 días, `pg_cron`, migración `20260925`): **ese es el patrón a copiar** (`solutions/retention_pg_cron.sql`).

### 4.5 Tamaño y 500 MB de Supabase Free
Esquema vacío: **22 MB** (catálogo de 173 tablas/656 índices). Datos: **~7 MB por hotel con 2 años de historia**, 63 % de índices. Con 500 MB caben ~60 hoteles de 2 años **sin** contar auditoría, outbox, sesiones, notificaciones ni comprobantes de pago (`payment_proof_blobs` guarda imágenes en la DB; verificar).

---

## 5. Procesos en segundo plano, realtime y lo que "se pisa"

| Trabajo | Dónde corre hoy | Observación |
|---|---|---|
| Barrido de no-shows | (1) Celery beat cada 300 s, (2) **cron Render cada 5 min** (`run_scheduled_hotel_jobs`), (3) **otro cron Render horario** (`render-no-show-cron.yaml`) | El (3) apunta a `fromService: hotel-backend`, **que no existe** en `render.yaml` (el servicio se llama `hotel-chipre-pms-api`): está roto y duplica al (2) |
| Outbox de notificaciones / reportes diarios | Celery (60 s / 15 min) **y** el cron SQL de 5 min | Mismo trabajo, dos orquestadores |
| Hechos de analítica | flag síncrono en escritura, cola drenada por el cron, Celery incremental (300 s), conciliación nocturna, CDC a ClickHouse | Cinco caminos |
| Realtime | Redis pub/sub, Postgres `LISTEN/NOTIFY`, polling de respaldo 60 s, + fila durable en outbox + dedupe | Tres transportes; en producción solo uno está activo |
| Auth | JWT Bearer + sesión por cookie + CSRF; RBAC por rol y por permiso | Coexisten (documentado como transición TECH-0021) |

**Cron cada 5 minutos** = 288 corridas/día × 30 = 8.640/mes: cada una arranca Python (≈5,5 s de import), abre una conexión TLS al pooler, recorre *todos* los hoteles y ejecuta ≥2 trabajos por hotel. Además mantiene Supabase "activo" (evita la pausa de 7 días) pero a costa de carga constante. Render cobra **mínimo USD 1/mes por cada servicio cron**.

**SSE:** bien resuelto — `events.py:173` cierra la sesión de DB antes de transmitir; no retiene conexión del pool. El costo por stream abierto es un hilo/cola en memoria y una consulta de revalidación periódica.

**Dormidos pero instalados** (`requirements.txt`): `celery`, `pymongo`, `cassandra-driver`, `neo4j` (+ módulos `app/db/*`, `graph_projection.py`, `timeseries_projection.py`), `redis` (opcional en uso real), `pytest*` en dependencias de producción. El plan NoSQL (`docs/CONSOLIDATION_AND_NOSQL_PLAN.md`, 2026-06-24) fue un requisito explícito "NoSQL obligatorio… para lectura/escritura más rápida", adoptado **sin medición**; el propio `render.yaml` hoy declara perfil "Postgres único". Esta auditoría confirma que Postgres resuelve todo en < 4 ms a 195.000 reservas.

---

## 6. Memoria, arranque y dependencias

- `import app.main`: **5,5 s y 206 MB** de pico antes de servir nada (1.331 módulos). En Render Free (CPU muy reducida; la doc consultada no la especifica y suele citarse 0,1 vCPU — `inferred`) esto explica buena parte del cold start de ~32–60 s que documenta `STATUS-TODAY` y la propia Render (~1 min).
- RSS: 229 MB reposo → 283 MB pantallas normales → **499 MB** tras 4 rondas de reportes → **1.233 MB** bajo mezcla concurrente. Lo que crece es la materialización ORM de historiales completos (Python no devuelve la memoria al SO).
- **OR-Tools** (solo `allocation_engine.run_allocation`, import perezoso): al resolver una vez suma **+77 MB residentes** y arrastra pandas+numpy; el solver puede correr hasta 30 s dentro de un request.
- Peso instalado: **291 MB**; de ellos **178 MB** son `ortools+pandas+numpy+…`, 11 MB Cassandra, 10 MB Mongo/bson, 5 MB Celery, 3 MB Neo4j, 4 MB pytest. ~65 % de `site-packages` es opcional en el perfil actual.
- `Dockerfile.backend`: una sola etapa con `build-essential` y `libpq-dev` (innecesarios con `psycopg2-binary`), sin `uvicorn[standard]` (uvloop/httptools).

---

## 7. Infraestructura y planes gratuitos (límites verificados hoy)

| Servicio | Límite relevante | Fuente / estado |
|---|---|---|
| **Render Free (web)** | 750 h/mes por workspace; se duerme a los 15 min; ~1 min de cold start; sin disco; **sin cron jobs gratuitos**; 1 instancia | [doc oficial](https://render.com/docs/free) |
| **Render Starter** | USD 7/mes · 512 MB · 0,5 CPU; Standard USD 25 · 2 GB · 1 CPU; cron: prorrateo por segundo, **mínimo USD 1/mes por servicio** | [cron docs](https://render.com/docs/cronjobs) y búsqueda de precios |
| **Render ancho de banda saliente** | Según una reseña de terceros, desde 2026-08-01 el workspace Hobby incluye **5 GB/mes** (antes 100 GB) | `needs-verification` en el panel |
| **Supabase Free** | 500 MB DB · 5 GB egress · 1 GB storage · 2 proyectos; **pausa por baja actividad en 7 días**; PITR es de pago | [billing](https://supabase.com/docs/guides/platform/billing-on-supabase), [pausing](https://supabase.com/docs/guides/platform/free-project-pausing) |
| **Vercel Hobby** | **"restringido a uso personal no comercial"**; comercial = cualquier deployment con fin de lucro de *cualquiera* involucrado | [fair use](https://vercel.com/docs/limits/fair-use-guidelines) |
| **Cloudflare Workers Free** | 100.000 req/día · 10 ms CPU · **5 Cron Triggers** | [límites](https://developers.cloudflare.com/workers/platform/limits) |
| **Cloud Run** | 2 M req, 180.000 vCPU-s, 360.000 GiB-s gratis; facturación por request | `inferred`: un SSE de larga duración mantiene la CPU facturable → no apto para este diseño |
| **Neon Free** | 100 CU-h/mes, 0,5 GB, escala a cero a los 5 min | alternativa de DB; menos holgado que Supabase |

**Consecuencias para este proyecto:**
1. **Hoy `render.yaml` es un plan pago** (web Starter USD 7 + cron Starter ≥ USD 1; más otro cron si se despliega `render-no-show-cron.yaml`), no gratuito.
2. **Vercel Hobby no es válido** para el piloto comercial → mover el frontend estático a **Cloudflare Pages** (o pagar Vercel Pro).
3. **El egreso de 5 GB de Supabase importa:** 68 KB/request liviano → ~75.000 requests/mes agotan el cupo; 5 usuarios × 500 requests/día ya lo rozan. Corregir la sobrecarga del ORM (§ 3) baja a 46 KB (liviano) y 334 KB (pesado) y es *necesario* para el plan gratuito. (`needs-verification`: confirmar con Supabase que el tráfico API→DB cuenta como egress.)
4. **Render Free con una sola instancia puede quedar despierto 24/7** (744 h < 750 h) si algo lo consulta cada <15 min; un Cron Trigger gratuito de Cloudflare puede cumplir esa función **y** reemplazar al cron de Render. Costo: 512 MB de RAM y CPU muy limitada → solo viable tras los arreglos de §§ 2–3.
5. **Región:** API y base deben compartir región (§ 2.1). `render.yaml` no fija `region` y `.env.render` (ejemplo) menciona Supabase `aws-0-us-east-1`; la única medición de producción (QA 2026-10-06) dio 38–50 ms por consulta. `needs-verification` (§ 0.3 O2).
6. **El blueprint puede no ser el servicio que corre** (§ 0.3 O1): `render.yaml` describe `hotel-chipre-pms-api` en plan Starter con pre-deploy, pero los reportes de `qa/` observan `hotel-backend` en plan Free sin pre-deploy. Toda estimación de costo de esta sección sale del blueprint; confirmar en el panel.
7. **`autoDeploy: true` sin `buildFilter`** (`render.yaml:134`): cada commit —también los de documentación, 63 de 111 commits no-merge, 57 %— reinstala dependencias, migra y reinicia. Un `buildFilter` por `app/`, `alembic/`, `requirements.txt` evita esos despliegues.
8. **Sin copias de seguridad programadas en el repo** (§ 0.3 O7): ni `pg_dump` ni cron de backup; el único drill es local. Supabase Free no incluye PITR; si incluye copias diarias es `needs-verification`. Antes de cargar datos reales: un `pg_dump` semanal cifrado a un bucket gratuito (R2/B2) y **una restauración probada**.
9. **`vercel.json` duplicado** (§ 0.3 O8): el de la raíz tiene 1 rewrite; `frontend/vercel.json`, 9 (las 8 páginas de marketing estáticas). Si Vercel usa el de la raíz, esas rutas caen al `index.html` genérico y pierden los meta tags por ruta (SEO y vista previa de enlaces; el bundle JS es el mismo, así que no cambia el ancho de banda). Resolver con el Root Directory del proyecto, o al migrar a Cloudflare Pages.

**Topologías comparadas (estimadas):**

| | Hoy (`render.yaml`) | A: casi gratis | B: robusta, bajo costo |
|---|---|---|---|
| Frontend | Vercel Hobby ⚠ | Cloudflare Pages | Cloudflare Pages |
| API | Render Starter USD 7 | Render Free + ping/cron CF | Render Starter USD 7 |
| Tareas programadas | 1–2 servicios cron (≥ USD 1 c/u) | Cloudflare Cron → endpoint interno | Cloudflare Cron → endpoint interno |
| DB | Supabase Free | Supabase Free | Supabase Free (Pro si el egreso lo exige) |
| **Costo mensual** | **~USD 8–9** (+ Vercel Pro si se regulariza) | **~USD 0** | **~USD 7** |
| Riesgo | cold start / OOM / licencia | cold start de ~1 min si falla el ping; 512 MB | 512 MB aún ajustado hasta corregir § 3 |

---

## 8. Frontend

**Bien resuelto:** división por rutas (lazy), `QueryClient` con `staleTime` 30 s, sin refetch en foco, sin reintento en 4xx; **cero `refetchInterval`/`setInterval`**; invalidación por eventos de dominio (SSE) en lugar de polling; PWA con service worker; spec e2e que verifica 0 requests en reposo.

**A mejorar (medido con `vite build`):**
- Chunk de entrada: **571 kB / 179 kB gzip**, bajado por *todo* visitante (marketing incluido). **44 % es `react-router` v7** (399 kB sin minificar); luego react-dom 14 %, i18next 9 %, `@tanstack/query-core` 8 %. Alternativas: `react-router` v6 o TanStack Router/wouter; cargar los locales (`es`+`en`, 16 namespaces) bajo demanda.
- `ReservationsPage.tsx` tiene **6.120 líneas** (chunk de 205 kB) y otras 8 páginas superan 1.000; dificultan optimizar renders y revisión.
- **Imágenes sin optimizar:** `logo-full.png` **992 kB**, `logo-avatar.png` 388 kB, `icon-512-maskable.png` 308 kB; 2,7 MB de imágenes en `dist` (5,4 MB total). A WebP/SVG se ahorra ~90 %. Cuenta contra los 5 GB de ancho de banda saliente.
- `@tanstack/react-query-devtools` figura en `dependencies` (se excluye del build prod, pero conviene `devDependencies`); `@capacitor/cli` ^7 vs `@capacitor/core` ^8 (desalineados).
- **35 MB de proyectos nativos** (`frontend/ios` 20 MB, `frontend/android` 15 MB) versionados para un piloto web/PWA.
- **Fan-out de invalidación:** una escritura invalida las consultas activas de *todos* los usuarios conectados al hotel; si alguien tiene abierto un reporte pesado, se re-ejecuta (hoy 2,9 s/110 consultas). Otra razón para arreglar § 3. ✔ **90 de los 118 modelos** emiten el dominio `analytics` (`domain_events.py:276-…`), de modo que casi cualquier escritura toca los reportes (§ 0.3 F3).
- **Lectura completa de `frontend/src` (§ 0.3 F1–F16):** lo que más pesa para el consumo es (1) las hasta 9 requests de arranque antes de la primera consulta de la página y el bloqueo del render hasta el refresh (F2), (2) las listas de 200 filas sin ventana de fechas (F1) y las pantallas sin cota (F9), (3) el fan-out de invalidación (F3), (4) los reportes pedidos dos veces (F10) y (5) i18n/Drawer en el chunk de entrada (F11). Correctitud y seguridad: sin `queryClient.clear()` al cerrar sesión (F5), `PricingPage` puede borrar todos los planes (F6) y las credenciales del wizard (F7/N3).
- **Bundle:** los números de esta sección son de `vite build`; los ahorros de la carga perezosa de i18n (−48 % solo `en`; −95 % por ruta) son cálculo sobre los JSON y **no se construyeron** (F11).

---

## 9. Repositorio, CI y pruebas

- **Producto:** `app` 101k LOC + `frontend/src` 61k + `alembic` 19k. **No producto:** `tests` 103k + `e2e` 16k (justificado), pero también `docs` 35k + `knowledge` 75k + `qa` 9k + andamiaje de agentes 14k líneas: ~**133.000 líneas de documentación/proceso**, más que el backend. Riesgo: deriva documental (el propio repo marca secciones como `historical`).
- `.git`: 32 MB de pack (el 20-sep se resolvió `graph.json` de 53 MB; bien documentado).
- **CI:** `pr-validation.yml` (backend, frontend, e2e Playwright con timeout 30 min), `build-and-push` en cada push a `main`, y 4 workflows de QA/gates. Si el repo es privado, GitHub Free da 2.000 min/mes: un e2e de 30 min por PR los consume rápido (`needs-verification`: visibilidad del repo).
- **Costo de CI por push (§ 0.3 O3/O4):** `pr-validation` corre 3 jobs en paralelo (backend en Python 3.11, frontend, e2e en 3.12) **sin `concurrency`, sin `paths-ignore` y sin caché de Playwright**, y hace `npm ci` dos veces; cada push a un PR cuesta ≈ **29–35 min** (e2e ≈ 16,1 min medido en un reporte de QA; el resto, estimado). 63 de los 111 commits no-merge del clon (57 %) no tocan código de ejecución. `build-and-push.yml` construye y publica 2 imágenes por merge que nadie consume (≈ 7–11 min, estimado). Si el repo es privado, 2.000 min/mes se agotan con ≈ 60 pushes. Palancas: `concurrency`, `paths-ignore`, caché de navegadores, quitar `build-and-push`, `timeout-minutes` (solo 3 jobs lo tienen) y unificar Python 3.12.
- **`requests` sin declarar:** se importa en 8 módulos (`grep`) y no figura en `requirements.txt`; hoy llega por una dependencia transitiva y un cambio ajeno puede romper el arranque. 11 de 33 pins son prescindibles en producción (§ 6).
- **Brecha de pruebas:** los tests usan SQLite/`create_all`; **no existe una prueba que migre con Alembic y arranque la app** (de ahí los bugs de § 0 #6). Agregar un job "Alembic → app → smoke" contra Postgres, y `alembic check`. Misma brecha para N1 (auditoría posterior al `commit`: en SQLite persiste por una rareza del SAVEPOINT) y M4 (RLS con rol `NOBYPASSRLS`): hay que probar contra PostgreSQL con el rol de aplicación real.
- **Suite backend medida** (copia sin `qa/`, `docs/`, `knowledge/`): **2.943 passed, 40 skipped, 12 xfailed, 101 failed**. Los 101 fallos son de entorno (tests de QA/agent-ops/preview que leen esas carpetas) y son **idénticos** con y sin el experimento de carga perezosa. Duración ≈ 23 min en 4 vCPU compartidas (el reloj mostró 31 min; descuento ~8 min en que pausé el proceso para medir carga). Hay ≥ 10 tests de migración *up/down/up* sobre SQLite de 12–20 s cada uno.
- **Costo del cambio de carga perezosa:** con las 138 relaciones en `lazy="select"` solo fallan 6 tests nuevos (`test_row_locks` ×4, `test_soft_delete` ×1, `test_allocation_v72_rules` ×1). La suite **no detecta** el N+1 de `/api/bookings/` (47 → 6.512 consultas): hace falta además un test de *presupuesto de consultas* por endpoint (el repo ya tiene `query-load-budget.test.mjs` en frontend; falta el equivalente en backend).

---

## 10. ¿Cambiar de lenguaje o de tecnología? Por qué hoy y qué cambiaría

### 10.1 Datos que deciden
- CPU por request liviano: **~38 ms** en Python (perfil: 15 % driver DB, 14 % permisos, ~40 % construir/validar objetos de lectura). Un worker sirve **25–34 req/s** (sin latencia de red).
- Demanda del piloto (5–30 usuarios del hotel, una acción cada 5–10 s, más el re-fetch por eventos): **1–6 req/s**. Python no es el cuello de botella; sí lo son (a) viajes a la DB, (b) memoria por ORM, (c) pool de 6 conexiones.
- Lo que un lenguaje compilado ahorraría: RAM base de ~20–40 MB (vs 230 MB), CPU por request 10–30× menor, cold start de milisegundos (vs 5,5 s). Ninguno de esos tres es lo que hoy rompe el piloto, y todos se acercan con arreglos de diseño en Python (RSS 611 MB → objetivo < 350 MB con SQL agregado).

### 10.2 Opciones evaluadas
| Opción | Ventajas | Costo / riesgo | Veredicto |
|---|---|---|---|
| **Quedarse en Python/FastAPI** y corregir el diseño | 0 reescritura; 2.055 tests; Pydantic; OR-Tools nativo | Hay que disciplinar el ORM y recortar dependencias | **Recomendado ahora** |
| TypeScript (Hono/Fastify + Drizzle/Kysely + zod) | Un solo lenguaje con el frontend (comparte esquemas zod/tipos); async nativo (SSE barato); 60–100 MB RSS | Reescribir ~101k LOC + 103k de tests; OR-Tools sin binding oficial para Node | Candidato **si** se decide rehacer más adelante |
| Go (chi + pgx + sqlc) | 20–40 MB RSS, binario único, cold start ~ms (ideal para free tier "scale to zero") | Reescritura completa; menos ecosistema de dominio; OR-Tools sin binding oficial → sidecar Python | Solo para extraer **rutas de lectura** calientes si hiciera falta |
| Rust (axum + sqlx) | Máximo rendimiento | Curva y costo de desarrollo muy altos | No justificado |
| Elixir/Phoenix | Reemplaza SSE/WebSocket/Redis/LISTEN nativamente | Ecosistema/equipo; reescritura | No |
| PostgREST/RPC de Supabase para CRUD simple | Elimina endpoints triviales; ya usan RLS | Duplicaría reglas de negocio; control fino de auditoría | Parcial, futuro |

**Orden de magnitud de una reescritura:** meses-persona (`inferred`), con riesgo de regresión sobre reglas hoteleras ya probadas, para ganar capacidad que el piloto no necesita. **Criterios para reabrir la decisión** (medir primero): >50 req/s sostenidos, >200 SSE simultáneos por instancia, o RAM por hotel que no cierre con el plan elegido.

### 10.3 Por qué se usa cada tecnología y qué haría distinto
| Tecnología | Por qué está (documentado/inferido) | Evaluación |
|---|---|---|
| FastAPI + SQLAlchemy + Alembic | `docs/tooling-stack.md`; velocidad de desarrollo, Pydantic, OR-Tools | Correcto. Cambiar la *configuración* del ORM, no el ORM |
| PostgreSQL (Supabase) + RLS | Aislamiento multi-hotel como defensa en profundidad | Correcto. `needs-verification`: si prod conecta con `postgres` (BYPASSRLS) o dueño de tabla, **la RLS no filtra nada**; usar un rol de aplicación `NOBYPASSRLS` |
| Redis, Celery, Mongo, Cassandra, Neo4j, ClickHouse | Requisito explícito de junio ("NoSQL obligatorio") sin medición | **Retirar** de dependencias, compose y código muerto; Postgres basta (medido) |
| SSE + `LISTEN/NOTIFY` + outbox durable | Realtime sin Redis (perfil SQL-only) | Buen diseño; reducir filas por evento y purgar |
| OR-Tools CP-SAT | Asignación óptima de habitaciones | Para 30–80 habitaciones un algoritmo voraz/húngaro alcanza; mover a extra opcional (+77 MB) |
| React + Vite + TanStack Query + Tailwind + i18next | Estándar | Muy bien; ajustar router/imágenes |
| Capacitor (iOS/Android) | Futuro app móvil | Prematuro; sacar del repo principal hasta necesitarlo |
| Vercel / Render / Supabase | Plataformas con plan gratuito | Vercel Hobby no cumple licencia; Render y Supabase OK con los ajustes de § 7 |

---

## 11. Plan priorizado (impacto / esfuerzo)

### Fase 0 — Antes de abrir el piloto (horas–2 días)
1. Migración Alembic para las 4 tablas legacy (o retirar la capa legacy según `docs/decisions/subscription-model-consolidation-plan.md`) **+ job de CI "Alembic → arrancar → smoke"**.
2. Guardia `connection is None` en `database.py:_handle_query_error`.
3. Eliminar o paginar `GET /api/bookings/`; límites por defecto en los 65 listados sin paginar.
4. Verificar en los paneles: región de Render vs Supabase, rol de la `DATABASE_URL` (¿`postgres`?), tamaño real, plan de Vercel.
5. Borrar `render-no-show-cron.yaml` (roto y duplicado).
5-bis. **Gratis y de minutos (§ 0.3 O3–O8):** `concurrency: cancel-in-progress` y `paths-ignore` (docs/knowledge/qa/.graphify) en `pr-validation.yml`; quitar `build-and-push.yml` (o dejarlo manual); `buildFilter` en `render.yaml`; declarar `requests` en `requirements.txt`; elegir un solo `vercel.json`; `.mcp.json` con rutas portables; **un `pg_dump` semanal cifrado y una restauración probada** antes de cargar datos reales.

### Fase 0-bis — Integridad y seguridad (antes de que entre un usuario real; § 0.2)
- **N1** Mover las 15 escrituras de auditoría posteriores al `commit` a la misma transacción; test de auditoría contra PostgreSQL (el SQLite de los tests lo oculta).
- **N2** Almacenamiento de objetos persistente (R2 o Supabase Storage); prohibir `OBJECT_STORAGE_BACKEND=local` en el validador de producción; migrar `payment_proof_blobs`.
- **N3** Cifrar o no persistir las credenciales del asistente de onboarding; rotar las que ya se hayan cargado.
- **N4** API pública: resolver/crear el huésped dentro del endpoint y devolver un esquema público sin documento.
- **N15** Autenticar `/health/datastores` (dejar `/health/live` y `/health/ready` públicos).
- **N18** Decidir el perfil de correo del piloto: con `EXTERNAL_EFFECTS_ENABLED=false` no sale ningún correo.
- **N19** Tests de fechas con la zona del hotel (`hotel_today`) en lugar de `date.today()`: elimina el fallo de CI entre 00:00 y 03:00 UTC.
- **M4** Decidir el rol de la `DATABASE_URL` (`BYPASSRLS` ⇒ la RLS no protege; `NOBYPASSRLS` ⇒ toda clave de la API pública da 401) y arreglar la búsqueda de claves por hash (función `SECURITY DEFINER` o política permisiva de lectura); agregar el test con un rol `NOBYPASSRLS`.
- **F5/F6** `queryClient.clear()` al cerrar sesión y `userId` en las claves de caché; `min_length=1` en `plans` de precios y deshabilitar "Publicar" hasta que cargue el `GET`.

### Fase 1 — Capacidad y memoria (1–2 semanas) — el mayor retorno
6. **Carga perezosa por defecto** + `selectinload` explícito donde se serializan relaciones (medido: reportes ×3–×6, RSS −50 %, sin 503; rompe 6 tests de forma de SQL). Agregar un test de presupuesto de consultas por endpoint para no reintroducir N+1.
7. **Colapsar el costo fijo por request** (9 → 3–4 consultas): quitar `pool_pre_ping` (usar `pool_recycle` + reintento por desconexión), fusionar los `set_config` en una sola sentencia, cachear usuario/membresías/permisos con TTL corto invalidado por el `NOTIFY` que ya existe, resolver solo el permiso pedido. (Medido: +36 % req/s liviano.)
8. **Reportes con `GROUP BY` en SQL** (`financial_report`, `analytics/rooms`, `housekeeping`, `cash_daily_summary`).
9. Pool/hilos: liberar la conexión antes de serializar o limitar concurrencia de endpoints pesados con un semáforo; el pool 4+2 con 40 hilos genera 503 a partir de ~40 usuarios simultáneos.
10. Reducir login: 4 commits → 1–2; rate limiter en memoria para el proceso único (con respaldo persistente solo en bloqueo).
10-bis. **Costos nuevos de § 0.2:** `async def` con base síncrona en webhooks de OTA/WhatsApp/FX → `def` (hilo) o `run_in_threadpool` (N9); sacar el I/O externo (correo, Mercado Pago, Stripe) de la transacción del request (N10); caché de `billing_policy` y de verificación de claves de API, con `last_used_at` espaciado (N6, N7); HMAC en lugar de Argon2id para códigos de 6 dígitos (N8); tope global de cuerpo de request en un middleware ASGI (N13).

10-ter. **Frontend de arranque y listas (§ 0.3 F1–F3, F8–F10, F14):** sembrar permisos e idioma desde la respuesta del refresh (de 9 a 7 requests; a ≈ 4 si además se fusionan config, onboarding, suscripción y notificaciones en un solo `GET` de arranque); ventana de fechas y paginación en `/reservas`, Dashboard y Stock; debounce en las búsquedas; invalidar por clave concreta (sin `analytics` en cada escritura); pedir día y semana de reportes en una sola request; `Idempotency-Key` estable por intento de formulario.

### Fase 2 — Costo y plan gratuito (días)
11. Frontend a Cloudflare Pages; endpoint interno `POST /internal/jobs` con secreto + **Cloudflare Cron** cada 5–15 min; apagar el servicio cron de Render. Decidir entre topología A (gratis) o B (USD 7).
12. Recortar dependencias: `requirements.txt` → núcleo + `requirements-dev.txt` (pytest) + extras opcionales (`ortools`, `redis`); Dockerfile multietapa sin `build-essential`; `uvicorn[standard]`. Quitar Mongo/Cassandra/Neo4j de `docker-compose.yml` y del código (`app/db/*`, `graph_projection`, `timeseries_projection`).
13. Imágenes de marca a WebP/SVG; locales por idioma y por ruta bajo demanda (`en` perezoso primero: cambio solo en `i18n.ts`); `ReservationDetailDrawer` con `React.lazy` y `DashboardPage` cargando su propio namespace (prerrequisitos de lo anterior: ambos usan `reservations`, que hoy viaja en la entrada); quitar la hoja de Google Fonts; versionar la caché del service worker; evaluar `react-router` v6/TanStack Router. Archivos en base64: reescalar en el navegador y subir con multipart/URL firmada (F15).
14. Sacar `frontend/ios` y `frontend/android` del repo principal (o a rama/repo aparte).

### Fase 3 — Higiene de datos (antes de escalar)
15. Dinero `Float → Numeric` (empezar por tarifas y reglas de impuestos); fechas a `timestamptz`; enums nativos → `text + CHECK` al tocar cada dominio.
16. Índices: quitar los claramente redundantes (`ix_reservation_dates`, `*_hotel_id` solitarios, `external_id`/`source_provider_code` solitarios), pasar a **parciales `WHERE deleted_at IS NULL`**, consolidar GIN de huéspedes, `fillfactor` 85–90 en `reservations`; **decidir con 2 semanas de `pg_stat_user_indexes`**. Para grandes hoteles: cota inferior por estadía en la grilla o GiST `daterange`.
17. Purga del outbox, `rate_limit_events`, `security_tokens`, sesiones, exportaciones y auditorías operativas **con `pg_cron`, siguiendo el patrón de las migraciones `20260925`/`20260926`** (N11; lista completa en M1; código probado en `solutions/retention_pg_cron.sql`); medir crecimiento semanal. Corregir la semántica de permisos cruzada (N12) y pasar el dinero de la API y de las tarifas a `Decimal`/`Numeric` (N14; el libro ya lo es).
17-bis. **Índices (M2/M3):** crear primero los que faltan (`room_state_events`, `analytics_export_jobs`, `hotel_api_keys.key_hash`, `(hotel_id, item_id)` en stock/lencería); parcializar los 6 índices sobre columnas casi siempre NULL; **después** quitar los ≈ 70 redundantes con 2 semanas de `pg_stat_user_indexes` y `DROP INDEX CONCURRENTLY`. Retirar el esquema dormido de OTA/allocation si el producto no lo usará (M6).
18. Consolidar sistemas paralelos (suscripción legacy/v2, OTA, conexiones, precios por método de pago) y las 28 rutas duplicadas `/x` vs `/api/x`.

### Metas medibles (para validar cada fase)
| Métrica | Hoy | Meta |
|---|---|---|
| Consultas por GET autenticado (mediana) | 9 | ≤ 4 |
| Login | 37 consultas / 5 tx | ≤ 12 / 2 |
| `reports/revenue` | 110 q / 2,9 s | ≤ 6 q / ≤ 150 ms |
| RSS tras carga mixta (5–20 usuarios) | 1.233 MB | < 400 MB |
| Req/s con reportes en la mezcla | 2–3 | ≥ 15 |
| Egreso DB→API por request liviano | 68 KB | ≤ 25 KB |
| Errores 503 por pool | sí (≥ 10 usuarios) | 0 |

---

## 12. Riesgos y lo que no pude verificar
- **No verificado en producción:** región real de API y DB, rol de la base y si la RLS aplica, tamaño y crecimiento reales, plan de Vercel, visibilidad del repo (minutos de Actions), si el egreso API→DB cuenta contra el cupo de Supabase.
- **Medido sin latencia de red** y con CPU mayor a la de Render: cifras absolutas de req/s serán menores en producción; las proporciones y los conteos de consultas no cambian.
- **Prototipos no productivos:** el caché de autenticación (TTL 10 s) omite a propósito la revocación inmediata que el diseño actual exige ("una revocación debe verse en el siguiente request"); implementarlo en serio requiere invalidar con el `NOTIFY` existente.
- **Estado de verificación de la tercera pasada:** las diez partes (7 de frontend, 2 de migraciones y ops) pasaron por un segundo lector (262 afirmaciones: 198 confirmadas, 64 corregidas; todas incorporadas) y comprobé yo los puntos de mayor impacto (`frontend-notes/verificacion-manual.md`); lo no comprobado de forma individual queda en ◐/○. Cifras con `estimado` (minutos de CI, ahorro de i18n, costo de preflight CORS) **no se midieron**.
- **Límites de planes gratuitos** cambian; los de Render (ancho de banda desde agosto de 2026) provienen de una reseña de terceros — confirmar en el panel antes de decidir.

## 13. Reproducir
Ver [`scripts/README.md`](scripts/README.md).
