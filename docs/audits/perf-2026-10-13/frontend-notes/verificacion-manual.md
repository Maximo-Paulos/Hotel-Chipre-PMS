# Verificación manual de hallazgos de frontend (partes 1 y 2)

Comprobados por mí contra el código, independientemente del agente que escribió las notas.

| Hallazgo | Resultado | Evidencia |
|---|---|---|
| `/reservas` muestra las 200 reservas de estadía más antigua | **Confirmado** | `ReservationsPage.tsx:403-415` pide `order:"check_in"`, `limit:200`, sin `fromDate`; `reservation_service.py:2093` ordena `check_in_date ASC`. El comentario del código lo presenta como decisión para conservar el orden previo, pero con más de 200 reservas históricas no se ven las vigentes |
| Buscador global sin debounce | **Confirmado** (con matiz) | `ReservationGlobalSearch.tsx:22` usa el texto directo; `useReservations.ts:69-84` exige ≥ 2 caracteres y usa `keepPreviousData`, pero cada cambio de texto lanza una request |
| Locales de reservas en el chunk de entrada | **Confirmado** | `i18n.ts:10,18` importa `es/reservations.json` y `en/reservations.json` (65.843 + 63.350 = 129.193 bytes; 33.378 gzip medidos con `gzip -c`), además de 7 namespaces más |
| `GET /api/laundry/remitos` sin límite | **Confirmado** | `laundry_vendor_service.py:430-445` termina en `.all()`; `LaundryPage.tsx:184-189` lo pide sin filtros |
| `GET /api/cash-register/sessions` sin límite | **Confirmado** | `cash_register_service.py:738-744` termina en `.all()` |

## Parte 4 (onboarding, vistas públicas, panel master)

| Hallazgo | Resultado | Evidencia |
|---|---|---|
| El wizard de onboarding envía credenciales de 6 proveedores en texto plano y el backend las guarda sin cifrar | **Confirmado** (también reproducido con `scripts/verify_misc_findings.py`) | `OnboardingWizard.tsx:1603-1617` (campo de texto), `onboarding_service.py:462,484`, lector solo expone `has_credentials` (`onboarding_service.py:149-155`) |
| `PUT /api/master-admin/pricing/plans` con `plans: []` borra todos los planes públicos | **Confirmado** | `marketing_service.py:140-142` borra todo plan que no esté en el payload; `schemas/marketing.py:84-85` sin `min_length`; `PricingPage.tsx:57-93` arranca con `plans = []` y el formulario sigue enviable si el GET falla |

## Partes 3 y 5 (vistas protegidas restantes; capa `api/` y hooks)

| Hallazgo | Resultado | Evidencia |
|---|---|---|
| `CORSMiddleware` sin `max_age` (preflight en cada request cross-origin) | **Confirmado el hecho, con matiz sobre el impacto** | `app/main.py:443-451` no define `max_age`; Starlette usa 600 s por defecto y el navegador cachea por URL (con query incluida), así que el costo real depende de cuántas URLs distintas se piden por sesión: el "hasta el doble" de la nota es una **inferencia sin medir** |
| La bandeja de WhatsApp carga conversaciones con `selectin` | **Confirmado** | `models/whatsapp_crm.py:85-86,137` (`conversations` con `lazy="selectin"` en canal y contacto) |
| Los endpoints MFA devuelven `401` por código inválido | **Confirmado** | `api/auth.py:1489,1500,1532`; el cliente solo exceptúa ese `401` del cierre de sesión cuando la ruta es de *step-up* y el texto coincide exactamente (`client.ts:482-488`) |

## Partes 6, 7 y ops (comprobadas por mí mientras el Workflow verificaba fe3–fe7)

| Hallazgo | Resultado | Evidencia |
|---|---|---|
| El arranque de sesión bloquea el render hasta que `POST /api/auth/refresh` responde | **Confirmado, con matiz**: solo para quien ya tiene sesión que restaurar (`shouldRestoreInitialSession()`); el visitante anónimo de marketing no queda bloqueado | `state/session.tsx:175-177,368-379` devuelve un `<p>` mientras `isInitializing` |
| `GET` de permisos efectivos duplica lo que ya trae el login/refresh | **Confirmado** | `hooks/usePermissions.ts:16-22` sin `initialData`/`placeholderData` desde `session.permissions`; `staleTime` 5 min |
| `setPermissions` en un `useEffect` de cada montaje del hook | **Confirmado** | `hooks/usePermissions.ts:24-28` |
| "90 de 118 modelos emiten el dominio `analytics`" | **Confirmado** (contado por script sobre el mapa de `domain_events.py`) | 118 entradas, 90 con `"analytics"` (`app/services/domain_events.py:276-…`) |
| "Cada pestaña visible fija un hilo del threadpool para el stream SSE" | **CORREGIDO**: solo con transporte Redis. Con `LISTEN/NOTIFY` (perfil de `render.yaml`) el stream es asíncrono (`asyncio.wait_for(queue.get(), …)`, `domain_events.py:2160`) y **no** ocupa hilo; `iter_event_stream` (síncrono, `pubsub.get_message`, `domain_events.py:2189-2205`) es la rama Redis. El hilo por pestaña sigue existiendo para la revalidación de membresía cada 60 s (`events.py:51-80`) | `app/api/events.py:34-60`, `domain_events.py:2102-2175,2189-2241` |
| 61 columnas `Float` en el ORM; el libro de dinero ya es `Numeric` | **Confirmado**: 61 `Float` (56 con nombre de monto/tasa/precio: `price_periods` 9, `ota_price_rules` 9, `category_pricing_legacy` 8, `daily_rates` 6, …); `reservations`/`transactions`/`billing_adjustments` son `Numeric(12,2)` (corrección del verificador de migraciones) | metadatos del ORM; `app/schemas/` tiene 125 anotaciones `float` (p. ej. `transaction.py:22`, `reservation_operations.py:126-204`) |
| `/reservas`, Dashboard y Stock piden `limit=200` sin ventana de fechas útil | **Confirmado** (ver parte 1) | — |
| No hay `queryClient.clear()` al cerrar sesión; claves de caché sin `userId` | **Confirmado** | grep `queryClient.(clear\|removeQueries\|resetQueries)` en `src`: solo Gemma; `useNotifications.ts:23-24` |
| `render.yaml`: `autoDeploy: true`, sin `buildFilter`/`region`/`disk`; cron `*/5` plan `starter` | **Confirmado** | `render.yaml:134,139-143` |
| `pr-validation.yml` sin `concurrency` ni `paths-ignore`; Python 3.11 (backend) vs 3.12 (e2e) | **Confirmado** | `.github/workflows/pr-validation.yml:3-4,17,85` |
| `build-and-push.yml` construye 2 imágenes por merge y nadie las consume | **Confirmado el hecho** (solo ese workflow y un test mencionan `ghcr.io`); el costo en minutos es **estimado**, no medido | grep `ghcr.io` |
| `requests` se importa en 8 módulos y no está en `requirements.txt` | **Confirmado** | grep de imports vs `requirements.txt` |
| `vercel.json` raíz: 1 rewrite; `frontend/vercel.json`: 9 | **Confirmado** (qué archivo usa Vercel: `needs-verification`, depende del Root Directory) | diff |
| `.mcp.json` fija `/Users/maximopaulos/.local/node/bin/npx` | **Confirmado**; es la causa del `ENOENT` de `stripe`/`supabase` en esta sesión | `.mcp.json:4,16` |
| No hay backup/restore programado en el repo | **Confirmado** (0 coincidencias de `pg_dump\|backup` en `.github`, `render*.yaml`, `docker-compose.yml`); los backups gestionados del proveedor no son visibles desde el repo | grep |
| 182 llamadas a `/api/notifications` en 49 min (QA) | **No explicado**: no hay `refetchInterval`/`setInterval` en `frontend/src`; sigue como `○` hasta ver logs | `qa/operational/runs/pr117-postmerge-20261005-3c91a3e8/report.md:32` |

## Migraciones: RLS de `hotel_api_keys` frente a la búsqueda de la clave (reproducido)

| Hallazgo | Resultado | Evidencia |
|---|---|---|
| `hotel_api_keys` tiene RLS `FORCE` con política `hotel_id = NULLIF(current_setting('app.hotel_id'),'')::int`, pero `verify_key` busca la clave por hash **antes** de conocer el hotel | **Reproducido en PostgreSQL 16**: con un rol `NOBYPASSRLS` y sin `app.hotel_id`, `SELECT … WHERE key_hash = …` devuelve **0 filas**; con `app.hotel_id=1` devuelve 1. Consecuencia: o la `DATABASE_URL` de producción usa un rol con `BYPASSRLS` (entonces la RLS no protege nada), o **toda** clave de la API pública responde 401. | `alembic/versions/20260820_missing_tenant_rls.py:24-26,53-56`; `app/dependencies/api_key_auth.py:35-70` (el comentario de la línea 66-69 afirma que la búsqueda "queda fuera de RLS", pero la política no lo permite); `app/services/hotel_api_key_service.py:69` |

## Verificación por un segundo lector (Workflow `wf_99bb92bc-b2c`)

Un agente independiente por parte comprobó contra el código las afirmaciones principales de cada nota y dejó las líneas `CORREGIDO (verificación)` / `IMPRECISO` en la nota correspondiente. Resultado: **262 afirmaciones comprobadas, 198 confirmadas y 64 corregidas**.

| Parte | Comprobadas | Confirmadas | Corregidas | Tasa de corrección |
|---|---:|---:|---:|---:|
| fe1 (reservas) | 26 | 19 | 7 | 27 % |
| fe2 (páginas grandes, api/hooks) | 32 | 27 | 5 | 16 % |
| fe3 (vistas protegidas restantes) | 22 | 19 | 3 | 14 % |
| fe4 (onboarding, público, master, marketing) | 22 | 18 | 4 | 18 % |
| fe5 (`api/*` y `hooks/*`) | 26 | 16 | 10 | 38 % |
| fe6 (i18n) | 23 | 20 | 3 | 13 % |
| fe7 (shell, router, sesión, config) | 25 | 16 | 9 | 36 % |
| migraciones A | 24 | 17 | 7 | 29 % |
| migraciones B | 40 | 31 | 9 | 22 % |
| ops (CI, despliegue, scripts, QA) | 22 | 15 | 7 | 32 % |

Correcciones que cambiaron una conclusión del informe (todas incorporadas en `REPORT.md` § 0.3 y `SOLUCIONES.md`):

- **Arranque del frontend:** el endpoint es `POST /api/auth/session/refresh`; el peor caso es 62 s; son 6 lecturas propias del shell (9 requests en total, no 9–10); `render.yaml` declara plan Starter (siempre encendido), así que el cold start de Render Free solo aplica si el servicio real es Free (F2, O1).
- **SSE:** el hilo fijo por stream solo existe con transporte Redis; `render.yaml:42-43` fija `REALTIME_EVENTS_TRANSPORT=postgresql` (asíncrono) y el heartbeat de producción es 30 s (F4).
- **Onboarding:** las credenciales se pierden solo al volver a montar el wizard, no al guardar dentro de la misma sesión (F7).
- **Auditoría operativa:** 12 consultas, no 9 (cota de 240.000 filas ORM por request) (F9).
- **Calendario de tarifas:** hasta 366 columnas (≈ 3.660 celdas, 2.196 inputs), no 365 filas siempre (F9).
- **Service worker:** las navegaciones son network-first (`sw.js:77-82`); el cache-first es `:84-98` (F12).
- **`useEffectivePermissions()`:** 28 llamadas en 27 archivos, no 29 en 28 (F16).
- **CI:** 63 de 111 commits no-merge (57 %; clon superficial desde 2026-09-26), no 63 de 132 (O3, O5).
- **Región:** `.env.render` es un archivo de ejemplo; 38–50 ms por consulta (no solo 50) (O2).
- **`vercel.json` raíz:** el impacto es SEO y vista previa de enlaces (los `.html` son copias de `index.html` con meta tags por ruta), no ancho de banda (O8, § 7).
- **Dinero `Float`** (migraciones B): el libro ya es `Numeric(12,2)`; quedan 30 columnas `Float` en esa era y 61 en el ORM actual (N14, M5).
- **Migraciones A:** `price_periods` no se retira; "+17 índices" eran ≤ 14; 4 FKs compuestas con `CASCADE`, no 5; `TokenStore.issue()` también purga tokens previos (M1, M2, M5).
