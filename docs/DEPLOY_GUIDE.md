# Hotel Chipre PMS - Deploy Guide

> Nota de vigencia: esta guía conserva una baseline técnica del 2026-09-03.
> Describe configuración y requisitos del repositorio, no prueba qué plan,
> servicios o variables están activos hoy en Vercel, Render o Supabase. Antes
> de cambiar producción, confirmar el estado directamente en esos proveedores.

## Baseline de trazabilidad TECH-0140

Esta copia fue revisada el 2026-09-03 desde la rama
`feature/tech-0140-realtime-recovery-contract`, commit completo
`d907adc` como base de esta actualización. El árbol estaba limpio antes de
los cambios documentales y la cabeza Alembic observada es
`tech0140_job_runtime (head)`.

Configuración no sensible confirmada en código/plantillas: `APP_ENV` separa
development/test/production; `REALTIME_EVENTS_ENABLED=true`,
`REALTIME_EVENTS_HEARTBEAT_SECONDS=15`,
`DISTRIBUTED_LOCK_ENABLED=true`; producción exige
`DISTRIBUTED_LOCK_REQUIRED=true`; y `INBOUND_PROVIDER_EVENTS_ENABLED=false`
para preview QA. `CORS_ORIGINS` debe ser explícito y no contener `*`.
`DATABASE_URL`, `REDIS_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`,
`CLICKHOUSE_URL` y todas las credenciales son referencias de configuración,
no valores confirmados en este documento.

El endpoint `GET /api/events/recovery` permite recuperar invalidaciones por
cursor sin exponer payloads. El cliente ejecuta recovery antes de abrir o
reabrir SSE, persiste el cursor por usuario/hotel y usa polling acotado cuando
realtime está degradado. La disponibilidad de Redis/Valkey y las URLs privadas
de proveedor quedan `needs-verification` hasta una QA aislada autorizada. Esta
baseline no provisiona ni muta proveedores externos.

Arquitectura objetivo:
- Frontend/landing/app: Vercel
- Backend API: Render
- Base de datos: Supabase
- DNS: Cloudflare

## 1) Vercel

Crear un proyecto desde la raíz del repo.

Config:
- Framework: Vite
- No usar `FastAPI` como framework preset para este proyecto de Vercel.
- Build command: usar la del `vercel.json` de la raíz
- Output directory: `frontend/dist`
- Rewrites SPA: todas las rutas a `/index.html`
- Si el proyecto de Vercel usa `Root Directory = frontend`, la config equivalente vive en `frontend/vercel.json`.

Dominios a conectar:
- `hotels-pms.com`
- `app.hotels-pms.com`

Variables de entorno:
- `VITE_API_URL=https://<render-service>.onrender.com/api`
- `VITE_PUBLIC_SITE_URL=https://hotels-pms.com`
- `VITE_PUBLIC_APP_URL=https://app.hotels-pms.com`
- `VITE_PUBLIC_APP_HOSTNAME=app.hotels-pms.com`
- `VITE_ALLOW_INDEXING=true` en production

## 2) Render

Crear un Web Service desde `render.yaml`.

Config del servicio:
- Build command: `pip install -r requirements.txt`
- Pre-deploy command: `python -m alembic upgrade head`
- Start command: `exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}`
- Healthcheck: `/health`
- El Blueprint declara autoscaling de 3 a 50 instancias con objetivos de CPU
  60% y memoria 70%; requiere workspace Render Pro+ y debe validarse con
  telemetría antes de certificar capacidad.
- El Blueprint declara un worker Celery separado y un beat separado. Ambos
  usan el Key Value Valkey administrado, persistente y privado.

Regla de esquema:
- Producción, preview, QA y staging deben ejecutar Alembic antes de iniciar la aplicación.
- El backend falla cerrado si PostgreSQL no tiene `alembic_version` con una revisión aplicada.
- `create_all()` queda reservado para desarrollo/tests locales; no se usa para reparar drift en un deploy.
- Cuando el proveedor permita un release/pre-deploy job separado, ejecutar allí `alembic upgrade head` y dejar el proceso web sólo con Uvicorn.

Variables de entorno:
- `APP_ENV=production`
- `DATABASE_URL=postgresql+psycopg2://...` (Supabase)
- `APP_BASE_URL=https://<render-service>.onrender.com`
- `FRONTEND_URL=https://app.hotels-pms.com`
- `CORS_ORIGINS=https://hotels-pms.com,https://app.hotels-pms.com`
- `JWT_SECRET=<strong secret>`
- `MANAGER_PIN=<6+ digits>`
- `INTEGRATIONS_ENCRYPTION_KEY=<fernet key>`
- `EMAIL_PROVIDER=resend`
- `RESEND_API_KEY=<resend key>`
- `SYSTEM_EMAIL_FROM="Hotel Chipre PMS <noreply@auth.hotels-pms.com>"`
- `SYSTEM_EMAIL_REPLY_TO=hotelxpms@gmail.com`
- `PUBLIC_INQUIRY_RECIPIENT_EMAIL=<destinatario comercial verificado>`
- `PUBLIC_INQUIRY_RATE_LIMIT=5`
- `PUBLIC_INQUIRY_GLOBAL_RATE_LIMIT=100`
- `PUBLIC_MARKETING_GLOBAL_RATE_LIMIT=100` (15-minute shared cap across early-access lead submissions)
- `ANALYTICS_EXPORTS_DIR=/var/exports/analytics`
- **Comprobantes internos de pagos registrados:** el pago y sus datos quedan en PostgreSQL. El comprobante se prepara en el navegador al imprimirlo o guardarlo como PDF; no se crea un archivo permanente en el servidor y no es una factura fiscal.
- **Imágenes de transferencias adjuntadas para revisión:** son evidencia distinta del comprobante interno. Sus metadatos y referencia se registran en PostgreSQL; los bytes se escriben en el almacenamiento configurado. `OBJECT_STORAGE_BACKEND=local` es el valor predeterminado y usa `OBJECT_STORAGE_LOCAL_DIR` (por defecto `./var/object-storage`), que no debe considerarse durable en un contenedor efímero. El adaptador GCS del código requiere agregar su biblioteca opcional, configurar bucket/autenticación y comprobar acceso; no está habilitado por este documento. El adaptador S3 sigue siendo un stub. Las cargas existentes deben verificarse antes de cambiar de backend: no se copian automáticamente.
- `AI_ENABLED=false` until the hotel-specific IA provider is configured
- `GEMMA_ENABLED=false`

- La migración `20260828_public_inquiries` habilita RLS y revoca el acceso de `PUBLIC`, `anon`, `authenticated` y `service_role` a la tabla y su secuencia. No hay una API pública de lectura.
- Las migraciones `20260925_public_inquiry_retention`, `20260926_legal_retention_holds`, `20260928_public_inquiry_updated_at` y `20260928_public_inquiry_retention_anchor` mantienen el job diario de `pg_cron` en Supabase. Leads y consultas se purgan a los 90 días de `updated_at`; la migración agrega la columna nullable con default de base para mantener compatibilidad con instancias anteriores, backfillea desde `created_at` y finalmente la hace obligatoria y actualiza la función, sin editar migraciones históricas. Los holds legales vigentes siguen excluidos y no reinician el reloj al liberarse. El downgrade falla cerrado si quedan registros de holds, para no borrar su historial auditable. Los avisos por email ya no copian datos personales; la consulta completa se muestra solo en Master Admin con acceso auditado y sin caché. Las claves de rate limiter se borran a los 15 minutos. En PostgreSQL local/preview sin `pg_cron`, se omite el job solo con `APP_ENV` configurado explícitamente como `development`, `test`, `qa` o `preview`; si falta o es desconocido, falla cerrada. No agrega un servicio Cron de Render ni una dependencia paga.
- La migración `20260926_legal_retention_holds` agrega el almacenamiento seguro para excepciones legales; el mismo release incluye la API `/api/master-admin/privacy-retention/holds` y la interfaz `/adminpmsmaster/privacy-retention`, detrás de sesión Master Admin, MFA y CSRF. Cada alta o liberación se registra en `/api/master-admin/audit/events` sin incluir datos de contacto; una fecha de vencimiento nula significa retención indefinida hasta liberación explícita. Las referencias admiten únicamente formatos opacos como `CASE-2026-41`, no nombres, contactos ni identificadores personales. Liberar requiere contraseña Master Admin y un TOTP de seis dígitos, de un solo uso; además se confirma la acción en pantalla. El trabajo nocturno y las operaciones sobre excepciones se coordinan mediante locks transaccionales, de modo que la purga no pueda competir con la creación de una excepción vigente. La purga excluye las excepciones vigentes; cuando vencen o se liberan, no reinician el plazo de 90 días.
- Verificar en Supabase Cron que exista `hotel-chipre-public-form-retention` con ejecución diaria y revisar `cron.job_run_details` tras el primer ciclo. El log de la función contiene únicamente conteos, nunca campos de contacto.
- Los límites persistidos por scope/clave usan `pg_advisory_xact_lock` y cuentan bajo el aislamiento PostgreSQL predeterminado `READ COMMITTED`. No elevar el aislamiento de las transacciones de request que consumen estos límites sin reemplazar el mecanismo y validar su concurrencia.
- Antes de aceptar tráfico real, confirmar que hay destinatario comercial y proveedor de email operativo. Con `PUBLIC_INQUIRY_RECIPIENT_EMAIL` vacío, la API responde con error de configuración y no persiste la consulta. Si falla el envío externo, conserva la consulta y registra el estado fallido para revisión operativa.

Variables de capacidad y warehouse:
- `REDIS_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`: provistas por el
  servicio Key Value del Blueprint cuando esté disponible. Redis/Valkey es el
  backend primario para locks; caja y asignación usan un advisory lock
  transaccional de PostgreSQL como fallback seguro si Redis no está disponible.
- `DISTRIBUTED_LOCK_ENABLED=true`
- `DISTRIBUTED_LOCK_REQUIRED=true`
- `CLICKHOUSE_ENABLED=true`
- `CLICKHOUSE_REQUIRED=true`
- `CLICKHOUSE_URL`, `CLICKHOUSE_USER`, `CLICKHOUSE_PASSWORD`: cargar como
  secretos en Render; nunca commitear valores.

## 3) Cloudflare DNS

Primero cambiar los nameservers del dominio al set de Cloudflare.

Luego crear:
- `@` -> CNAME flattening al target que entrega Vercel para el proyecto
- `app` -> CNAME al target que entrega Vercel para el mismo proyecto
- `api` -> opcional, CNAME al target que entrega Render si querés vanity API

Notas:
- Los targets exactos no se pueden deducir del repo. Copiar los valores que muestren Vercel/Render en sus dashboards.
- Si Vercel o Render piden TXT de verificación, copiar exactamente el que indiquen.

## 4) Qué validar después

- `https://hotels-pms.com/`
- `https://hotels-pms.com/precios`
- `https://hotels-pms.com/funciones`
- `https://hotels-pms.com/pms-hotelero`
- `https://hotels-pms.com/software-para-hoteles`
- `https://hotels-pms.com/faq`
- `https://app.hotels-pms.com/login`
- `https://app.hotels-pms.com/register-owner`
- `GET https://<render-service>.onrender.com/health`
- Flujo de auth:
  - register
  - verify email
  - onboarding/status

## 5) Errores típicos

- DNS no resuelto: nameservers o CNAME mal puestos
- CORS error: `CORS_ORIGINS` incorrecto en Render
- Links de email rotos: `FRONTEND_URL` no apunta a `app.hotels-pms.com`
- Frontend hablando con localhost: `VITE_API_URL` no configurado en Vercel
- Email fallando al arrancar: falta `RESEND_API_KEY` o `SYSTEM_EMAIL_FROM`
- SPA 404 en rutas internas: rewrites de Vercel ausentes o proyecto equivocado
